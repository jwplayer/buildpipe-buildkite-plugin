FROM python:3.7-slim

RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y git

WORKDIR "/buildkite"

COPY setup.py ./
RUN pip install --no-cache-dir -e .

CMD ["buildpipe", "-i", "foo"]
