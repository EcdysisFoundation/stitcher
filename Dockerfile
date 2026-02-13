FROM docker.io/python:3.12-slim AS python

# Create generic non-root user (1000:1000) EARLY
RUN groupadd --gid 1000 appgroup && \
    useradd --uid 1000 --gid appgroup --shell /bin/bash --create-home appuser

RUN apt-get update && apt-get install -y gosu && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /data /logs /code\
    && chown -R appuser:appgroup /data /logs /code

RUN python -m pip install --upgrade pip

WORKDIR /code

COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade -r requirements.txt


COPY --chown=appuser:appgroup ./start-celeryworker /start-celeryworker
COPY --chown=appuser:appgroup ./start-flower /start-flower
COPY --chown=appuser:appgroup ./entrypoint.sh /entrypoint.sh
RUN chmod +x /start-celeryworker /start-flower /entrypoint.sh

# Switch to non-root user
USER appuser

