"""Auto-discovery engine — scan workspace for MCP-capable services."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agora.registry import ServiceRegistry


@dataclass
class DiscoveredService:
    name: str
    description: str = ""
    mcp_endpoint: str = ""
    health_endpoint: str = ""
    port: int = 0
    tags: list[str] = field(default_factory=list)
    source: str = ""
    confidence: float = 1.0


class DiscoveryEngine:
    """Auto-discover MCP services in the workspace.

    Uses fast static analysis — reads pyproject.toml metadata,
    no subprocess calls needed.
    """

    # Known MCP-capable projects with extended metadata
    KNOWN_PROJECTS: dict[str, dict] = {
        "minerva": {
            "description": "Local-first deep research system — 5 Super Tools (Dropbox Dash pattern)",
            "mcp_endpoint": "stdio://minerva",
            "health_port": 8765,
            "tags": ["research", "knowledge", "llm"],
        },
        "ontoderive": {
            "description": "Fact-driven knowledge engineering — ToolForge + derive + check",
            "mcp_endpoint": "stdio://ontoderive",
            "health_port": 0,
            "tags": ["knowledge-engineering", "derivation", "ontology"],
        },
        "sophia": {
            "description": "Symbolic research paradigm compiler — state machine formalism",
            "mcp_endpoint": "stdio://sophia",
            "health_port": 0,
            "tags": ["paradigm", "compiler", "state-machine"],
        },
        "agora": {
            "description": "MCP service convergence hub — registry, routing, pipeline",
            "mcp_endpoint": "stdio://agora",
            "health_port": 0,
            "tags": ["gateway", "registry", "pipeline"],
        },
        "agentmesh": {
            "description": "Multi-agent gateway scheduler — unified agent orchestration",
            "mcp_endpoint": "",
            "health_port": 3000,
            "tags": ["agent", "gateway", "scheduler"],
        },
        "honeycomb": {
            "description": "Multi-agent collaboration engine — DSL compiler + agent pool",
            "mcp_endpoint": "",
            "health_port": 0,
            "tags": ["agent", "dsl", "collaboration"],
        },
        "bos-skill-cli": {
            "description": "Skill discovery and staged activation CLI",
            "mcp_endpoint": "",
            "health_port": 0,
            "tags": ["skill", "discovery", "cli"],
        },
    }

    def __init__(self, workspace_root: str | None = None):
        self.root = Path(workspace_root or self._find_workspace())

    @staticmethod
    def _find_workspace() -> str:
        cwd = Path.cwd()
        for ancestor in [cwd] + list(cwd.parents):
            if (ancestor / "agora").is_dir() and (ancestor / "minerva").is_dir():
                return str(ancestor)
        return str(cwd)

    def scan_known_projects(self) -> list[DiscoveredService]:
        """Scan for known projects with .venv confirmation."""
        found = []
        for proj_name, info in self.KNOWN_PROJECTS.items():
            proj_dir = self.root / proj_name
            if not proj_dir.is_dir():
                continue
            venv_bin = proj_dir / ".venv" / "bin"
            if not venv_bin.is_dir():
                continue

            service = DiscoveredService(
                name=proj_name,
                description=info.get("description", proj_name),
                mcp_endpoint=info.get("mcp_endpoint", ""),
                health_endpoint=f"http://localhost:{info['health_port']}/health" if info.get("health_port") else "",
                port=info.get("health_port", 0),
                tags=info.get("tags", []),
                source=f"known-project:{proj_dir}",
                confidence=0.85,
            )
            found.append(service)
        return found

    def scan_pyproject_scripts(self) -> list[DiscoveredService]:
        """Scan pyproject.toml for MCP-related project.scripts entries."""
        found = []
        for project_dir in self.root.iterdir():
            if not project_dir.is_dir() or project_dir.name.startswith("."):
                continue
            pyproject = project_dir / "pyproject.toml"
            if not pyproject.exists():
                continue
            try:
                data = tomllib.loads(pyproject.read_text())
            except Exception:
                try:
                    content = pyproject.read_text()
                except Exception:
                    continue
                if "mcp" not in content.lower() and "fastmcp" not in content.lower():
                    continue
                name = project_dir.name
                found.append(DiscoveredService(
                    name=name,
                    description=f"MCP project: {name}",
                    source=f"pyproject:{pyproject}",
                    confidence=0.65,
                ))
                continue

            scripts = data.get("project", {}).get("scripts", {})
            if not scripts:
                continue

            # Check if any script has mcp-related name or value
            has_mcp = any("mcp" in k.lower() or "mcp" in str(v).lower() for k, v in scripts.items())
            # Also check dependencies for fastmcp
            deps = data.get("project", {}).get("dependencies", [])
            has_fastmcp = any("fastmcp" in str(d).lower() for d in deps)

            if has_mcp or has_fastmcp:
                name = data.get("project", {}).get("name", project_dir.name)
                desc = data.get("project", {}).get("description", "")
                found.append(DiscoveredService(
                    name=name,
                    description=desc or f"MCP service: {name}",
                    mcp_endpoint=f"stdio://{name}" if has_mcp else "",
                    source=f"pyproject:{pyproject}",
                    confidence=0.75 if has_mcp else 0.60,
                    tags=data.get("project", {}).get("keywords", []),
                ))
        return found

    def discover_all(self) -> list[DiscoveredService]:
        """Run all discovery strategies and deduplicate by confidence."""
        all_found: dict[str, DiscoveredService] = {}

        for svc in self.scan_known_projects():
            all_found[svc.name] = svc

        for svc in self.scan_pyproject_scripts():
            if svc.name not in all_found:
                all_found[svc.name] = svc

        return sorted(all_found.values(), key=lambda s: s.confidence, reverse=True)

    def auto_register(self, registry: "ServiceRegistry") -> int:
        """Discover and auto-register new services. Returns count registered."""
        from agora.registry import Service

        count = 0
        for svc in self.discover_all():
            if svc.name not in {s.name for s in registry.list_all()}:
                registry.register(Service(
                    name=svc.name,
                    description=svc.description,
                    mcp_endpoint=svc.mcp_endpoint,
                    health_endpoint=svc.health_endpoint,
                    port=svc.port,
                    tags=svc.tags,
                ))
                count += 1
        return count
