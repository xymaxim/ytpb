import json
import os
from datetime import datetime, UTC
from pathlib import Path

from freezegun import freeze_time

from ytpb.cache import read_from_cache, remove_expired_cache_items, write_to_cache


@freeze_time(str(datetime.fromtimestamp(1697012300, UTC)))
def test_remove_expired_items(cache_directory: Path):
    a = cache_directory / "1697012299~a"
    a.touch()
    b = cache_directory / "1697012300~b"
    b.touch()
    c = cache_directory / "1697012301~c"
    c.touch()

    remove_expired_cache_items(cache_directory)
    assert not os.path.exists(a)
    assert not os.path.exists(b)
    assert os.path.exists(c)


@freeze_time(str(datetime.fromtimestamp(1697012300, UTC)))
def test_remove_expired_items_from_empty_cache(cache_directory: Path):
    assert next(cache_directory.iterdir(), None) is None
    remove_expired_cache_items(cache_directory)


@freeze_time(str(datetime.fromtimestamp(1697012300, UTC)))
def test_read_item_from_cache(cache_directory: Path):
    (cache_directory / "1697012301~a").touch()
    (cache_directory / "1697012302~a").write_text('{"f(x)": "x"}')
    assert read_from_cache("a", cache_directory) == {"f(x)": "x"}


@freeze_time(str(datetime.fromtimestamp(1697012300, UTC)))
def test_read_non_existing_item_from_cache(cache_directory: Path):
    assert read_from_cache("n", cache_directory) is None


@freeze_time(str(datetime.fromtimestamp(1697012300, UTC)))
def test_read_expired_item_from_cache(cache_directory: Path):
    a = cache_directory / "1697012299~a"
    a.touch()
    assert read_from_cache("a", cache_directory) is None


@freeze_time(str(datetime.fromtimestamp(1697012300, UTC)))
def test_write_to_cache(cache_directory: Path):
    o = cache_directory / "1697012299~o"
    o.touch()

    a1 = cache_directory / "1697012301~a"
    a1.touch()

    a2 = cache_directory / "1697012302~a"
    item_to_cache = {"f(x)": "x"}
    write_to_cache("a", "1697012302", item_to_cache, cache_directory)
    with open(a2) as f:
        cached_item = json.load(f)

    assert cached_item == item_to_cache

    assert os.path.exists(o)
    assert not os.path.exists(a1)
