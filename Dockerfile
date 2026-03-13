FROM python:3.12-slim

WORKDIR /app

# Install dependencies first for layer caching
COPY pyproject.toml ./
COPY src/ ./src/

RUN pip install --no-cache-dir .

# Cloud Run injects PORT; MCP_BASE_URL must be set to the service's public URL
ENV PORT=8080
ENV MCP_BASE_URL=""

EXPOSE 8080

CMD ["python", "-m", "gsc_mcp_oauth"]
