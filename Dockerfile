# Agora — MCP Service Convergence Hub
# docker build -t starlink-awaken/agora:1.2 .
# docker run -p 7430:7430 starlink-awaken/agora:1.2

FROM python:3.13-slim AS builder
WORKDIR /app
COPY pyproject.toml .
COPY src/ src/
RUN pip install --no-cache-dir -e . && rm -rf ~/.cache/pip

FROM python:3.13-slim
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin/agora /usr/local/bin/agora
COPY --from=builder /usr/local/bin/agora-mcp /usr/local/bin/agora-mcp
COPY --from=builder /usr/local/bin/agora-web /usr/local/bin/agora-web
COPY src/agora/web/dashboard.html src/agora/web/dashboard.html
COPY README.md .

ENV AGORA_API_KEY=""
EXPOSE 7430
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:7430/api/health')"
CMD ["agora", "web"]
