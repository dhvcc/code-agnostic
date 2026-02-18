FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app
COPY pyproject.toml ./
COPY code_agnostic/ code_agnostic/

RUN uv pip install --system .

# Config lives here at runtime
ENV XDG_CONFIG_HOME=/root/.config
RUN mkdir -p /root/.config/code-agnostic/config \
    && echo '{"mcpServers":{}}' > /root/.config/code-agnostic/config/mcp.base.json

ENTRYPOINT ["code-agnostic"]
CMD ["--help"]
