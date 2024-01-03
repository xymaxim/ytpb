import enum
import math
import re
import string
import warnings
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Any, Literal


@dataclass
class ISO8601DateStyleParameters:
    format: Literal["basic", "extended"] = "basic"
    precision: Literal["reduced", "complete"] = "complete"
    offset_format: Literal["hh", "hhmm"] = "hh"
    fractional_component: Literal["sec"] | None = None
    fraction_delimiter: Literal[".", ","] = "."
    use_z_for_utc: bool = False


def ensure_date_aware(date: datetime) -> datetime:
    """Ensure a date is timezone aware."""
    if date.tzinfo is None:
        local_tzinfo = date.astimezone().tzinfo
        return date.replace(tzinfo=local_tzinfo)
    else:
        return date


def format_iso_datetime(
    date: datetime,
    style: ISO8601DateStyleParameters | None = None,
) -> str:
    """Format `datetime` objects after ISO 8601. Supports complete and reduced
    date and time representations in basic and extended formats.

    Complete:
    - [year]["-"][month]["-"][day]["T"][hour][min][sec]
    """

    if style is None:
        style = ISO8601DateStyleParameters()

    plain_offset = date.strftime("%z")
    if plain_offset == "":
        raise ValueError("datetime object should be timezone aware")

    match style.precision:
        case "reduced":
            if date.microsecond != 0:
                # output_time_format = "%H:%M:%S.%f"
                output_time_format = "%H:%M:%S"
            elif date.second != 0:
                output_time_format = "%H:%M:%S"
            elif date.minute != 0:
                output_time_format = "%H:%M"
            else:
                output_time_format = "%H"
            output_format = f"%Y-%m-%dT{output_time_format}"
        case "complete":
            output_format = "%Y-%m-%dT%H:%M:%S"
            # if date.microsecond != 0:
            #    output_format += ".%f"
        case _:
            raise ValueError(
                "'precision' value should be either 'reduced' or 'complete'"
            )

    match style.format:
        case "basic":
            output_format = output_format.replace("-", "").replace(":", "")
            full_offset = plain_offset
        case "extended":
            full_offset = f"{plain_offset[:3]}:{plain_offset[-2:]}"
        case _:
            raise ValueError("'format' value should be either 'basic' or 'extended'")

    match style.offset_format:
        case "hh":
            offset = full_offset[:3]
        case "hhmm":
            offset = full_offset
        case _:
            raise ValueError("'offset_format' value should be either 'hh' or 'hhmm'")

    if style.use_z_for_utc and plain_offset == "+0000":
        offset = "Z"

    date_string = date.strftime(output_format)
    if date.microsecond != 0:
        # output = f"{date_string[:-3]}{offset}"
        output = f"{date_string}{offset}"
    else:
        output = f"{date_string}{offset}"

    return output


class DurationFormatPattern(enum.Enum):
    NUMERIC = "%H:%M%:%S"
    ISO8601 = "PT[%-HH][%-MM][%-SS]"
    IN_SENTENCE = "[%-H h ][%-M m ][%-S s]"


def format_duration(duration: timedelta, pattern: DurationFormatPattern) -> str:
    total_seconds = math.floor(duration.total_seconds() + 0.5)
    total_minutes, ss = divmod(total_seconds, 60)
    hh, mm = divmod(total_minutes, 60)

    output = pattern.value
    time_object = time(hh, mm, ss)

    optional_parts_re = r"\[(?P<part>(?P<fmt>%-?[HMS]).*?)\]"
    for matched in re.finditer(optional_parts_re, pattern.value):
        if int(time_object.strftime(matched.group("fmt"))) == 0:
            output = output.replace(matched.group(0), "")
        else:
            formatted_part = time_object.strftime(matched.group("part"))
            output = output.replace(matched.group(0), formatted_part)

    output = time_object.strftime(output).rstrip(" ")

    return output


def format_timedelta(duration: timedelta, use_ms_precision: bool = False) -> str:
    duration_total_seconds = abs(duration.total_seconds())

    if use_ms_precision:
        total_seconds = int(duration_total_seconds)
    else:
        total_seconds = math.floor(duration_total_seconds + 0.5)
    total_minutes, ss = divmod(total_seconds, 60)
    hh, mm = divmod(total_minutes, 60)

    sign = "+" if duration.total_seconds() >= 0 else "-"
    if hh == 0:
        output = f"{sign}{mm:02}:{ss:02}"
    else:
        output = f"{sign}{hh:02}:{mm:02}:{ss:02}"

    if use_ms_precision:
        rounded_milliseconds = round(abs(duration.microseconds / 1e3))
        output += f".{rounded_milliseconds:03d}"

    return output


def round_date(date: datetime) -> datetime:
    rounded = date.replace(second=0, microsecond=0)
    if date.microsecond < 1e6 / 2:
        rounded = rounded + timedelta(seconds=date.second)
    else:
        rounded = rounded + timedelta(seconds=date.second + 1)
    return rounded


def express_timedelta_in_words(delta: timedelta) -> str:
    if delta.seconds > 60:
        total_seconds = math.floor(delta.seconds / 60 + 0.5) * 60
    else:
        total_seconds = delta.seconds

    total_minutes, ss = divmod(total_seconds, 60)
    hh, mm = divmod(total_minutes, 60)

    if (hh == 0 and mm >= 45) or (hh == 1 and mm < 15):
        output = "an hour"
    elif hh >= 1:
        x = hh + math.floor(mm / 60 / 0.5 + 0.5) * 0.5
        output = f"{x:g} hours"
    elif mm == 1 and ss < 30:
        output = "a minute"
    elif mm >= 1:
        x = mm + math.floor(ss / 60 + 0.5)
        output = f"{x:g} minutes"
    elif mm == 0 and ss > 10:
        output = "less than a minute"
    else:
        output = "a moment"

    return output


def build_style_parameters_from_spec(
    style_spec: str,
) -> ISO8601DateStyleParameters | None:
    if not style_spec:
        return None

    style_parameters = {}
    input_styles = set([x.strip() for x in style_spec.split(",")])

    if "z" in input_styles:
        style_parameters["use_z_for_utc"] = True
        input_styles.remove("z")

    conflicting_styles_map: dict[str, str] = {}
    parameters_to_check = ["format", "precision", "offset_format"]
    for field_name in parameters_to_check:
        field = ISO8601DateStyleParameters.__dataclass_fields__[field_name]
        conflicting_styles_map[field_name] = field.type.__args__

    for input_style in input_styles:
        for parameter, parameter_styles in conflicting_styles_map.items():
            if input_style in parameter_styles:
                if already_set_style := style_parameters.get(parameter, None):
                    conflicted_styles = sorted([already_set_style, input_style])
                    raise ValueError(
                        "Mutually exclusive styles provided: "
                        f"'{conflicted_styles[0]}' and '{conflicted_styles[1]}'"
                    )
                else:
                    style_parameters[parameter] = input_style
                    break

    if unknown_styles := input_styles ^ set(style_parameters.values()):
        warnings.warn(f"Ignoring unknown style(s): {', '.join(sorted(unknown_styles))}")

    return ISO8601DateStyleParameters(**style_parameters)


class ISO8601DateFormatter(string.Formatter):
    """A variant of `string.Formatter` that format dates in ISO 8601
    format.

    This extends the format specification for `datetime` objects with
    the following, ISO-8601 related, styles: 'basic', 'extended', 'reduced',
    'complete', 'hh', 'hhmm', and 'z'.
    """

    def format_field(self, value: Any, format_spec: str) -> str:
        if isinstance(value, datetime):
            if not format_spec:
                return format_iso_datetime(value)
            style_parameters = build_style_parameters_from_spec(format_spec)
            output = format_iso_datetime(value, style_parameters)  # type: ignore
        else:
            output = super().format_field(value, format_spec)

        return output
