# Core v3.0.1; publish-container run 34918034712, attempt 2, runtime index digest.
# Registry pull access must be verified before rebuilding an existing Codespace.
FROM ghcr.io/rka-project/rka-core@sha256:19a7ac4098e536930d395a1730ad5b57b082f769e784b40221312bc93cad00f7

# Do not mislabel App source with the inherited Core revision/version.
ARG RKA_APP_REVISION=unreleased
LABEL org.opencontainers.image.title="RKA user-owned demo" \
      org.opencontainers.image.source="https://github.com/rka-project/rka-app" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.version="0.0.1" \
      org.opencontainers.image.revision="${RKA_APP_REVISION}" \
      org.rka.core.image-ref="ghcr.io/rka-project/rka-core@sha256:19a7ac4098e536930d395a1730ad5b57b082f769e784b40221312bc93cad00f7"

# Tools needed by the development container, not a second RKA runtime.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git curl procps openssh-client openssh-server lsof \
    # Remove generated host identities IN THE INSTALL LAYER, not in a later one.
    # The sshd feature sees these packages already installed. Its ordered local
    # companion generates fresh identities when each container first starts.
    && rm -f /etc/ssh/ssh_host_rsa_key /etc/ssh/ssh_host_rsa_key.pub \
             /etc/ssh/ssh_host_ecdsa_key /etc/ssh/ssh_host_ecdsa_key.pub \
             /etc/ssh/ssh_host_ed25519_key /etc/ssh/ssh_host_ed25519_key.pub \
    && rm -rf /var/lib/apt/lists/*

COPY src/rka_app /opt/rka-app/rka_app
COPY .devcontainer/sshd.conf /etc/ssh/sshd_config.d/00-rka-codespaces.conf
ENV PYTHONPATH=/opt/rka-app

# Core stays idle unless the postStart adapter finds an explicit opt-in record
# and verifies private forwarding. No sample or auth is baked into the image.
# In particular, do not inherit Core's 9712 command or healthcheck.
HEALTHCHECK NONE
ENTRYPOINT []
CMD ["sleep", "infinity"]
