# Core v3.0.0; publish-container run 34520774150, runtime index digest.
# Registry pull access must be verified before rebuilding an existing Codespace.
FROM ghcr.io/rka-project/rka-core@sha256:f35123dd117e34c9344df022594fbec1bffb42d50a8f2a53d78e58837987a14b

LABEL org.opencontainers.image.title="RKA user-owned demo" \
      org.opencontainers.image.source="https://github.com/rka-project/rka-app" \
      org.opencontainers.image.licenses="MIT" \
      org.rka.core.image-ref="ghcr.io/rka-project/rka-core@sha256:f35123dd117e34c9344df022594fbec1bffb42d50a8f2a53d78e58837987a14b"

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
