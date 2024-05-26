import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, TypedDict, TypeVar

import jinja2
import pathvalidate

from ytpb.cli.utils import date, path
from ytpb.types import AudioStream, VideoStream

T = TypeVar("T", str, Path)


class MinimalOutputPathContext(TypedDict):
    #: YouTube video ID.
    id: str
    #: Video's title.
    title: str


class AudioStreamOutputPathContext(TypedDict):
    #: Audio stream (representaiton).
    audio_stream: AudioStream | None


class VideoStreamOutputPathContext(TypedDict):
    #: Video stream (representaiton).
    video_stream: VideoStream | None


class IntervalOutputPathContext(TypedDict):
    #: Input start date.
    input_start_date: datetime
    #: Input end date.
    input_end_date: datetime
    #: Actual start date.
    actual_start_date: datetime
    #: Actual end date.
    actual_end_date: datetime
    #: Actual duration.
    duration: timedelta


def check_is_template(value: str) -> bool:
    return any([delimiter in value for delimiter in ("{#", "{{", "{%")])


def render_template(
    value: T,
    environment: jinja2.Environment,
    context: dict,
) -> T:
    template = environment.from_string(str(value))
    return type(value)(template.render(context))


def render_path_template(
    value: Path, environment: jinja2.Environment, context: dict
) -> Path:
    rendered = render_template(value, environment, context)
    return sanitize_filepath(rendered)


def do_adjust_string(
    value: str,
    chars: str = "posix",
    length: int = 30,
    separator: str | None = None,
    break_words: bool = False,
) -> str:
    """Adjusts a string for platform-independent filename.

    The filter does the following:

    * Sanitize a string by replacing non-valid characters with '-' for
      multi-platform support
    * Translate characters to allowed ones (ASCII-only or POSIX-compliant [1])
      or keep them as is
    * Remove excessive whitespaces
    * Reduce the length to the provided value. By default, words are truncated
      at boundaries.

    References:
        1. https://www.gnu.org/software/automake/manual/html_node/Limitations-on-File-Names.html

    Examples:
        1. Allow only POSIX-compliant characters and truncate to the default
           length value:

           .. sourcecode:: jinja

              {{ "Vidéo en direct – 24/7"|adjust }}
              "Video-en-direct--24-7"

        2. Truncate to a shorten length and break words:

           .. sourcecode:: jinja

              {{ "Vidéo en direct – 24/7"|adjust(12, break_words=True) }}
              "Video-en-dir"

        3. Allow only ASCII characters:

           .. sourcecode:: jinja

              {{ "Vidéo en direct – 24/7"|adjust('ascii') }}
              "Vidéo en direct -- 24-7"

        4. Keep original characters and length but slightly adjust a title
           (sanitize characters, remove excessive whitespaces):

           .. sourcecode:: jinja

              {{ "Vidéo   en direct – 24/7"|adjust('unicode', length=255) }}
              "Vidéo en direct – 24-7"
    """
    characters = path.AllowedCharacters[chars.upper()]
    return path.adjust_string_for_filename(value, characters, length, separator)


def do_format_iso_date(value: datetime, styles: str = "basic,complete,hh") -> str:
    """Formats a date according to the ISO 8601 standard.

    Supports complete and reduced date and time representations in basic and
    extended formats. The list of available styles: ``basic`` or ``extended``,
    ``complete`` or ``reduced``, ``hh`` or ``hhmm``, ``z``. Can be used together
    separated by a comma.

    If no styles are provided, or not all styles are specified, the default ones
    will be applied separately: ``basic``, ``complete``, ``hh``.

    Examples:
        .. sourcecode:: jinja

           {# Complete representation, basic format #}
           {{ input_start_date|isodate }}
           "20240102T102000+00"

           {# Complete representation of the Zulu time, extended format #}
           {{ input_start_date|isodate('extended,z') }}
           "2024-01-02T10:20:00Z"

           {# Reduced representation, basic format #}
           {{ input_start_date|isodate('reduced') }}
           "20240102T1020+00"

           {# Complete representation, basic format, HHMM offset #}
           {{ input_start_date|isodate('hhmm') }}
           "20240102T102000+0000"
    """
    style_parameters = date.build_style_parameters_from_spec(styles)
    return date.format_iso_datetime(value, style_parameters)  # type: ignore


def do_convert_to_utc(value: datetime) -> str:
    """Converts a date to the UTC timezone.

    Example:
        .. sourcecode:: jinja

           {{ input_start_date|utc }}
           "2024-01-02 10:20:30.123456+00:00"
    """
    return value.astimezone(timezone.utc)


def do_convert_to_timestamp(value: datetime) -> int:
    """Converts a date to an Unix timestamp in seconds.

    Example:
        .. sourcecode:: jinja

            {{ input_start_date|timestamp }}
            1704190830
    """
    return int(value.timestamp())


def do_format_duration(value: timedelta, style: str = "iso") -> str:
    """Formats a timedelta to a duration string.

    Available styles: ``hms``, ``iso`` (default), ``numeric``.

    Examples:
        .. sourcecode:: jinja

           {{ duration|duration }}
           "PT1H20M30S"

           {{ duration|duration('hms') }}
           "1h20m30s"

           {{ duration|duration('numeric') }}
           "01:20:30"
    """
    pattern = date.DurationFormatPattern[style.upper()]
    return date.format_duration(value, pattern)


def sanitize_filepath(value: Path) -> Path:
    return pathvalidate.sanitize_filepath(value)


FILTERS = {
    "adjust": do_adjust_string,
    "utc": do_convert_to_utc,
    "isodate": do_format_iso_date,
    "timestamp": do_convert_to_timestamp,
    "duration": do_format_duration,
}

# Aliases for Sphinx (autodoc) documentation:
adjust = FILTERS["adjust"]
isodate = FILTERS["isodate"]
utc = FILTERS["utc"]
timestamp = FILTERS["timestamp"]
duration = FILTERS["duration"]
