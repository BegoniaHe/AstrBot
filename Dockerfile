FROM python:3.14-slim
WORKDIR /AstrBot

COPY . /AstrBot/

# Enable pipefail so failures in the NodeSource curl|bash pipe abort the build.
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ENV UV_INSTALL_DIR=/usr/local/bin \
    CARGO_HOME=/usr/local/cargo \
    RUSTUP_HOME=/usr/local/rustup \
    PATH=/usr/local/cargo/bin:${PATH} \
    UV_LINK_MODE=copy

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    build-essential \
    python3-dev \
    libffi-dev \
    libssl-dev \
    ca-certificates \
    bash \
    ffmpeg \
    libavcodec-extra \
    curl \
    dnsutils \
    file \
    less \
    lsof \
    netcat-openbsd \
    openssh-client \
    procps \
    iproute2 \
    iputils-ping \
    gnupg \
    git \
    gh \
    zip \
    unzip \
    tree \
    rsync \
    sqlite3 \
    strace \
    psmisc \
    mtr-tiny \
    vim-common \
    xxd \
    ripgrep \
    fd-find \
    jq \
    bat \
    eza \
    && curl -fsSL https://deb.nodesource.com/setup_lts.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && ln -sf /usr/bin/fdfind /usr/local/bin/fd \
    && ln -sf /usr/bin/batcat /usr/local/bin/bat \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | \
    sh -s -- -y --profile minimal --default-toolchain stable \
    && cargo --version \
    && cargo install --locked \
        git-delta \
        du-dust \
        procs \
        bandwhich \
        tokei \
        hyperfine \
        sd \
        xh \
        tealdeer

RUN curl -LsSf https://astral.sh/uv/install.sh | sh \
    && uv --version \
    && echo "3.14" > .python-version \
    && uv lock \
    && uv export --format requirements.txt --output-file requirements.txt --frozen \
    && uv pip install -r requirements.txt --no-cache-dir --system \
    && uv pip install socksio pilk --no-cache-dir --system

RUN mkdir -p /etc/profile.d \
    && cat <<'EOF' >/etc/profile.d/astrbot-dev-tools.sh
export PATH=/usr/local/cargo/bin:$PATH
alias fd='fdfind'
alias bat='batcat'
EOF

EXPOSE 6185

CMD ["python", "main.py"]
