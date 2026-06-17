# Hermes Console — nightly backup sidecar.
#
# Builds a thin image that has the tools needed to snapshot Hermes's
# state, encrypt it, upload as a release to BOTH Forgejo + GitHub, and
# prune anything older than the configured retention window.
#
# Run by host cron as a one-shot container. Does NOT stay running.

FROM alpine:3.20

RUN apk add --no-cache \
      bash \
      ca-certificates \
      coreutils \
      curl \
      findutils \
      git \
      gnupg \
      gzip \
      jq \
      openssh-client \
      tar \
      tini \
      tzdata \
    && update-ca-certificates

WORKDIR /opt/hermes-backup

COPY backup.sh /opt/hermes-backup/backup.sh
RUN chmod +x /opt/hermes-backup/backup.sh

ENTRYPOINT ["/sbin/tini", "--", "/opt/hermes-backup/backup.sh"]
