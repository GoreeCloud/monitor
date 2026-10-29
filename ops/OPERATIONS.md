# GoreeCloud Monitor operations and recovery

Status: alpha runbook. The presence of this procedure does not establish continuous backups or a successful live service restore.

## Runtime and privacy boundary

The monitor-web service listens only on 127.0.0.1:4305 and upstream Uptime Kuma on 127.0.0.1:3301. Verify both with docker compose ps and curl -f http://127.0.0.1:4305/healthz. The health endpoint tests Node liveness, not the availability of published monitors. Keep admin access private until an approved Caddy/TLS/VPN policy exists.

## Private SQLite-aware snapshot

Uptime Kuma uses SQLite with WAL. Copying only kuma.db while live is not a complete SQLite backup. The included Python utility uses SQLite's online backup API to capture a consistent committed database snapshot and copies supporting data separately. Supporting files might change during backup; quiesce service writes for full-system consistency where required.

Create a separate directory OUTSIDE the public source checkout on the VPS:

    install -d -m 700 "$HOME/goreecloud-monitor-private-backups"

From the Monitor repository, run:

    docker run --rm --network none --user "$(id -u):$(id -g)" \
      -v goreecloud-monitor_uptime-kuma-data:/source:ro \
      -v "$HOME/goreecloud-monitor-private-backups":/backups \
      -v "$PWD/ops/kuma_backup.py":/tool.py:ro \
      python:3.12-alpine python /tool.py backup --source /source --destination /backups

The tool writes an owner-only archive, validates its file checksums and opens an isolated temporary copy of SQLite for integrity checking. It does not mutate the live data volume. The archive may contain confidential monitor details and credentials. Protect access, encryption, rotation, retention and offsite storage appropriately.

To verify a selected archive, replace the placeholder filename with one actually observed in the backup directory:

    docker run --rm --network none --user "$(id -u):$(id -g)" \
      -v "$HOME/goreecloud-monitor-private-backups":/backups:ro \
      -v "$PWD/ops/kuma_backup.py":/tool.py:ro \
      python:3.12-alpine python /tool.py verify /backups/ARCHIVE-NAME.tar.gz

## Controlled upgrade/rollback

Record the current Git revision, upstream image digest and volume name. Before changes, verify a recent snapshot. Rebuild only monitor-web for frontend changes. Do not use docker compose down -v or delete the Uptime Kuma volume. Image rollback after a database migration can fail; test schema compatibility and restore into a separate volume rather than overwriting production data.

An isolated SQLite integrity check is not full application recovery evidence. A separate restored Uptime Kuma instance still needs to be launched and checked before declaring production recovery acceptance.

## Read-only CLI for operational checks

After setting `MONITOR_ACCESS_TOKEN` through a private process environment, run `node bin/monitorctl.mjs status --json` or `node bin/monitorctl.mjs watch --count 2 --interval 30 --json`. Read [docs/CLI.md](../docs/CLI.md) for script exit codes and access restrictions. Local CLI commands do not create monitors or bypass Uptime Kuma admin onboarding.

## Unresolved deployment prerequisites

Uptime Kuma administrator onboarding and a safe public status page with slug goreecloud remain necessary before Monitor shows actual health data. DNS/TLS/ingress exposure, native clients, device screenshots, retention scheduling, an encrypted offsite backup, and restore-to-running-service acceptance remain outstanding.
