FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    ANTLR_JAR=/opt/antlr-4.13.2-complete.jar

RUN apt-get update && apt-get install --yes --no-install-recommends \
        ca-certificates openjdk-17-jre-headless git make \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY experiments/api_load_test/requirements.lock /tmp/requirements.lock
RUN python -m pip install --no-cache-dir -r /tmp/requirements.lock
RUN python -c "import hashlib, urllib.request; from pathlib import Path; data=urllib.request.urlopen('https://www.antlr.org/download/antlr-4.13.2-complete.jar', timeout=60).read(); assert hashlib.sha256(data).hexdigest() == 'eae2dfa119a64327444672aff63e9ec35a20180dc5b8090b7a6ab85125df4d76'; Path('/opt/antlr-4.13.2-complete.jar').write_bytes(data)"

COPY . /app
RUN python -m pip install --no-deps --no-build-isolation -e '.[dev]' \
    && python -m build --no-isolation \
    && useradd --create-home --uid 10001 experiment \
    && chown -R experiment:experiment /app

USER experiment
CMD ["sh", "-c", "make check && python -m experiments.api_load_test self-check --output /tmp/api-self-check"]
