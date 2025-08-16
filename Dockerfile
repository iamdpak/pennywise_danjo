FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml ./
RUN pip install --no-cache-dir -U pip && \
    pip install --no-cache-dir -e .
COPY . .
CMD ["bash", "-lc", "python manage.py migrate && gunicorn pennywise_api.wsgi:application --bind 0.0.0.0:8000"]
