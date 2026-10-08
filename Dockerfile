FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATA_DIR=/data

WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY scripts ./scripts

RUN useradd --system --uid 10001 defter && mkdir /data && chown defter /data
USER defter
VOLUME /data
EXPOSE 8000

# Tek süreç: hatırlatma döngüsü ve giriş sınırlayıcı süreç içinde çalışır.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
