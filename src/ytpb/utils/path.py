import enum
import re
import string
import textwrap
import unicodedata
import warnings
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import pathvalidate
import unidecode

from ytpb.config import AddressableDict
from ytpb.types import AddressableMappingProtocol
from ytpb.utils.date import (
    format_iso_datetime,
    format_iso_duration,
    ISO8601DateFormatter,
    ISO8601DateStyleParameters,
)


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


class OutputStemPostfixType(enum.Enum):
    DURATION = enum.auto()
    END = enum.auto()


class TitleAllowedCharacters(enum.StrEnum):
    UNICODE = enum.auto()
    ASCII = enum.auto()
    POSIX = enum.auto()


@dataclass
class OutputPathTemplateContext:
    id: str
    title: str
    input_start_date: datetime
    input_end_date: datetime
    actual_start_date: datetime
    actual_end_date: datetime
    duration: timedelta

    def _render_title(self, value: str, settings: AddressableMappingProtocol) -> str:
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
                    value, style=style, **(custom_settings or {})
                )
            case _:
                warnings.warn(
                    f"Unknown style '{style}', fallback to 'original'. "
                    f"Check the {style_address} settings"
                )
                output = format_title_for_filename(value, style="original")
        return output

    def _render_date(
        self, value: datetime, formatter, settings: AddressableMappingProtocol
    ) -> str:
        output_date_styles = settings.traverse("output.date.styles")
        if output_date_styles:
            return formatter.format(f"{{:{output_date_styles}}}", value)
        else:
            return formatter.format("{}", value)

    def _render_duration(self, value) -> str:
        return format_iso_duration(value)

    def render(
        self, variables, config_settings: AddressableMappingProtocol | None = None
    ) -> dict[str, str]:
        if any(["date" in x for x in variables]):
            date_formatter = ISO8601DateFormatter()

        output = {}
        for variable in variables:
            match variable:
                case "title":
                    output[variable] = self._render_title(self.title, config_settings)
                case x if x.endswith("_date"):
                    output[variable] = self._render_date(
                        getattr(self, variable), date_formatter, config_settings
                    )
                case "duration":
                    output[variable] = self._render_duration(self.duration)
                case _:
                    output[variable] = getattr(self, variable)

        return output


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


def compose_excerpt_filename(
    prefix: str,
    start_date: datetime,
    /,
    end_date: datetime | None = None,
    *,
    basic_or_extended: str = "basic",
    reduced_or_complete: str = "reduced",
    duration_or_range: str = None,
    use_z_for_utc: bool = False,
    extension: str = "",
) -> str:
    style_parameters = ISO8601DateStyleParameters(
        format=basic_or_extended,
        precision=reduced_or_complete,
        use_z_for_utc=use_z_for_utc,
    )
    start_date_string = format_iso_datetime(start_date, style_parameters)
    prefix_and_start_date_part = f"{prefix}_{start_date_string}"

    if duration_or_range:
        match duration_or_range:
            case "duration":
                postfix = format_iso_duration(end_date - start_date)
            case "range":
                postfix = format_iso_datetime(end_date, style_parameters)
        output_filename = f"{prefix_and_start_date_part}_{postfix}"
    else:
        output_filename = f"{prefix_and_start_date_part}"

    if extension:
        output_filename += f".{extension}"

    return output_filename


def expand_template_output_path(
    value: Path,
    template_context: OutputPathTemplateContext,
    config_settings: AddressableMappingProtocol | None = None,
) -> Path:
    if config_settings is None:
        config_settings = AddressableDict({})
    value_string = str(value)

    matched_variables = OUTPUT_PATH_PLACEHOLDER_RE.findall(value_string)
    rendered = template_context.render(matched_variables, config_settings)
    output = ChevronTemplate(value_string).substitute(rendered)

    return Path(output)
