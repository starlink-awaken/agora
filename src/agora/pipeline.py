"""Pipeline Orchestrator — chain multiple MCP tool calls into a workflow.

Usage:
    pipeline = Pipeline(registry, router)
    pipeline.define("research-to-derive", [
        {"tool": "toolforge.match", "args": {"goal": "{{goal}}", "context": "{{context}}"}},
        {"tool": "ontoderive.derive", "args": {"project": "{{project}}", "goal": "{{goal}}"}},
        {"tool": "ontoderive.check", "args": {"project": "{{project}}"}},
    ])
    result = await pipeline.run("research-to-derive", {"goal": "...", "context": "...", "project": "."})
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class Pipeline:
    """Defines and executes multi-step tool call pipelines."""

    def __init__(self, registry, router):
        self.registry = registry
        self.router = router
        self._definitions: dict[str, list[dict]] = {}
        self._load_builtins()

    def _load_builtins(self):
        """Load built-in pipeline definitions."""
        self._definitions["match-derive"] = [
            {
                "tool": "toolforge.match",
                "args": {"goal": "{{goal}}", "context": "{{context}}"},
                "output_as": "matched_tools",
            },
            {
                "tool": "ontoderive.derive",
                "args": {"project": "{{project}}"},
                "depends_on": ["matched_tools"],
            },
        ]
        self._definitions["research-derive"] = [
            {
                "tool": "toolforge.match",
                "args": {"goal": "{{goal}}", "context": "{{context}}"},
                "output_as": "matched_tools",
            },
            {
                "tool": "toolforge.guide",
                "args": {"goal": "{{goal}}", "context": "{{context}}"},
                "output_as": "derivation_guide",
            },
            {
                "tool": "ontoderive.derive",
                "args": {"project": "{{project}}"},
                "depends_on": ["matched_tools", "derivation_guide"],
            },
        ]
        self._definitions["derive-check"] = [
            {
                "tool": "ontoderive.derive",
                "args": {"project": "{{project}}"},
                "output_as": "derive_result",
            },
            {
                "tool": "ontoderive.check",
                "args": {"project": "{{project}}"},
                "depends_on": ["derive_result"],
            },
        ]
        self._definitions["full-pipeline"] = [
            {
                "tool": "toolforge.match",
                "args": {"goal": "{{goal}}", "context": "{{context}}"},
                "output_as": "matched_tools",
            },
            {
                "tool": "minerva.research",
                "args": {"query": "{{goal}}", "level": "L1"},
                "output_as": "research_result",
            },
            {
                "tool": "ontoderive.derive",
                "args": {"project": "{{project}}"},
                "depends_on": ["matched_tools", "research_result"],
                "output_as": "derive_result",
            },
            {
                "tool": "ontoderive.check",
                "args": {"project": "{{project}}"},
                "depends_on": ["derive_result"],
            },
        ]

    def define(self, name: str, steps: list[dict]):
        """Register a custom pipeline definition."""
        self._definitions[name] = steps

    def list_pipelines(self) -> list[str]:
        """List available pipeline names."""
        return list(self._definitions.keys())

    def get_pipeline(self, name: str) -> list[dict] | None:
        """Get pipeline definition by name."""
        return self._definitions.get(name)

    async def run(self, name: str, variables: dict[str, Any]) -> dict[str, Any]:
        """Execute a named pipeline with template variables."""
        steps = self._definitions.get(name)
        if not steps:
            return {"status": "error", "error": f"Pipeline not found: {name}"}

        outputs: dict[str, Any] = {}
        results = []

        for i, step in enumerate(steps):
            tool_name = step["tool"]
            args = self._render_args(step.get("args", {}), variables, outputs)
            label = step.get("output_as", f"step_{i}")

            logger.info("pipeline_step", pipeline=name, step=i, tool=tool_name)

            try:
                result = await self.router.route(tool_name, args)
                outputs[label] = result
                results.append({"step": i, "tool": tool_name, "status": "ok"})
            except Exception as e:
                logger.error("pipeline_step_failed", pipeline=name, step=i, error=str(e))
                results.append({"step": i, "tool": tool_name, "status": "error", "error": str(e)})
                # Continue with next step unless critical
                if step.get("critical", False):
                    break

        return {
            "pipeline": name,
            "variables": variables,
            "results": results,
            "outputs": {k: str(v)[:500] for k, v in outputs.items()},
        }

    def _render_args(
        self,
        args: dict[str, Any],
        variables: dict[str, Any],
        previous_outputs: dict[str, Any],
    ) -> dict[str, Any]:
        """Render template variables in args: {{goal}} → variables['goal']"""
        rendered = {}
        for key, value in args.items():
            if isinstance(value, str) and "{{" in value:
                # Simple template substitution
                result = value
                for vk, vv in variables.items():
                    result = result.replace(f"{{{{{vk}}}}}", str(vv))
                rendered[key] = result
            else:
                rendered[key] = value
        return rendered

    def save_definition(self, name: str, path: str | Path):
        """Save a pipeline definition to a JSON file."""
        steps = self._definitions.get(name)
        if not steps:
            raise ValueError(f"Pipeline not found: {name}")
        Path(path).write_text(json.dumps({"name": name, "steps": steps}, indent=2, ensure_ascii=False))

    def load_definition(self, path: str | Path):
        """Load a pipeline definition from a JSON file."""
        data = json.loads(Path(path).read_text())
        self.define(data["name"], data["steps"])
        return data["name"]
