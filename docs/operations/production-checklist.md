# Production checklist

## Before first start

- Set a persistent, high-entropy `APP_SECRET_KEY`; do not rely on a generated
  development key. Generate with `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
- Set `INVENTORY_ENV=production`, secure cookie settings and the public origin.
- Set `INVENTORY_LINKS_ENCRYPTION_KEY` before creating inventory links. Keep it
  in the deployment secret store and restrict access.
- Store the SQLite database, uploads, runtime files and backups on durable
  storage with service-account-only permissions.
- Configure reverse proxy TLS termination and only list known proxy networks as
  trusted. Do not expose Flask's development server.
- Change or securely supply initial administrator credentials; remove the
  one-time credential file after recovery is verified.

## Deployment

- Build from the locked dependency set and record image digest/version.
- Run database migration preflight and take a verified backup before applying
  migrations.
- Run exactly one embedded scheduler owner. Set web worker count accordingly or
  disable job registration in non-scheduler workers.
- Keep the optional updater profile disabled unless its signed manifest policy,
  data volume and Docker socket risk are approved.
- Restrict egress for LDAP, SMTP, inventory links, health checks and updater
  manifest access to documented destinations.

## Routine operation

- Review failed logins, MFA failures, inventory-link failures, backup failures
  and update rollbacks.
- Verify backup completion and perform a restore drill at least quarterly.
- Rotate application and encryption secrets according to the documented
  procedure; keep an overlap key only until data is re-encrypted.
- Patch locked dependencies and rebuild the image through CI.
- Review user roles, inactive accounts, LDAP configuration and proxy allowlists.

## Incident response

1. Preserve logs and the affected database/backup read-only.
2. Revoke exposed application/encryption/LDAP/SMTP secrets as applicable.
3. Disable affected inventory links or updater automation.
4. Restore a verified backup into an isolated environment before production
   recovery.
5. Record the event and follow the private reporting process in `SECURITY.md`.
