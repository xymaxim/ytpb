import logging
import re
from datetime import datetime, time
from enum import auto, StrEnum
from typing import Literal, NamedTuple

import click
from timedelta_isoformat import timedelta

from ytpb import types
from ytpb.conditional import FORMAT_SPEC_RE
from ytpb.types import SegmentSequence
from ytpb.utils.date import ensure_date_aware

logger = logging.getLogger(__name__)


class PointInStreamParamType(click.ParamType):
    def __init__(self, allowed_literals: list[str] = None):
        if allowed_literals:
            self.allowed_literals = allowed_literals
        else:
            self.allowed_literals = []

    def convert(self, value: str, param, ctx) -> types.AbsolutePointInStream | str:
        match value:
            # Allowed literals
            case literal if value in self.allowed_literals:
                output = literal
            # Time of today
            case x if x[0] == "T" or (":" in x and "-" not in x):
                parsed_time = time.fromisoformat(x)
                today = datetime.now()
                output = today.replace(
                    hour=parsed_time.hour,
                    minute=parsed_time.minute,
                    second=parsed_time.second,
                    microsecond=parsed_time.microsecond,
                )
                output = output.astimezone(parsed_time.tzinfo)
            # Segment sequence
            case sequence if value.isdecimal():
                output = SegmentSequence(sequence)
            # Seems like a date and time
            case potential_date if value[:4].isdecimal():
                try:
                    output = ensure_date_aware(datetime.fromisoformat(value))
                except ValueError:
                    message = f"'{value}' does not match ISO 8601 date format."
                    self.fail(message, param, ctx)
            case _:
                self.fail("Option doesn't allow '{}' value", param, ctx)
                
        return output


class MomentParamType(click.ParamType):
    name = "moment"

    def convert(self, value: str, param, ctx) -> SegmentSequence | datetime | Literal["now"]:
        if value == "now":
            output = value
        else:
            output = PointInStreamParamType().convert(value, None, None)
        return output
    
    
class ISODateTimeParamType(click.ParamType):
    name = "date"

    def convert(self, value: str, param, ctx) -> datetime | Literal["now"]:
        if value == "now":
            output = value
        else:
            try:
                output = datetime.fromisoformat(value)
            except ValueError:
                self.fail(f"'{value}' does not match ISO 8601 date format.", param, ctx)
        return output


class DurationParamType(click.ParamType):
    def convert(self, value: str, param, ctx) -> float:
        """Converts a duration value into a float of total seconds. The
        acceptable syntax: '[%Hh][%Mm][%S[.%f]s]', where '%H', '%M', '%S' are
        integer number of hours, minutes, and seconds; '%f' expresses the
        fractional part of the seconds. Each part is optional but at least one
        part should be provided.

        >>> d = Duration()
        >>> d.convert("1.123s", None, None)
        1.123
        >>> d.convert("1h2m3s", None, None)
        3723
        >>> d.convert("120m", None, None)
        7200
        """
        duration_re = re.compile(
            (
                "(?:(?P<hh>[0-9]+)h)?"
                "(?:(?P<mm>[0-9]+)m)?"
                r"(?:(?P<ss>[0-9]+(?:\.[0-9]+)?)s)?"
            ),
            re.IGNORECASE,
        )

        matched = duration_re.match(value)
        # This assumes that the matched object is always non-None since the
        # expression consists of optional parts.
        is_nothing_extra = len(value) == matched.span()[1] - matched.span()[0]
        if any(matched.groups()) and is_nothing_extra:
            hh, mm, ss = matched.groups()
            total_seconds = 0
            for k, x in enumerate((ss, mm, hh)):
                if x:
                    total_seconds += float(x) * 60**k
        else:
            message = "Duration should be expressed as '[%Hh][%Mm][%S[.%f]s]'."
            self.fail(message, param, ctx)

        return total_seconds


class InputRewindInterval(NamedTuple):
    start: SegmentSequence | datetime | timedelta
    end: SegmentSequence | datetime | timedelta | Literal["now"]


class RewindIntervalParamType(click.ParamType):
    error_message_fmt = "Incorrectly formated interval: {}"

    def _replace_datetime_components(self, date: datetime, value: str):
        date_units = {"Y": "year", "M": "month", "D": "day"}
        time_units = {"H": "hour", "M": "minute", "S": "second"}

        components_to_replace = {}

        for part, units in zip(value.split("T"), (date_units, time_units)):
            if not part:
                continue
            previous = 0
            for i, c in enumerate(part):
                if c in units:
                    components_to_replace[units[c]] = int(part[previous:i])
                    previous = i + 1

        return date.replace(**components_to_replace)

    def _parse_interval_part(
        self, part: str, end: bool = False,
    ) -> int | str | Literal["now", ".."] | datetime | timedelta:
        match part:
            # Sequence number
            case x if x.isdecimal():
                output = int(x)
            # Duration
            case x if x[0] == "P":
                output = timedelta.fromisoformat(x)
            # Replace components
            case x if set(x) & set("DHMS"):
                output = x
            # Time of today
            case x if x[0] == "T" or (":" in x and "-" not in x):
                parsed_time = time.fromisoformat(x)
                today = datetime.now()
                output = today.replace(
                    hour=parsed_time.hour,
                    minute=parsed_time.minute,
                    second=parsed_time.second,
                    microsecond=parsed_time.microsecond,
                )
                output = output.astimezone(parsed_time.tzinfo)
            # Date and time
            case x if "T" in x:
                output = datetime.fromisoformat(x)
            case "now" | ".." as x:
                output = x
            case _:
                raise click.BadParameter(f"Incorrectly formatted part: {part}")

        return output

    def convert(
        self, value: str, param: click.Parameter, ctx: click.Context
    ) -> InputRewindInterval:
        parts = value.split("/")
        if len(parts) != 2:
            raise click.BadParameter("Interval must be formatted as '<start>/<end>'")

        start_part, end_part = parts

        parsed_start = self._parse_interval_part(start_part)
        parsed_end = self._parse_interval_part(end_part)

        match parsed_start, parsed_end:
            # Two durations
            case [timedelta(), timedelta()]:
                raise click.BadParameter("Two durations are ambiguous.")
            case "now" | ".." as x, _:
                raise click.BadParameter(
                    f"Keyword '{x}' is only allowed for the end part."
                )
            # Relative and 'now' or '..'
            case timedelta(), "now" | ".." as x:
                raise click.BadParameter(f"Keyword '{x}' not compatible with relative.")
            # Anything compatible and 'now' or '..'
            case ([int() | datetime() | timedelta(), "now" | ".."]):
                start = parsed_start
                end = parsed_end
            # Replacement components and date and time
            case ([str(), datetime()] | [datetime(), str()]):
                if isinstance(parsed_start, str):
                    end = parsed_end
                    start = self._replace_datetime_components(end, parsed_start)
                else:
                    start = parsed_start
                    end = self._replace_datetime_components(start, parsed_end)
            # Replacement components and anything non-compatible
            case ([str(), _] | [_, str()]):
                raise click.BadParameter(
                    "Replacement components is only compatible with date and time."
                )
            # Remaining and compatible
            case [_, _]:
                start = parsed_start
                end = parsed_end

        if type(start) == type(end) and start >= end:
            raise click.BadParameter(
                "Start is ahead or equal to end: {} >= {}".format(
                    start.isoformat(), end.isoformat()
                )
            )

        return start, end


class FormatSpecType(StrEnum):
    AUDIO = auto()
    VIDEO = auto()


class FormatSpecParamType(click.ParamType):
    def __init__(self, format_spec_type: FormatSpecType):
        self.format_spec_type = format_spec_type

    def convert(
        self, value: str, param: click.Parameter, ctx: click.Context
    ) -> str | None:
        if value in ("", "none"):
            output = None
        else:
            guard_condition = f"mime_type contains {self.format_spec_type.value}"
            if matched := FORMAT_SPEC_RE.match(value):
                if matched.group("function"):
                    replace_with = f"{guard_condition} and [{matched.group('expr')}]"
                    output = value.replace(matched.group("expr"), replace_with)
                else:
                    output = f"{guard_condition} and [{value}]"

        return output
