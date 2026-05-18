FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN addgroup --system nexus \
    && adduser --system --ingroup nexus --home /app nexus

COPY requirements.txt pyproject.toml README.md ./
RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements.txt

COPY core ./core
COPY dashboard ./dashboard
COPY modules ./modules
COPY recon ./recon
COPY nexusrecon ./nexusrecon
COPY docs ./docs
COPY main.py ./main.py

RUN mkdir -p results reports .nexusrecon \
    && chown -R nexus:nexus /app

USER nexus

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/api/health', timeout=3).read()"

CMD ["python", "main.py", "--no-banner", "dashboard", "0.0.0.0:8080"]
