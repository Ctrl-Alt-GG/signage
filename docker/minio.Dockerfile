# MinIO for the Django static files and uploads. MinIO, Inc. no longer publishes community
# images, so the last community release is built from its tagged source here and the
# resulting binary runs on a plain Debian base as an unprivileged user.
ARG MINIO_RELEASE=RELEASE.2025-10-15T17-29-55Z

FROM golang:1.26-trixie AS build
ARG MINIO_RELEASE
WORKDIR /src
RUN git clone --depth 1 --branch "${MINIO_RELEASE}" https://github.com/minio/minio.git .
RUN --mount=type=cache,target=/go/pkg/mod \
    --mount=type=cache,target=/root/.cache/go-build \
    CGO_ENABLED=0 go build -trimpath -tags kqueue \
        -ldflags "$(go run buildscripts/gen-ldflags.go)" -o /out/minio .

FROM debian:trixie-slim
ARG MINIO_RELEASE

LABEL org.opencontainers.image.description="Ctrl-Alt-GG Signage object storage: MinIO ${MINIO_RELEASE} built from source."

RUN apt-get update \
    && apt-get install --yes --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10002 minio \
    && useradd --uid 10002 --gid minio --no-create-home --shell /usr/sbin/nologin minio \
    && mkdir -p /data \
    && chown 10002:10002 /data

COPY --from=build /out/minio /usr/local/bin/minio

USER 10002:10002
VOLUME ["/data"]
EXPOSE 9000 9001

ENTRYPOINT ["minio"]
CMD ["server", "/data", "--address", ":9000", "--console-address", ":9001"]
