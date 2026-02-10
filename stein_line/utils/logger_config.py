import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logging(config):
    """Configure simple application-wide logging.

    Writes to `steinline.log` next to the project config if available.
    """
    root = logging.getLogger()
    if root.handlers:
        return root

    root.setLevel(logging.INFO)

    # Determine log path
    try:
        base = Path(config.source_root).resolve().parent
    except Exception:
        base = Path('.').resolve()
    log_path = base / 'steinline.log'

    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')

    file_h = RotatingFileHandler(log_path, maxBytes=10 * 1024 * 1024, backupCount=3)
    file_h.setFormatter(formatter)
    file_h.setLevel(logging.INFO)

    console_h = logging.StreamHandler()
    console_h.setFormatter(formatter)
    console_h.setLevel(logging.INFO)

    root.addHandler(file_h)
    root.addHandler(console_h)

    return root
