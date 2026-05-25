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

COPY backend/main.py ./main.py
COPY backend/tasks.py ./tasks.py
COPY backend/recon_validators.py ./recon_validators.py
COPY backend/__init__.py ./backend/__init__.py
COPY backend/artifact_classifier.py ./backend/artifact_classifier.py
COPY backend/queues.py ./backend/queues.py
COPY backend/modules ./backend/modules
COPY backend/osint ./backend/osint
COPY backend/investigator ./backend/investigator
COPY backend/playbooks ./backend/playbooks
COPY core ./core
COPY modules ./modules
COPY nexusrecon ./nexusrecon
COPY recon ./recon

RUN chown -R nexus:nexus /srv/nexusintel
USER nexus

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
