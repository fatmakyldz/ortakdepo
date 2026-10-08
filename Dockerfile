FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATA_DIR=/data

WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY scripts ./scripts

RUN useradd --system --uid 10001 --no-create-home defter && mkdir /data && chown defter /data
EXPOSE 8000

# Betik root olarak başlar, veri klasörünü "defter" kullanıcısına verir ve yetkiyi bırakır.
# Tek süreç: hatırlatma döngüsü ve giriş sınırlayıcı süreç içinde çalışır.
CMD ["python", "scripts/baslat.py"]
