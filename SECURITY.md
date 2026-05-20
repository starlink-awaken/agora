# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability, please **do NOT open a public issue**.

Email the details to the maintainers. We will respond within 48 hours.

## Supported Versions

| Version | Supported |
|---------|-----------|
| 1.3.x  | Active |

## Security Design

Agora follows these security principles:

- **Local-first**: Designed for local and trusted-network service meshes. No telemetry.
- **No credential storage**: Agora does not store or proxy API keys.
- **Input validation**: Service registration validates URLs and port ranges.
- **Circuit breaker**: Automatic isolation of failing services prevents cascading failures.

## Known Limitations

- MCP server has no built-in authentication (localhost/trusted-network only by design)
- Service health checks use HTTP GET only (no mutual TLS)
- No request-level authentication between services (assumes trusted network)
