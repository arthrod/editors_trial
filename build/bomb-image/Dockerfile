FROM debian:bookworm-slim
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 libreoffice-writer \
 && rm -rf /var/lib/apt/lists/*
