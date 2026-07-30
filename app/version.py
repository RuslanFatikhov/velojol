import re
from pathlib import Path


VERSION_PATTERN = re.compile(r'^\d+\.\d+(?:\.\d+)?$')
DEFAULT_VERSION = '0.0'
VERSION_FILE = Path(__file__).resolve().parents[1] / 'VERSION'


def load_app_version(version_file=None, fallback=DEFAULT_VERSION):
    """Read and validate the application version without failing startup."""
    path = Path(version_file) if version_file is not None else VERSION_FILE
    try:
        version = path.read_text(encoding='utf-8').strip()
    except OSError:
        return fallback
    return version if VERSION_PATTERN.fullmatch(version) else fallback
