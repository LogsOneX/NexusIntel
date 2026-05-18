FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv/nexusintel

RUN addgroup --system nexus \
    && adduser --system --ingroup nexus --home /srv/nexusintel nexus

COPY backend/requirements.txt ./
RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements.txt

COPY backend/app ./app
COPY backend/workers ./workers
COPY core ./core
COPY modules ./modules
COPY nexusrecon ./nexusrecon
COPY recon ./recon

RUN chown -R nexus:nexus /srv/nexusintel
USER nexus

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
