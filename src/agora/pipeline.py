"""Pipeline Orchestrator — chain multiple MCP tool calls into a workflow.

Usage:
    pipeline = Pipeline(registry, router)
    # Sequential
    result = await pipeline.run("full-pipeline", {"goal": "...", "project": "."})
    # Streaming (yield each step)
    async for step in pipeline.run_stream("full-pipeline", {"goal": "...", "project": "."}):
        print(step)
    # Parallel (independent steps)
    result = await pipeline.run_parallel("full-pipeline", {"goal": "...", "project": "."})
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class Pipeline:
    """Defines and executes multi-step MCP tool call pipelines.

    Supports three execution modes:
    - Sequential (run): each step waits for the previous
    - Streaming (run_stream): yield each step as it completes
    - Parallel (run_parallel): independent steps execute concurrently
    """

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
        """Execute a named pipeline sequentially."""
        results = []
        async for step in self.run_stream(name, variables):
            results.append(step)
        return {
            "pipeline": name,
            "variables": variables,
            "results": results,
            "outputs": {r["tool"]: r.get("output", "")[:200] for r in results if r["status"] == "ok"},
        }

    async def run_stream(self, name: str, variables: dict[str, Any]) -> AsyncIterator[dict]:
        """Execute pipeline and yield each step as it completes (streaming)."""
        steps = self._definitions.get(name)
        if not steps:
            yield {"status": "error", "error": f"Pipeline not found: {name}"}
            return

        outputs: dict[str, Any] = {}

        for i, step in enumerate(steps):
            tool_name = step["tool"]
            args = self._render_args(step.get("args", {}), variables, outputs)
            label = step.get("output_as", f"step_{i}")

            logger.info("pipeline_step", pipeline=name, step=i, tool=tool_name)

            try:
                result = await self.router.route(tool_name, args)
                outputs[label] = result
                yield {"step": i, "tool": tool_name, "status": "ok", "output": str(result)[:200]}
            except Exception as e:
                logger.error("pipeline_step_failed", pipeline=name, step=i, error=str(e))
                yield {"step": i, "tool": tool_name, "status": "error", "error": str(e)}
                if step.get("critical", False):
                    break

    async def run_parallel(self, name: str, variables: dict[str, Any]) -> dict[str, Any]:
        """Execute independent pipeline steps in parallel.

        Groups steps by dependency level — each level runs concurrently.
        Steps within a level that have no inter-dependencies execute in parallel.
        """
        steps = self._definitions.get(name)
        if not steps:
            return {"status": "error", "error": f"Pipeline not found: {name}"}

        outputs: dict[str, Any] = {}

        # Group steps by whether they have unmet dependencies
        remaining = list(enumerate(steps))
        results = []

        while remaining:
            # Find steps with all dependencies met
            ready = []
            still_waiting = []
            for i, step in remaining:
                deps = step.get("depends_on", [])
                if all(d in outputs for d in deps):
                    ready.append((i, step))
                else:
                    still_waiting.append((i, step))

            if not ready and still_waiting:
                # Deadlock: remaining steps have unresolvable deps
                for i, step in still_waiting:
                    results.append({"step": i, "tool": step["tool"], "status": "error",
                                    "error": "Unresolved dependency"})
                break

            # Execute ready steps in parallel
            async def _exec(i, step):
                tool_name = step["tool"]
                args = self._render_args(step.get("args", {}), variables, outputs)
                label = step.get("output_as", f"step_{i}")
                try:
                    result = await self.router.route(tool_name, args)
                    return i, label, result, None
                except Exception as e:
                    return i, label, None, str(e)

            tasks = [_exec(i, step) for i, step in ready]
            batch_results = await asyncio.gather(*tasks)

            critical_failed = False
            for i, label, result, error in batch_results:
                step = steps[i]
                if error:
                    results.append({"step": i, "tool": step["tool"], "status": "error", "error": error})
                    if step.get("critical", False):
                        critical_failed = True
                        break
                else:
                    outputs[label] = result
                    results.append({"step": i, "tool": step["tool"], "status": "ok"})

            remaining = [] if critical_failed else still_waiting

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
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"name": name, "steps": steps}, indent=2, ensure_ascii=False))

    def load_definition(self, path: str | Path):
        """Load a pipeline definition from a JSON file."""
        data = json.loads(Path(path).read_text())
        self.define(data["name"], data["steps"])
        return data["name"]
