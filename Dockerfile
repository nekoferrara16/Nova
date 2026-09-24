FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 NOVA_DB=/data/nova.sqlite3
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd --create-home nova && mkdir /data && chown nova:nova /data
COPY main ./main
COPY static ./static
COPY templates ./templates
USER nova
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "main.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers"]
