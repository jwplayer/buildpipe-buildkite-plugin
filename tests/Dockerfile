FROM buildkite/plugin-tester
MAINTAINER Kamil Sindi <https://github.com/ksindi>

RUN apk add --update-cache \
  python3 git \
  && python3 -m ensurepip \
  && rm -rf /var/cache/apk/*

RUN pip3 install ruamel.yaml>=0.16.10 jsonschema>=3.2.0

COPY . .

CMD ["bats", "tests/"]
