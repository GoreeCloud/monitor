# Security policy

This is an alpha application, not a security certification.

- Keep Kuma admin port 3301 and Monitor frontend port 4305 bound to loopback by default; use private SSH or VPN tunneling.
- If intentionally exposing Monitor via TLS, enforce trusted ingress and set MONITOR_PUBLIC_ORIGIN to the exact HTTPS origin.
- Use unique strong MONITOR_ACCESS_TOKEN and MONITOR_SESSION_SECRET values, stored only in a private .env with 0600 permissions.
- Never commit logs, database volumes, secrets or backups.
- Public Kuma status pages expose the monitors you publish; do not place sensitive target names or addresses there.
- Update the pinned upstream engine deliberately and test backups/restoration before upgrades.
- Privileged monitor editing is not available through this read-only console.

Report security issues privately to the maintainer rather than posting live exploit details.
