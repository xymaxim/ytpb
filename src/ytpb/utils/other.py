import logging
import tempfile
from pathlib import Path

from platformdirs import user_cache_path

logger = logging.getLogger(__name__)


def get_cache_directory() -> Path:
    return Path(user_cache_path(), "ytpb")


def remove_cached_file(path: Path):
    logger.debug("Removing cached file '%s'", path)
    path.unlink()
