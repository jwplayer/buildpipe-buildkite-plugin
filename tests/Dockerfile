FROM buildkite/plugin-tester
MAINTAINER Kamil Sindi <kamil@jwplayer.com>

RUN apk add --update-cache \
  python3 git docker \
  && python3 -m ensurepip \
  && rm -rf /var/cache/apk/*

COPY requirements.txt ./
RUN pip3 install --no-cache-dir -r requirements.txt

CMD ["bats", "tests/"]
