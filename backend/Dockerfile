FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt build-requirements.txt requirements.lock ./

RUN python -m pip install --no-cache-dir --require-hashes --only-binary=:all: -r requirements.lock \
    && python -m pip check

COPY . .

EXPOSE 8443

CMD ["python", "-m", "deployment.serve"]
