FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    fastapi==0.115.0 \
    uvicorn[standard]==0.30.6 \
    pyyaml==6.0.2 \
    pydantic==2.9.2 \
    requests==2.32.3

COPY app/ .
COPY locales/ /locales/

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
