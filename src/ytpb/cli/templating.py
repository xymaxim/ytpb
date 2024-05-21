import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import TypedDict, TypeVar

import jinja2

from ytpb.cli.utils import date, path

T = TypeVar("T", str, Path)

TEMPLATE_STRING_RE = re.compile(r"\{\{\s?([a-z_]+)\|?.*\}\}")


class MinimalOutputPathContext(TypedDict):
    id: str
    title: str


class IntervalOutputPathContext(TypedDict):
    input_start_date: datetime
    input_end_date: datetime
    actual_start_date: datetime
    actual_end_date: datetime
    duration: timedelta


def expand_template(
    value: T,
    environment: jinja2.Environment,
    context: dict,
) -> T:
    template = environment.from_string(str(value))
    return type(value)(template.render(context))


def adjust_string(
    value: str, chars: str = "posix", length: int = 30, separator: str = "-"
) -> str:
    characters = path.AllowedCharacters[chars.upper()]
    return path.adjust_string_for_filename(value, characters, length, separator)


def convert_to_timestamp(value: datetime) -> int:
    return int(value.timestamp())


def format_iso_date(value: datetime, styles: str = "basic,complete,hh") -> str:
    style_parameters = date.build_style_parameters_from_spec(styles)
    return date.format_iso_datetime(value, style_parameters)  # type: ignore


def format_duration(value: timedelta, style: str = "iso") -> str:
    pattern = date.DurationFormatPattern[style.upper()]
    return date.format_duration(value, pattern)


FILTERS = {
    "adjust": adjust_string,
    "date": datetime.strftime,
    "timestamp": convert_to_timestamp,
    "isodate": format_iso_date,
    "duration": format_duration,
}
