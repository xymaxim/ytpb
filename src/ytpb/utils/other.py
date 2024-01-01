import logging
from pathlib import Path

from platformdirs import user_cache_path

from ytpb.types import RelativePointInStream

logger = logging.getLogger(__name__)


def get_cache_directory() -> Path:
    return Path(user_cache_path(), "ytpb")


def remove_cached_file(path: Path):
    logger.debug("Removing cached file '%s'", path)
    path.unlink()


def resolve_relativity_in_interval(start, end):
    is_start_relative = isinstance(start, RelativePointInStream)
    is_end_relative = isinstance(end, RelativePointInStream)

    if is_start_relative and is_end_relative:
        raise ValueError("Start and end couldn't be both relative")

    try:
        if is_start_relative:
            start = end - start
        elif is_end_relative:
            end = start + end
    except TypeError:
        pass

    return start, end
