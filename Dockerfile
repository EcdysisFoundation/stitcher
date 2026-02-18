FROM docker.io/python:3.12-slim AS python

RUN apt-get update && apt-get install -y gosu && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /sqlite_data /logs /code

RUN python -m pip install --upgrade pip

# Create non-root user
RUN groupadd --gid 1000 appgroup && \
    useradd --uid 1000 --gid appgroup --shell /bin/bash --create-home appuser && \
    chown -R appuser:appgroup /sqlite_data /logs /code

WORKDIR /code

COPY requirements.txt .
COPY common.env .

RUN pip install --no-cache-dir --upgrade -r requirements.txt


COPY --chown=appuser:appgroup ./start-celeryworker /start-celeryworker
COPY --chown=appuser:appgroup ./start-flower /start-flower
RUN chmod +x /start-celeryworker /start-flower

# Switch to non-root user for runtime
USER appuser
