FROM python:3.8-alpine
MAINTAINER Kamil Sindi <kamil@jwplayer.com>

WORKDIR "/buildkite"

COPY requirements.txt ./
RUN pip3 install --no-cache-dir -r requirements.txt

CMD ["python3", "buildpipe"]
