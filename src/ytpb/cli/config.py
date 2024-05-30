import logging
import operator
import os
import tomllib
from collections import ChainMap
from collections.abc import Hashable, Mapping, MutableMapping
from copy import deepcopy
from functools import reduce
from pathlib import Path
from typing import Any

import platformdirs
import structlog

from ytpb.cli.formats import ALIASES as FORMAT_ALIASES


class AddressableMixin:
    def traverse(self, address: str, default: Any = None, delimiter: str = ".") -> Any:
        """Traverse nested dictionary to access a value by an address."""
        try:
            keys = address.split(delimiter)
            return reduce(operator.getitem, keys, self)
        except KeyError:
            return default


class AddressableDict(dict, AddressableMixin):
    """A dictionary that allows to use an address to access a nested value."""


class DeepChainMap(ChainMap):
    """A ChainMap that works on nested dictionaries."""

    def __getitem__(self, key: Hashable) -> Any:
        if not isinstance(value := super().__getitem__(key), Mapping):
            return value

        values: list[dict] = []
        for mapping in self.maps:
            try:
                values.append(mapping[key])
            except KeyError:
                pass

        if values:
            return self.__class__(*values)

        return self.__missing__(key)


class AddressableChainMap(DeepChainMap, AddressableMixin):
    """A ChainMap that allows to use an address to access a nested value."""


USER_AGENT = "Mozilla/5.0 (Android 14; Mobile; rv:68.0) Gecko/68.0 Firefox/120.0"


DEFAULT_OUTPUT_PATH = "{{ title|adjust }}_{{ id }}_{{ input_start_date|isodate }}"

DEFAULT_CONFIG = AddressableDict(
    {
        "version": 2,
        "options": {
            "download": {
                "audio_format": "itag eq 140",
                "video_format": (
                    "best(format eq mp4 and height le 1080 and frame_rate eq 30)"
                ),
                "output_path": DEFAULT_OUTPUT_PATH,
            },
            "capture": {
                "frame": {
                    "video_format": "best(frame_rate eq 30)",
                    "output_path": "{{ title|adjust }}_{{ id }}_{{ moment_date|isodate }}.jpg",
                },
                "timelapse": {
                    "video_format": "best(frame_rate eq 30)",
                    "output_path": (
                        "{{ title|adjust }}_{{ id }}/{{ input_start_date|isodate }}/{{ every.replace('PT', 'ET') }}/"
                        "{{ title|adjust }}_{{ id }}_{{ input_start_date|isodate }}_{{ every.replace('PT', 'ET') }}_%04d.jpg"
                    ),
                },
            },
            "mpd": {
                "compose": {
                    "audio_formats": "itag eq 140",
                    "video_formats": (
                        "codes eq vp9 and [height eq 1080 or height eq 720] and frame_rate eq 30"
                    ),
                    "output_path": f"{DEFAULT_OUTPUT_PATH}.mpd",
                }
            },
        },
        "general": {
            "preview_duration": 10,
            "user_agent": USER_AGENT,
            "aliases": FORMAT_ALIASES,
        },
        "output": {
            "metadata": {
                "dates": "iso",
            },
        },
    }
)


def setup_logging(level: int) -> None:
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.dev.ConsoleRenderer(
                exception_formatter=structlog.dev.plain_traceback,
                # For details about NO_COLOR, see https://no-color.org/
                colors="NO_COLOR" not in os.environ,
            ),
            structlog.dev.set_exc_info,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("urllib3").propagate = False


def get_default_config_path() -> Path:
    return platformdirs.user_config_path() / "ytpb/config.toml"


def load_config_from_file(path: Path) -> dict:
    with path.open("rb") as f:
        return tomllib.load(f)


def update_nested_dict(base: MutableMapping, updates: MutableMapping) -> MutableMapping:
    """Update a base nested dict with values from updates. The new, update
    dictionary will be returned.
    """
    updated_dict = deepcopy(base)
    for key, value in updates.items():
        if isinstance(value, Mapping) and isinstance(base.get(key), Mapping):
            updated_dict[key] = update_nested_dict(base[key], value)
        else:
            updated_dict[key] = value
    return updated_dict
