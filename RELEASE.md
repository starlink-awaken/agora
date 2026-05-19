# Agora Release Guide

## PyPI 发布

```bash
# 1. 打 tag
git tag v1.2.0
git push origin v1.2.0

# 2. CI 自动构建 + 发布到 PyPI
# → .github/workflows/publish.yml 触发
# → 需要设置 GitHub Secrets: PYPI_API_TOKEN

# 3. 用户安装
pip install agora-mcp
```

## Homebrew (计划中)

```bash
brew install starlink-awaken/tap/agora
```

## Docker 发布

```bash
docker build -t starlink-awaken/agora:1.2 .
docker push starlink-awaken/agora:1.2
```
