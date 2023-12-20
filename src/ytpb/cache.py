"""A naive disk-based caching solution via JSON. Invalidation is based on the
filenaming."""
import json
import time
from pathlib import Path
from typing import Iterable


def _find_cached_item_paths(key: str, cache_directory: Path) -> Iterable[Path]:
    return cache_directory.glob(f"*~{key}")


def _check_item_is_expired(item_name: str) -> bool:
    """Check if an item has expired or not based on the item filename."""
    expires_at = int(item_name.split("~")[0])
    return time.time() >= expires_at


def read_from_cache(key: str, cache_directory: Path) -> dict | None:
    try:
        found_item_paths = _find_cached_item_paths(key, cache_directory)
        *earlier_item_paths, latest_item_path = sorted(found_item_paths)
    except ValueError:
        item = None
    else:
        for path in earlier_item_paths:
            path.unlink()

        if not _check_item_is_expired(latest_item_path.name):
            with open(latest_item_path) as f:
                item = json.load(f)
        else:
            item = None
            latest_item_path.unlink()

    return item


def write_to_cache(
    key: str, expires_at: str, item: dict, cache_directory: Path
) -> None:
    """Write an item to the cache file. The previous cached items with the key
    will be removed before."""
    cache_directory.mkdir(parents=True, exist_ok=True)
    if old_item_paths := _find_cached_item_paths(key, cache_directory):
        for path in old_item_paths:
            path.unlink()
    new_item_path = cache_directory / f"{expires_at}~{key}"
    with open(new_item_path, "w") as f:
        json.dump(item, f)


def remove_expired_cache_items(cache_directory: Path) -> None:
    for path in sorted(cache_directory.glob("*~*")):
        if _check_item_is_expired(path.name):
            path.unlink()
        else:
            break
