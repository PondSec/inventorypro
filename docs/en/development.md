# Development and quality assurance

[Deutsch](../de/development.md) · [Documentation](../INDEX.md)

## Local environment

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m playwright install chromium firefox
python -m pytest -q
```

On Windows, use `.venv\Scripts\Activate.ps1`. Runtime dependencies are pinned in `requirements.lock`. Flask and Jinja remain the application stack. Shared components live in `templates/_ui.html`, the shell and base templates. Design tokens and layout rules are in `static/design-system.css` and `static/enterprise.css`.

## Architecture

`app.py` contains existing contracts and module registration. Domains under `inventorypro/domains/` encapsulate inventory, media, exports and other services. Checksummed SQL migrations live in `migrations/`. Compatibility mappings retain historical device IDs and permission boundaries; new interfaces use assets.

Static interface text is translated through `inventorypro/i18n.py` and `static/locale-en.json`. JavaScript uses `uiText()` only for interface messages. Do not translate user data, technical IDs, field keys, API values or CSS classes. Preserve placeholders and escaping.

## Tests

The suite uses isolated databases and synthetic records. Browser tests run in Chromium and Firefox. Coverage includes roles, CSRF, CRUD, category integrity, nested assets, ticket deletion, media access, language changes, focus, responsive layouts and themes. Platform-specific visual baselines live under `tests/visual-baselines/`.

`scripts/visual_audit.py` writes screenshots to `.qa-artifacts/visual-audit` by default, not to public documentation. Real records, operational logs and internal infrastructure must never become fixtures or public screenshots. Reports must identify checks actually executed and environmental limitations.

The release scripts `check_release_install.py`, `check_asset_image_upgrade.py`, `check_release_upgrade.py` and `check_release_volume_rollback.py` test Docker installation and rollback. Read each script's `--help` for options. Use disposable test volumes first.


### Planning visual checks

`python -m pytest -q tests/test_wishes_visual.py` compares the planning workspace in Chromium and Firefox, with light and dark themes at desktop and mobile sizes. The committed pixel baselines were reviewed on macOS. Other operating systems capture the views; without a matching baseline, the pixel comparison is reported as skipped. Interaction tests still run.

Explicitly generate replacement images with `UPDATE_WISH_VISUALS=1 python -m pytest -q tests/test_wishes_visual.py`, review every change visually, then run again without that variable. Never replace baselines solely because a comparison failed.
