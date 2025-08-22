# Dev image for Django
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System deps often needed in Django dev (psycopg2, Pillow, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev netcat-traditional curl \
 && rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN pip install --upgrade pip

# --- Install Python deps (cache-friendly) ---
# Base/runtime deps (optional if you put everything in requirements-dev.txt)
COPY requirements.txt /tmp/requirements.txt
RUN if [ -f /tmp/requirements.txt ]; then pip install -r /tmp/requirements.txt; fi

# Dev-only deps (pytest, debug toolbar, etc.)
COPY requirements-dev.txt /tmp/requirements-dev.txt
RUN if [ -f /tmp/requirements-dev.txt ]; then pip install -r /tmp/requirements-dev.txt; fi

# Optional lightweight entrypoint to wait for DB + migrate in dev
COPY docker-entrypoint.dev.sh /usr/local/bin/docker-entrypoint.dev.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.dev.sh

EXPOSE 8000

# Use entrypoint so compose can still override CMD if needed
ENTRYPOINT ["docker-entrypoint.dev.sh"]
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
