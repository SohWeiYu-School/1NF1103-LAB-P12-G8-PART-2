FROM python:3.12-slim

WORKDIR /app

# Install dependencies first so this layer is cached separately from code changes
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Create runtime directories and assign ownership before switching to non-root user
RUN mkdir -p /app/data/cache /app/data/"local database" /app/logs \
    && useradd --create-home --shell /bin/sh appuser \
    && chown -R appuser:appuser /app/data /app/logs

USER appuser

# The web app; set HOST so it can be reached from outside the container
ENV HOST=0.0.0.0 PORT=5000
EXPOSE 5000
CMD ["python", "main.py", "--web"]
