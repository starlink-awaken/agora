"""MCP Tool Market — discover, install, and register third-party MCP services.

Usage:
    agora market list                          # List available MCP services
    agora market search "filesystem"           # Search by keyword
    agora market install starlink-awaken/minerva  # Install from GitHub
    agora market install <url> --name custom   # Install from any URL
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlparse


# Built-in MCP service registry
BUILTIN_MARKET: dict[str, dict] = {
    "minerva": {
        "name": "minerva",
        "description": "Local-first deep research system — web + academic + code search",
        "repo": "starlink-awaken/minerva",
        "type": "python",
        "entry": "mcp_server.py",
        "tags": ["research", "llm", "knowledge"],
        "port": 8765,
    },
    "ontoderive": {
        "name": "ontoderive",
        "description": "Fact-driven derivation engine — ToolForge + consistency check",
        "repo": "starlink-awaken/ontoderive",
        "type": "python",
        "entry": "engine/mcp-server.py",
        "tags": ["knowledge", "ontology", "derivation"],
        "port": 0,
    },
    "sophia": {
        "name": "sophia",
        "description": "Symbolic research paradigm compiler — state machine formalism",
        "repo": "starlink-awaken/sophia",
        "type": "python",
        "entry": "cli.py",
        "tags": ["paradigm", "compiler", "state-machine"],
        "port": 0,
    },
    "kos": {
        "name": "kos",
        "description": "Knowledge OS — cross-domain semantic search + entity graph",
        "repo": "starlink-awaken/kos",
        "type": "python",
        "entry": "kos-mcp-server.py",
        "tags": ["knowledge", "search", "graph"],
        "port": 0,
    },
    "filesystem": {
        "name": "filesystem",
        "description": "Local filesystem MCP — read, write, search, patch files",
        "repo": "modelcontextprotocol/servers",
        "subdir": "src/filesystem",
        "type": "node",
        "entry": "dist/index.js",
        "tags": ["filesystem", "local"],
        "port": 0,
    },
    "fetch": {
        "name": "fetch",
        "description": "HTTP fetch MCP — web scraping and API calls",
        "repo": "modelcontextprotocol/servers",
        "subdir": "src/fetch",
        "type": "node",
        "entry": "dist/index.js",
        "tags": ["web", "http", "scraping"],
        "port": 0,
    },
    "puppeteer": {
        "name": "puppeteer",
        "description": "Browser automation MCP — headless Chrome control",
        "repo": "modelcontextprotocol/servers",
        "subdir": "src/puppeteer",
        "type": "node",
        "entry": "dist/index.js",
        "tags": ["browser", "automation", "scraping"],
        "port": 0,
    },
    "github": {
        "name": "github",
        "description": "GitHub API MCP — issues, PRs, repos, code review",
        "repo": "modelcontextprotocol/servers",
        "subdir": "src/github",
        "type": "node",
        "entry": "dist/index.js",
        "tags": ["github", "git", "code-review"],
        "port": 0,
    },
    "sequential-thinking": {
        "name": "sequential-thinking",
        "description": "Sequential thinking MCP — structured reasoning steps",
        "repo": "modelcontextprotocol/servers",
        "subdir": "src/sequentialthinking",
        "type": "node",
        "entry": "dist/index.js",
        "tags": ["reasoning", "thinking"],
        "port": 0,
    },
    "brave-search": {
        "name": "brave-search",
        "description": "Brave Search MCP — web and local search API",
        "repo": "modelcontextprotocol/servers",
        "subdir": "src/brave-search",
        "type": "node",
        "entry": "dist/index.js",
        "tags": ["search", "web"],
        "port": 0,
    },
}


class Market:
    """MCP tool marketplace — discover, install, and register services."""

    INSTALL_DIR = Path.home() / ".agora" / "market"

    def search(self, query: str) -> list[dict]:
        """Search the built-in market by keyword."""
        q = query.lower()
        results = []
        for info in BUILTIN_MARKET.values():
            if (q in info["name"].lower()
                or q in info["description"].lower()
                or any(q in t.lower() for t in info.get("tags", []))):
                results.append(info)
        return results

    def list_all(self) -> list[dict]:
        """List all available MCP services in the market."""
        return list(BUILTIN_MARKET.values())

    def install(self, name_or_url: str) -> dict:
        """Install an MCP service from the built-in market or GitHub URL.

        Returns metadata for registration.
        """
        # Check built-in market first
        if name_or_url in BUILTIN_MARKET:
            info = BUILTIN_MARKET[name_or_url]
            repo = info["repo"]
            subdir = info.get("subdir", "")
        else:
            # Treat as GitHub repo URL or shorthand
            repo = name_or_url.replace("https://github.com/", "").rstrip("/")
            # Look for metadata
            info = self._fetch_repo_metadata(repo)
            subdir = ""

        install_path = self.INSTALL_DIR / repo.replace("/", "__")
        if not install_path.exists():
            # Clone repo
            url = f"https://github.com/{repo}.git"
            self._run_cmd(["git", "clone", "--depth", "1", url, str(install_path)])

        # Build / install based on type
        svc_type = info.get("type", "python")
        entry_path = install_path
        if subdir:
            entry_path = install_path / subdir

        if svc_type == "node":
            self._run_cmd(["npm", "install", "--production"], cwd=str(entry_path))
        elif svc_type == "python":
            pip = Path(sys.prefix) / "bin" / "pip"
            if not pip.exists():
                pip = Path(sys.prefix) / "bin" / "pip3"
            self._run_cmd([str(pip), "install", "-e", "."], cwd=str(entry_path))

        return {
            "name": info["name"],
            "description": info["description"],
            "entry": str(entry_path / info["entry"]),
            "type": svc_type,
            "port": info.get("port", 0),
            "tags": info.get("tags", []),
        }

    def _fetch_repo_metadata(self, repo: str) -> dict:
        """Fetch repo metadata from GitHub API."""
        import httpx
        try:
            r = httpx.get(f"https://api.github.com/repos/{repo}", timeout=10)
            if r.status_code == 200:
                data = r.json()
                return {
                    "name": data.get("name", repo.split("/")[-1]),
                    "description": data.get("description", ""),
                    "type": "python",  # default
                    "entry": "server.py",
                    "tags": ["github", "mcp"],
                }
        except Exception:
            pass
        return {"name": repo.split("/")[-1], "description": "", "type": "python", "entry": "server.py", "tags": []}

    @staticmethod
    def _run_cmd(cmd: list[str], cwd: str | None = None):
        """Run a shell command, raise on failure."""
        result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{result.stderr[:500]}")
