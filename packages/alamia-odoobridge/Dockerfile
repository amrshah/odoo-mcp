FROM python:3.12-slim

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy package definition and code
COPY pyproject.toml README.md /app/
COPY src/ /app/src/

# Install package
RUN pip install --no-cache-dir -e .

# Default environment
ENV MCP_TRANSPORT=sse
ENV MCP_SERVER_HOST=0.0.0.0
ENV MCP_SERVER_PORT=8008

EXPOSE 8008

ENTRYPOINT ["alamia-odoobridge"]
CMD ["--transport", "sse"]
