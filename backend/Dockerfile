FROM python:3.11-slim@sha256:b7a9e5f6a93d6d4a31f129bbd4bdee69efccb6ded0fb230d78aafaf37af98377

WORKDIR /app

COPY requirements.txt build-requirements.txt requirements.lock ./

RUN python -m pip install --no-cache-dir --require-hashes --only-binary=:all: -r requirements.lock \
    && python -m pip check \
    && python -m pip uninstall --yes pip

COPY . .

EXPOSE 8443

CMD ["python", "-m", "deployment.serve"]
