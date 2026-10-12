# The notifier: watches the hub's events and sends a Signal message about changed
# files. signal-cli is baked into the image, its state (the linked account) is
# mounted from ../signal-state, like in 35services/3d-printing-simple-filament-tool.

# signal-cli needs a JRE newer than Debian ships, so take it from eclipse-temurin
FROM eclipse-temurin:25-jre AS java

FROM python:3.13-slim

ENV SIGNAL_CLI_VERSION=0.14.8
# libsignal-client version bundled in signal-cli's lib/libsignal-client-<version>.jar.
# Check that filename when bumping SIGNAL_CLI_VERSION, and update this to match.
ENV LIBSIGNAL_VERSION=0.102.1
ENV JAVA_HOME=/opt/java/openjdk
ENV PATH="${JAVA_HOME}/bin:${PATH}"
# without a UTF-8 locale, Java passes umlauts in file names to Signal mangled
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
ENV PYTHONUNBUFFERED=1

COPY --from=java /opt/java/openjdk /opt/java/openjdk

# signal-cli only bundles libsignal's native library for amd64, so on arm64 (e.g. a
# Mac with Apple silicon) it comes from exquo/signal-libs-build.
# qrencode shows the link code as a QR code in the terminal.
RUN apt-get update && \
    apt-get install -y --no-install-recommends wget ca-certificates qrencode && \
    wget -q "https://github.com/AsamK/signal-cli/releases/download/v${SIGNAL_CLI_VERSION}/signal-cli-${SIGNAL_CLI_VERSION}.tar.gz" && \
    tar xf "signal-cli-${SIGNAL_CLI_VERSION}.tar.gz" -C /opt && \
    rm "signal-cli-${SIGNAL_CLI_VERSION}.tar.gz" && \
    ln -sf "/opt/signal-cli-${SIGNAL_CLI_VERSION}/bin/signal-cli" /usr/local/bin/ && \
    ARCH=$(dpkg --print-architecture) && \
    if [ "$ARCH" != "amd64" ]; then \
        case "$ARCH" in \
            arm64) RUST_TARGET=aarch64-unknown-linux-gnu ;; \
            armhf) RUST_TARGET=armv7-unknown-linux-gnueabihf ;; \
            *) echo "No known libsignal native lib for architecture: $ARCH" >&2 && exit 1 ;; \
        esac && \
        wget -q "https://github.com/exquo/signal-libs-build/releases/download/libsignal_v${LIBSIGNAL_VERSION}/libsignal_jni.so-v${LIBSIGNAL_VERSION}-${RUST_TARGET}.tar.gz" && \
        tar xzf "libsignal_jni.so-v${LIBSIGNAL_VERSION}-${RUST_TARGET}.tar.gz" -C /usr/lib && \
        rm "libsignal_jni.so-v${LIBSIGNAL_VERSION}-${RUST_TARGET}.tar.gz"; \
    fi && \
    rm -rf /var/lib/apt/lists/*

COPY notifier.py /usr/local/bin/notifier.py

CMD ["python3", "/usr/local/bin/notifier.py"]
