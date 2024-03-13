import logging
import operator
import os
import re
import tomllib
from collections import ChainMap
from functools import reduce
from itertools import product
from pathlib import Path
from typing import Any, Callable

import structlog
from platformdirs import user_config_path


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


class AddressableChainMap(ChainMap, AddressableMixin):
    """ChainMap that allows to use an address to access a nested value."""


USER_AGENT = "Mozilla/5.0 (Android 14; Mobile; rv:68.0) Gecko/68.0 Firefox/120.0"


# Dynamic aliases (such aliases that are expanded by functions).
def expand_itag_aliases(format_spec: str) -> str:
    """@<itag> = itag eq <itag>"""
    return re.sub(r"@(\d+)\b", r"itag eq \1", format_spec)


ALIAS_EXPAND_FUNCTIONS: tuple[Callable[[str], str]] = (expand_itag_aliases,)

# Static aliases (such aliases that are explicitly defined).
FORMAT_ALIASES = {"mp4": "format eq mp4", "webm": "format eq webm"}

VIDEO_QUALITY_HEIGHTS = (144, 240, 360, 480, 720, 1080, 1440, 2160)

VIDEO_QUALITY_30FPS_ALIASES = {
    f"{height}p": f"height eq {height} and frame_rate eq 30"
    for height in VIDEO_QUALITY_HEIGHTS
}
VIDEO_QUALITY_30FPS_ALIASES.update(
    {
        f"{height}p30": f"height eq {height} and frame_rate eq 30"
        for height in VIDEO_QUALITY_HEIGHTS
    }
)

VIDEO_QUALITY_60FPS_ALIASES = {
    f"{height}p60": f"height eq {height} and frame_rate eq 60"
    for height in [720, 1080, 1440, 2160]
}

VIDEO_QUALITY_WITH_OPERATOR_ALIASES = {
    f"{operator}{height}p": f"height {operator_name} {height}"
    for (operator, operator_name), height in product(
        [("<", "lt"), ("<=", "le"), (">", "gt"), (">=", "ge")], VIDEO_QUALITY_HEIGHTS
    )
}

NAME_QUALITY_ALIASES = {
    "low": "height eq 144",
    "medium": "height eq 480",
    "high": "height eq 720",
    "FHD": "height eq 1080",
    "2K": "height eq 1440",
    "4K": "height eq 2160",
}

FRAME_PER_SECOND_ALIASES = {"30fps": "frame_rate eq 30", "60fps": "frame_rate eq 60"}

BUILT_IN_ALIASES = {
    **FORMAT_ALIASES,
    **VIDEO_QUALITY_30FPS_ALIASES,
    **VIDEO_QUALITY_60FPS_ALIASES,
    **VIDEO_QUALITY_WITH_OPERATOR_ALIASES,
    **NAME_QUALITY_ALIASES,
    **FRAME_PER_SECOND_ALIASES,
}

ALL_ALIASES = {**BUILT_IN_ALIASES}

DEFAULT_OUTPUT_PATH = "<title>_<input_start_date>"

DEFAULT_CONFIG = AddressableDict(
    {
        "version": 1,
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
                    "video_format": "best(format eq mp4 and frame_rate eq 30)",
                    "output_path": "<title>_<moment_date>.jpg",
                },
                "timelapse": {
                    "video_format": "best(format eq mp4 and frame_rate eq 30)",
                    "output_path": (
                        "<title>/<input_start_date>/<every>/"
                        "<title>_<input_start_date>_<every>_%04d.jpg"
                    ),
                },
            },
            "mpd": {
                "compose": {
                    "audio_formats": "itag eq 140",
                    "video_formats": (
                        "format eq webm and [height eq 720 or height eq 1080] and "
                        "frame_rate eq 30"
                    ),
                    "output_path": f"{DEFAULT_OUTPUT_PATH}.mpd",
                }
            },
        },
        "general": {
            "preview_duration": 10,
            "user_agent": USER_AGENT,
        },
        "output": {
            "date": {"styles": "basic,complete,hh"},
            "title": {
                "style": "custom",
                "custom": {
                    "characters": "posix",
                    "separator": "-",
                    "max_length": 30,
                    "lowercase": False,
                },
            },
        },
    }
)


def setup_logging(level: int) -> None:
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.TimeStamper(fmt="%s.%f", utc=True),
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
    return user_config_path("ytpb") / "config.toml"


def load_config_from_file(path: Path) -> dict:
    with path.open("rb") as f:
        return tomllib.load(f)


def update_nested_dict(base: dict, updates: dict) -> dict:
    """Update a base nested dict with values from updates. The new, update
    dictionary will be returned.
    """
    updated_dict = base.copy()
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            updated_dict[key] = update_nested_dict(base[key], value)
        else:
            updated_dict[key] = value
    return updated_dict
