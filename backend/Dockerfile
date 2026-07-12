# SwimStats Chile — backend API and pipeline
FROM python:3.12-slim

WORKDIR /app

# System deps for pdfplumber / image backends if needed later
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

# Default: API only. Override CMD for one-off pipeline scripts.
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
