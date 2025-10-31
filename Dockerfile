# syntax=docker/dockerfile:1
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY AI_Agentic_World/my_first_proj/my_first_proj/requirements.txt ./requirements.txt
RUN pip install -r requirements.txt

# Copy project
COPY AI_Agentic_World/my_first_proj/my_first_proj /app

EXPOSE 8000

# Default creds for dashboard (override in env)
ENV DASH_USER=admin DASH_PASS=admin

CMD ["uvicorn", "webapp.app:app", "--host", "0.0.0.0", "--port", "8000"]
