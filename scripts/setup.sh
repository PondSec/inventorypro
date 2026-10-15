#!/bin/sh
set -eu
command -v python3 >/dev/null 2>&1 || { echo 'Python 3 fehlt. Bitte Python 3 installieren oder den Compose-Schnellstart nutzen.' >&2; exit 1; }
exec python3 "$(dirname "$0")/setup.py" "$@"
