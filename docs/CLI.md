# GoreeCloud Monitor CLI

GoreeCloud Monitor includes a **first-party, read-only, zero-dependency Node.js 22 CLI**, named `monitorctl`, using the same authenticated Monitor API as the browser frontend. It does not connect directly to Uptime Kuma's private Socket.IO or database and does not have mutation privileges.

## Install / run

From the public [GoreeCloud/monitor](https://github.com/GoreeCloud/monitor) checkout:

```sh
node bin/monitorctl.mjs --help
npm link # optional: makes 'monitorctl' available in your PATH
monitorctl doctor
```

Use an authorized SSH tunnel (or approved private network) to reach the frontend. By default the CLI targets `http://127.0.0.1:4305`, which is loopback only. For an approved HTTPS deployment, set `MONITOR_URL=https://monitor.goreecloud.com`. The CLI rejects cleartext HTTP to non-loopback hosts, embedded URL credentials and redirects.

## Authentication

Set `MONITOR_ACCESS_TOKEN` in the **shell process environment**, using your private secret injection workflow, then run:

```sh
monitorctl status
monitorctl list --state down
monitorctl incidents --json
monitorctl export --format csv > services.csv
monitorctl export --format json > services.json
monitorctl watch --interval 30
monitorctl doctor
```

Alternatively, for a noninteractive one-shot invocation, pipe the token from a secret manager into standard input with `--token-stdin`; no token is accepted as a command argument. The CLI performs authenticated login and keeps the returned short-lived session cookie in memory for that process. It never writes either credential to disk. In watch mode, repeated authenticated reads use the same session until it expires (then terminate with an authentication exit code).

Do not use `set -x`, shell history, insecure environment-file permissions, or commands that print access tokens. Never store them in GitHub issues, screenshots, logs or shared files.

## Automation

```sh
monitorctl status --json
monitorctl list --state unknown --json
monitorctl watch --json --count 2 --interval 30
monitorctl doctor --json
```

The `--json` output is a JSON object for one-shot commands; `watch --json` emits **one newline-delimited JSON object per observation**. The CSV export protects spreadsheet consumers from formula injection. Output contains only monitors published via the configured Uptime Kuma status page—these may include sensitive service names if published upstream, so safeguard exports.

| Exit code | Meaning |
| --- | --- |
| 0 | A configured status page with at least one published monitor, all UP, no active incident or published maintenance; or reachable frontend in unauthenticated doctor mode |
| 2 | One or more DOWN, UNKNOWN or MAINTENANCE services, a published active incident, or a maintenance window |
| 3 | Monitor data unavailable or page not configured, including no published monitors |
| 4 | Authentication denied or access token unavailable |
| 64 | Invalid arguments or a disallowed endpoint URL |

`status` always evaluates the full set of published monitors; `list` and `export` accept `--state` and `--search` filters but retain the full state exit classification. `doctor` without a token checks frontend liveness only; it does **not** establish live monitoring availability.

`monitorctl` is a local CLI and does not itself provide public DNS or Uptime Kuma admin automation. Native mobile/desktop apps remain separate deliverables.
