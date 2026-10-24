FROM postgres:16-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-venv \
    && rm -rf /var/lib/apt/lists/*
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/app
WORKDIR /app
COPY backend/requirements.txt backend/build-requirements.txt backend/requirements.lock /app/
RUN python -m pip install --no-cache-dir --require-hashes --only-binary=:all: -r requirements.lock \
    && python -m pip check
COPY backend/ /app/
COPY tests/p0/ /tests/
ENTRYPOINT []
CMD ["pytest", "-c", "/tests/pytest.ini", "/tests", "--tb=short", "-ra", "--junitxml=/results/junit.xml"]
