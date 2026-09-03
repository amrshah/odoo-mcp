FROM python:3.12-slim

WORKDIR /app

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY odoo_client.py .
COPY server.py .

# Environment defaults
ENV PYTHONUNBUFFERED=1
ENV MCP_TRANSPORT=sse
ENV MCP_SERVER_HOST=0.0.0.0
ENV MCP_SERVER_PORT=8008

EXPOSE 8008

CMD ["python", "server.py", "--sse"]
