import logging
import re
from datetime import datetime
from enum import auto, StrEnum
from typing import Literal

import click

from ytpb import types
from ytpb.conditional import FORMAT_SPEC_RE
from ytpb.utils.date import ensure_date_aware


logger = logging.getLogger(__name__)


class PointInStreamParamType(click.ParamType):
    def __init__(self, end: bool = False):
        self.end = end

    def convert(self, value: str, param, ctx) -> types.PointInStream | Literal["now"]:
        match value:
            case "now":
                if self.end:
                    output = value
                else:
                    self.fail("Option does not accept 'now' keyword.")
            case value if value.isdecimal():
                output = int(value)
            case _:
                try:
                    output = ensure_date_aware(datetime.fromisoformat(value))
                except ValueError:
                    message = f"'{value}' does not match ISO 8601 date format."
                    self.fail(message, param, ctx)
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
