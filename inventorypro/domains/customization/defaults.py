"""Single source for backend validation and the initial browser theme."""
import json
from pathlib import Path

DEFAULT_CUSTOMIZATION = json.loads(Path(__file__).with_name('defaults.json').read_text(encoding='utf-8'))
