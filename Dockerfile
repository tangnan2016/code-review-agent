# ============================================================
#  Code Review Agent - Dockerfile
# ============================================================
FROM python:3.11-slim

WORKDIR /app

# 系统依赖（git 用于远程仓库 clone）
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

# 先装依赖，利用层缓存
# 支持离线安装：若构建时已将 `pip download` 产物放入 packages/ 目录，
# 则优先从本地安装（无需联网）；否则回退到在线安装。
COPY requirements.txt .
COPY packages* /tmp/packages/
RUN if [ -n "$(ls /tmp/packages/ 2>/dev/null)" ]; then \
      pip install --no-cache-dir --no-index --find-links=/tmp/packages -r requirements.txt; \
    else \
      pip install --no-cache-dir -r requirements.txt; \
    fi \
    && rm -rf /tmp/packages

# 拷贝项目代码
COPY . .

# 运行时目录（报告输出、挂载代码用）
RUN mkdir -p /app/output /workspace

# 默认以 MCP HTTP/SSE 模式启动，对外暴露 8080
EXPOSE 8080

ENTRYPOINT ["python", "mcp_server.py"]
CMD ["--transport", "sse", "--host", "0.0.0.0", "--port", "8080"]