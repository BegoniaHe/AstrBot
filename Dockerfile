# syntax=docker/dockerfile:1.7
FROM python:3.14-slim
WORKDIR /AstrBot

COPY . /AstrBot/

# Enable pipefail so failures in install pipes abort the build.
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ENV UV_INSTALL_DIR=/usr/local/bin \
    CARGO_HOME=/usr/local/cargo \
    RUSTUP_HOME=/usr/local/rustup \
    NVM_DIR=/root/.nvm \
    BASH_ENV=/root/.bash_env \
    PATH=/usr/local/cargo/bin:${PATH} \
    XDG_BIN_HOME=/usr/local/bin \
    UV_LINK_MODE=copy \
    SHFMT_VERSION=3.10.0 \
    HADOLINT_VERSION=2.12.0 \
    DEBIAN_FRONTEND=noninteractive \
    APT_LISTCHANGES_FRONTEND=none

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
    printf '%s\n' \
        'Acquire::Retries "5";' \
        'Acquire::Languages "none";' \
        'APT::Install-Recommends "0";' \
        'APT::Install-Suggests "0";' \
        'Dpkg::Use-Pty "0";' \
        >/etc/apt/apt.conf.d/99astrbot \
    && install -m 0755 -d /etc/apt/keyrings \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        gnupg \
    && curl -fsSL https://download.docker.com/linux/debian/gpg \
        | gpg --dearmor -o /etc/apt/keyrings/docker.gpg \
    && chmod a+r /etc/apt/keyrings/docker.gpg \
    && . /etc/os-release \
    && echo \
        "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian ${VERSION_CODENAME} stable" \
        > /etc/apt/sources.list.d/docker.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        bash \
        bat \
        build-essential \
        cmake \
        dnsutils \
        docker-ce-cli \
        docker-compose-plugin \
        eza \
        fd-find \
        ffmpeg \
        file \
        fonts-liberation \
        fzf \
        gcc \
        gh \
        git \
        iproute2 \
        iputils-ping \
        jq \
        less \
        libavcodec-extra \
        libbz2-dev \
        libffi-dev \
        libgdbm-dev \
        libicu-dev \
        libjpeg62-turbo-dev \
        liblzma-dev \
        libmagic-dev \
        libncurses-dev \
        libpng-dev \
        libreadline-dev \
        libsqlite3-dev \
        libssl-dev \
        libxml2-dev \
        libxslt1-dev \
        lsof \
        mtr-tiny \
        netcat-openbsd \
        ninja-build \
        openssh-client \
        pkg-config \
        procps \
        psmisc \
        python3-dev \
        ripgrep \
        rsync \
        shellcheck \
        sqlite3 \
        strace \
        tree \
        unzip \
        vim-common \
        xxd \
        zip \
        zlib1g-dev \
        zsh \
    && ln -sf /usr/bin/fdfind /usr/local/bin/fd \
    && ln -sf /usr/bin/batcat /usr/local/bin/bat \
    && docker --version \
    && docker compose version \
    && rm -f /etc/apt/apt.conf.d/99astrbot

RUN touch "${BASH_ENV}" \
    && echo '. "${BASH_ENV}"' >> ~/.bashrc \
    && curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.5/install.sh | PROFILE="${BASH_ENV}" bash \
    && source "${BASH_ENV}" \
    && nvm install node \
    && nvm alias default node \
    && npm install -g corepack \
    && corepack enable \
    && corepack prepare pnpm@11.9.0 --activate \
    && current_node_dir="$(dirname "$(dirname "$(nvm which current)")")" \
    && for tool in node npm npx corepack pnpm; do \
        if [[ -x "${current_node_dir}/bin/${tool}" ]]; then \
            ln -sf "${current_node_dir}/bin/${tool}" "/usr/local/bin/${tool}"; \
        fi; \
    done \
    && node --version \
    && npm --version \
    && corepack --version

RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | \
    sh -s -- -y --profile minimal --default-toolchain stable \
    && cargo --version \
    && tmpdir="$(mktemp -d)" \
    && curl -L --proto '=https' --tlsv1.2 -sSf \
        https://github.com/cargo-bins/cargo-binstall/releases/latest/download/cargo-binstall-x86_64-unknown-linux-musl.tgz \
        | tar -C "$tmpdir" -xzf - \
    && install -m 0755 "$tmpdir/cargo-binstall" /usr/local/cargo/bin/cargo-binstall \
    && rm -rf "$tmpdir" \
    && cargo binstall --no-confirm \
        git-delta \
        du-dust \
        procs \
        tokei \
        hyperfine \
        sd \
        xh \
        tealdeer

RUN arch="$(dpkg --print-architecture)" \
    && case "${arch}" in \
        amd64) shfmt_arch="linux_amd64"; hadolint_arch="Linux-x86_64" ;; \
        arm64) shfmt_arch="linux_arm64"; hadolint_arch="Linux-arm64" ;; \
        *) echo "Unsupported architecture: ${arch}" >&2; exit 1 ;; \
    esac \
    && curl -fsSL \
        "https://github.com/mvdan/sh/releases/download/v${SHFMT_VERSION}/shfmt_v${SHFMT_VERSION}_${shfmt_arch}" \
        -o /usr/local/bin/shfmt \
    && chmod +x /usr/local/bin/shfmt \
    && curl -fsSL \
        "https://github.com/hadolint/hadolint/releases/download/v${HADOLINT_VERSION}/hadolint-${hadolint_arch}" \
        -o /usr/local/bin/hadolint \
    && chmod +x /usr/local/bin/hadolint \
    && shfmt --version \
    && hadolint --version

RUN curl -LsSf https://astral.sh/uv/install.sh | sh \
    && uv --version \
    && echo "3.14" > .python-version \
    && uv lock \
    && uv export --format requirements.txt --output-file requirements.txt --frozen \
    && uv pip install -r requirements.txt --no-cache-dir --system \
    && uv pip install socksio pilk --no-cache-dir --system \
    && uv sync --group dev --frozen

RUN arch="$(dpkg --print-architecture)" \
    && case "${arch}" in \
        amd64) powershell_arch="x64" ;; \
        arm64) powershell_arch="arm64" ;; \
        *) echo "Unsupported architecture: ${arch}" >&2; exit 1 ;; \
    esac \
    && mkdir -p /opt/microsoft/powershell/7 \
    && curl -fsSL \
        "https://github.com/PowerShell/PowerShell/releases/download/v7.5.3/powershell-7.5.3-linux-${powershell_arch}.tar.gz" \
        | tar -xz -C /opt/microsoft/powershell/7 \
    && chmod +x /opt/microsoft/powershell/7/pwsh \
    && ln -sf /opt/microsoft/powershell/7/pwsh /usr/local/bin/pwsh \
    && ln -sf /opt/microsoft/powershell/7/pwsh /usr/local/bin/powershell \
    && pwsh -NoLogo -NoProfile -Command '$PSVersionTable.PSVersion.ToString()' \
    && pwsh -NoLogo -NoProfile -Command "Set-PSRepository PSGallery -InstallationPolicy Trusted; Install-Module PSScriptAnalyzer -Scope AllUsers -Force -SkipPublisherCheck" \
    && pwsh -NoLogo -NoProfile -Command "Get-Module -ListAvailable PSScriptAnalyzer | Select-Object -First 1 Name, Version"

RUN npm ci

WORKDIR /AstrBot/dashboard
RUN pnpm install --frozen-lockfile \
    && pnpm build \
    && rm -rf /AstrBot/astrbot/dashboard/dist \
    && mkdir -p /AstrBot/astrbot/dashboard \
    && cp -r dist /AstrBot/astrbot/dashboard/

WORKDIR /AstrBot/docs
RUN rm -rf /AstrBot/docs/node_modules \
    && CI=true pnpm install --frozen-lockfile

WORKDIR /AstrBot

RUN mkdir -p /etc/profile.d \
    && cat <<'EOF' >/etc/profile.d/astrbot-dev-tools.sh
export PATH=/usr/local/cargo/bin:$PATH
export NVM_DIR=/root/.nvm
if [ -s "$NVM_DIR/nvm.sh" ]; then
  . "$NVM_DIR/nvm.sh"
fi
alias fd='fdfind'
alias bat='batcat'
if [ -S /var/run/docker.sock ]; then
  export DOCKER_HOST="${DOCKER_HOST:-unix:///var/run/docker.sock}"
fi
EOF

EXPOSE 6185

CMD ["python", "main.py"]
