FROM golang:1.14 as builder

WORKDIR /go/src/github.com/jwplayer/buildpipe-buildkite-plugin/

COPY .	.

RUN make clean
RUN make build-linux

FROM buildkite/plugin-tester:v1.1.0

COPY .	.

COPY --from=builder /go/src/github.com/jwplayer/buildpipe-buildkite-plugin/buildpipe-linux buildpipe

CMD ["bats", "tests/"]
