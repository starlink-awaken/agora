"""Agora — MCP Service Convergence Hub.

Routes, monitors, and governs communication between MCP-based services.
Single-registry hub-spoke topology: every service knows only Agora; Agora
knows every service.
"""
__version__ = "1.2.0"
"""
Agora — MCP 服务融合 Hub。

跨项目桥接:
- agora → sophia: 共享 MCP 生态，paradigm 编译可复用
- agora → minerva: 共享 fastmcp 基础设施
- agora → pallas: pallas 通过 subprocess 调用 agora CLI
"""
