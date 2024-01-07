import enum
import re
import string
import textwrap
import unicodedata
import warnings
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, TypedDict

import pathvalidate
import unidecode
from timedelta_isoformat import timedelta as isotimedelta

from ytpb.config import AddressableDict
from ytpb.types import AddressableMappingProtocol
from ytpb.utils.date import ISO8601DateFormatter


DASHES = [
    "\u002D",  # HYPHEN-MINUS
    "\u2010",  # HYPHEN
    "\u2011",  # NON-BREAKING HYPHEN
    "\u2012",  # FIGURE DASH
    "\u2013",  # EN DASH
    "\u2014",  # EM DASH
    "\u2015",  # HORIZONTAL BAR
]

OUTPUT_PATH_PLACEHOLDER_NAME = r"[a-z_]+"
OUTPUT_PATH_PLACEHOLDER_RE = re.compile(rf"<({OUTPUT_PATH_PLACEHOLDER_NAME})>")


class TitleAllowedCharacters(enum.StrEnum):
    UNICODE = enum.auto()
    ASCII = enum.auto()
    POSIX = enum.auto()


class ChevronTemplate(string.Template):
    """A template that supports <variable>-style substitution."""

    delimiter = "<"
    pattern = rf"""
        <(?:
            (?P<escaped><) |
            (?P<named>{OUTPUT_PATH_PLACEHOLDER_NAME})> |
            (?P<braced>) |
            (?P<invalid>)
        )
    """


class OutputPathContextRenderer:
    @staticmethod
    def render_title(value: str, settings: AddressableMappingProtocol) -> str:
        style_address = "output.title.style"
        style = settings.traverse(style_address)
        match style:
            case "original" | None:
                output = format_title_for_filename(value)
            case "custom":
                custom_settings = AddressableDict(
                    settings.traverse("output.title.custom")
                )
                output = format_title_for_filename(
                    value, style=style, **custom_settings
                )
            case _:
                warnings.warn(
                    f"Unknown style '{style}', fallback to 'original'. "
                    f"Check the {style_address} settings"
                )
                output = format_title_for_filename(value, style="original")
        return output

    @staticmethod
    def render_date(
        value: datetime, formatter, settings: AddressableMappingProtocol
    ) -> str:
        output_date_styles = settings.traverse("output.date.styles")
        if output_date_styles:
            return formatter.format(f"{{:{output_date_styles}}}", value)
        else:
            return formatter.format("{}", value)

    @staticmethod
    def render_duration(value: timedelta, settings: AddressableMappingProtocol) -> str:
        seconds_rounded = round(value.total_seconds())
        return isotimedelta(seconds=seconds_rounded).isoformat()


class MinimalOutputPathContext(TypedDict):
    id: str
    title: str


class IntervalOutputPathContext(TypedDict):
    input_start_date: datetime
    input_end_date: datetime
    actual_start_date: datetime
    actual_end_date: datetime
    duration: timedelta


def render_minimal_output_path_context(
    context: MinimalOutputPathContext,
    config_settings: AddressableMappingProtocol | None = None,
) -> MinimalOutputPathContext:
    config_settings = config_settings or AddressableMappingProtocol({})
    output: MinimalOutputPathContext = {}
    for variable in MinimalOutputPathContext.__annotations__.keys():
        match variable:
            case "title" as x:
                output[x] = OutputPathContextRenderer.render_title(
                    context[x], config_settings
                )
            case _ as x:
                output[x] = context[x]
    return output


def render_interval_output_path_context(
    context: IntervalOutputPathContext,
    config_settings: AddressableMappingProtocol | None = None,
) -> IntervalOutputPathContext:
    config_settings = config_settings or AddressableMappingProtocol({})

    date_formatter = ISO8601DateFormatter()

    output: IntervalOutputPathContext = {}
    for variable in IntervalOutputPathContext.__annotations__.keys():
        match variable:
            case x if x.endswith("_date"):
                output[x] = OutputPathContextRenderer.render_date(
                    context[x], date_formatter, config_settings
                )
            case "duration" as x:
                output[x] = OutputPathContextRenderer.render_duration(
                    context[x], config_settings
                )
            case _ as x:
                output[x] = context[x]

    return output


def expand_template_output_path(
    path: Path,
    template_context: dict,
    render_function: Callable[[dict, AddressableMappingProtocol], dict],
    config_settings: AddressableMappingProtocol | None = None,
) -> Path:
    if config_settings is None:
        config_settings = AddressableDict({})

    path_string = str(path)

    matched_variables = OUTPUT_PATH_PLACEHOLDER_RE.findall(path_string)
    known_variables = set(template_context.keys())
    if unknown_variables := set(matched_variables) - known_variables:
        warnings.warn(f"Unknown variables: {unknown_variables}")

    rendered_context = render_function(template_context, config_settings)
    output = ChevronTemplate(path_string).substitute(rendered_context)

    return Path(output)


def sanitize_filename(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    output = pathvalidate.sanitize_filename(
        normalized, replacement_text="-", platform="POSIX"
    )
    return output


def posixify_filename(value: str, separator: str = "-"):
    posix_characters_re = re.compile(r"[^\w\-.]+", flags=re.ASCII)

    if not posix_characters_re.match(separator):
        actual_separator = separator
    else:
        actual_separator = "-"

    output = unidecode.unidecode(value, "replace", " ")
    output = posix_characters_re.sub(actual_separator, output)
    # Strip the space if a title started with a non-POSIX character.
    output = output.lstrip(actual_separator)

    return output


def adjust_title_for_filename(
    title: str,
    separator: str | None = None,
    max_length: int | None = None,
    characters: TitleAllowedCharacters = TitleAllowedCharacters.UNICODE,
) -> str:
    fallback_separator = "-"
    dashes_pattern = r"(?:\s+)?([{0}]+)(?:\s+)?".format("".join(DASHES))

    if separator:
        # For visual appeal, replace dashes and surrounding spaces with
        # dashes. Compare, e.g.: 'A_B_-_C_D' and 'A_B-C_D' (we prefer this one).
        title = re.sub(dashes_pattern, r"\1", title)

    if characters == TitleAllowedCharacters.POSIX:
        output = posixify_filename(title, separator or fallback_separator)
    else:
        output = sanitize_filename(title)

        actual_separator: str

        match characters:
            case TitleAllowedCharacters.UNICODE:
                actual_separator = separator
            case TitleAllowedCharacters.ASCII:
                actual_separator = separator and unidecode.unidecode(
                    separator, "replace", fallback_separator
                )
                output = unidecode.unidecode(output, "replace", " ")
                # Strip the space if a title started with a non-converted character.
                output = output.lstrip()

        # Replace multiple consecutive spaces with a single space. This can be
        # in an original title, as well as after converting a title using ASCII
        # codec (non-converted characters are replaced with a space).
        output = re.sub(r"\s+", " ", output)

    if max_length and len(output) > max_length:
        output = textwrap.shorten(output, max_length, placeholder="")
        output = re.sub(dashes_pattern + "$", "", output)

    if separator and characters != TitleAllowedCharacters.POSIX:
        # For the POSIX case, the output is already with spaces replaced after
        # the posixify_filename() function.
        output = re.sub(r"\s", actual_separator, output)

    return output


def format_title_for_filename(
    title: str,
    style: str = "original",
    separator: str | None = None,
    max_length: int | None = None,
    characters: TitleAllowedCharacters = TitleAllowedCharacters.UNICODE,
    lowercase: bool = False,
):
    match style:
        case "original":
            output = sanitize_filename(title)
        case "custom":
            output = adjust_title_for_filename(
                title, separator, max_length, characters=characters
            )
            if lowercase:
                output = output.lower()
        case _:
            raise ValueError(f"Unknown title formatting style: '{style}'")

    return output
