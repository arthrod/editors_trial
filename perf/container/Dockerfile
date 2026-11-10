# Registry OCI index resolved 2026-11-10; linux/amd64 manifest.
FROM mcr.microsoft.com/playwright:v1.64.1-noble@sha256:ee15712262f017b8157421b212b12099146645f44b1bc5c0514cbbe6a229b1d0
RUN apt-get update \
 && apt-get install -y --no-install-recommends git git-lfs curl ca-certificates procps bash python3.12 python3-venv build-essential pkg-config libssl-dev unzip \
 && rm -rf /var/lib/apt/lists/* \
 && npm install -g pnpm@10
RUN usermod -l user -d /home/user -m ubuntu \
 && groupmod -n user ubuntu \
 && mkdir -p /app /data \
 && chown -R 1000:1000 /app /data /home/user
USER 1000
ENV HOME=/home/user PATH=/home/user/.local/bin:/home/user/.cargo/bin:/home/user/.bun/bin:$PATH PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN curl -fsSL https://sh.rustup.rs | sh -s -- -y --profile minimal --default-toolchain stable \
 && rustup target add wasm32-unknown-unknown \
 && cargo install --locked trunk \
 && curl -LsSf https://astral.sh/uv/install.sh | sh \
 && curl -fsSL https://bun.sh/install | bash
# Python runtime dependencies are installed before any measured session.
RUN python3 -m venv /home/user/python-runtime \
 && /home/user/python-runtime/bin/pip install --no-cache-dir playwright==1.64.1 psutil==7.2.2
ENV PATH=/home/user/python-runtime/bin:$PATH
WORKDIR /app
EXPOSE 7860
CMD ["python3", "-m", "http.server", "7860", "--directory", "/app"]
