FROM python:3.11-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.11-slim AS runtime
WORKDIR /app
# site-packages + binary'ler (/usr/local/bin -> uvicorn, gunicorn vb.)
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY . .
ENV PORT=8080
ENV PYTHONUNBUFFERED=1
EXPOSE 8080
# Non-root çalıştır — container breach durumunda ayrıcalık yükseltmeyi engeller.
USER 1000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]