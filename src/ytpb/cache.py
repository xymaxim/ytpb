"""Naive disk-based caching via JSON files.

The cache invalidation is based on the filenaming: ``<expires-at>~<key>``.

In the playback context, ``key`` is a video ID and ``expires-at`` is a
timestamp referred to the expiration time of segment base URL.
"""

import json
import time
from pathlib import Path
from typing import Iterable

import structlog

logger = structlog.get_logger(__name__)


def _find_cached_item_paths(key: str, cache_directory: Path) -> Iterable[Path]:
    return cache_directory.glob(f"*~{key}")


def _check_item_is_expired(item_name: str) -> bool:
    """Checks if an item has expired based on the item filename."""
    expires_at = int(item_name.split("~")[0])
    return time.time() >= expires_at


def read_from_cache(key: str, cache_directory: Path) -> dict | None:
    """Reads a cached item.

    Args:
        key: A cached item key.
        cache_directory: A cached items location.

    Returns:
        A dictionary of a cached item.
    """
    try:
        found_item_paths = _find_cached_item_paths(key, cache_directory)
        *earlier_item_paths, latest_item_path = sorted(found_item_paths)
    except ValueError:
        item = None
    else:
        for path in earlier_item_paths:
            path.unlink()

        if _check_item_is_expired(latest_item_path.name):
            logger.debug("Found expired cached item: %s", latest_item_path)
            latest_item_path.unlink()
            item = None
        else:
            with open(latest_item_path, encoding="utf-8") as f:
                item = json.load(f)
            logger.debug("Found unexpired cached item: %s", latest_item_path)

    return item


def write_to_cache(
    key: str, expires_at: str, item: dict, cache_directory: Path
) -> None:
    """Writes a cache item to a file.

    The existing cached items with ``key`` (both expired and unexpired) will be
    removed before writing.

    Args:
        key: A cache item key.
        expires_at: When a cache item will be expired.
        cache_directory: A cached items location.
    """
    cache_directory.mkdir(parents=True, exist_ok=True)
    if old_item_paths := _find_cached_item_paths(key, cache_directory):
        for path in old_item_paths:
            path.unlink()
    new_item_path = cache_directory / f"{expires_at}~{key}"
    with open(new_item_path, "w", encoding="utf-8") as f:
        json.dump(item, f)
    logger.debug("New cache item has been created: %s", new_item_path)


def remove_expired_cache_items(cache_directory: Path) -> None:
    """Removes expired cache items."""
    for path in sorted(cache_directory.glob("*~*")):
        if _check_item_is_expired(path.name):
            path.unlink()
        else:
            break
