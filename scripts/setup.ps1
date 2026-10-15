$ErrorActionPreference = 'Stop'
if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 "$PSScriptRoot/setup.py" @args
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    & python "$PSScriptRoot/setup.py" @args
} else {
    throw 'Python 3 fehlt. Python installieren oder den Compose-Schnellstart nutzen.'
}
exit $LASTEXITCODE
