FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (cached layer if requirements unchanged)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code and exported projections
COPY src/ src/
COPY export/ export/

# Non-root user for security
RUN useradd --create-home appuser
USER appuser

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
