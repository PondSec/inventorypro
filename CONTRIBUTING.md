# Contributing

## Local setup

Use Python 3.12 or newer and an isolated environment:

```sh
python -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m playwright install firefox
.venv/bin/python -m pytest
```

Do not use production databases, credentials, update keys or uploaded files in
tests. Keep a change focused on one concern and retain public API routes unless
the pull request documents a compatibility migration.

## Pull requests

Before opening a pull request, run the relevant tests and inspect `git diff` for
secrets and unrelated files. The description must use the pull-request template,
including rollback and known limitations. Schema changes need a migration,
preflight backup instruction and a tested restore or downgrade path.

Security-sensitive changes require negative tests. Never solve a failing test by
removing coverage or weakening an authorization, validation or cryptographic
check without a reviewed replacement.
