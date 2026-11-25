FROM python:3.12-slim
WORKDIR /app
COPY requirements.lock.txt .
RUN pip install --no-cache-dir -r requirements.lock.txt
COPY . .
RUN useradd -m campus && mkdir -p /data && chown -R campus:campus /app /data
USER campus
ENV DATABASE_URL=sqlite:////data/campuspath.db
EXPOSE 8000
CMD ["sh", "-c", "python -m alembic upgrade head && python -c 'from app.services.bootstrap import ensure_accounts; ensure_accounts()' && exec python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
