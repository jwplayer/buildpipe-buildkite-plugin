FROM buildkite/plugin-tester
MAINTAINER Kamil Sindi <kamil@jwplayer.com>

RUN apk add --update-cache \
  python3 git \
  && python3 -m ensurepip \
  && rm -rf /var/cache/apk/*

COPY . .

CMD ["bats", "tests/"]
