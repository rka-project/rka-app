# syntax=docker/dockerfile:1

# A release build must pass a digest-pinned reference, for example:
#   ghcr.io/rka-project/rka-core@sha256:...
# There is deliberately no mutable default.
ARG RKA_CORE_IMAGE
FROM ${RKA_CORE_IMAGE}
ARG RKA_CORE_IMAGE

LABEL org.opencontainers.image.title="RKA App" \
      org.opencontainers.image.description="Lifecycle supervisor and deployment shell for RKA Core" \
      org.opencontainers.image.source="https://github.com/rka-project/rka-app" \
      org.opencontainers.image.licenses="MIT" \
      org.rka.core.image-ref="${RKA_CORE_IMAGE}"

COPY src/rka_app /opt/rka-app/rka_app

ENV PYTHONPATH=/opt/rka-app \
    RKA_HOST=0.0.0.0 \
    RKA_PORT=7860 \
    RKA_APP_WORKER_ENABLED=true \
    RKA_APP_STARTUP_TIMEOUT=120 \
    RKA_APP_SHUTDOWN_TIMEOUT=20 \
    RKA_APP_HEALTH_INTERVAL=0.25

EXPOSE 7860
STOPSIGNAL SIGTERM

# Override Core's 9712-specific check because RKA App exposes one configurable
# port and defaults to the Hugging Face-compatible 7860.
HEALTHCHECK --interval=10s --timeout=5s --start-period=15s --retries=6 \
  CMD python -c "import os,urllib.request; p=os.environ.get('RKA_PORT','7860'); urllib.request.urlopen('http://127.0.0.1:'+p+'/api/health',timeout=4).read()"

ENTRYPOINT ["python", "-m", "rka_app.supervisor"]
