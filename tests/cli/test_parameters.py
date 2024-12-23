from datetime import datetime, timedelta, timezone

import click
import freezegun
import pytest

from dateutil.tz import tzlocal
from freezegun import freeze_time
from freezegun.api import FakeDatetime

from ytpb.cli.parameters import (
    FormatSpecParamType,
    FormatSpecType,
    RewindIntervalParamType,
)

from tests.helpers import patched_freezgun_astimezone

freezegun.api.FakeDatetime.astimezone = patched_freezgun_astimezone


def test_none_format_spec():
    spec_type = FormatSpecType.AUDIO
    assert None == FormatSpecParamType(spec_type).convert("none", None, None)
    assert None == FormatSpecParamType(spec_type).convert("", None, None)


def test_format_spec_without_function():
    expected = "format eq mp4"
    actual = FormatSpecParamType(FormatSpecType.AUDIO).convert(
        "format eq mp4", None, None
    )
    assert expected == actual


@freeze_time(tz_offset=2)
@pytest.mark.parametrize(
    "value,expected",
    [
        ("0/100", (0, 100)),
        (
            "0/20240102T102030+00",
            (0, datetime(2024, 1, 2, 10, 20, 30, tzinfo=timezone.utc)),
        ),
        (
            "20240102T102000+00/100",
            (datetime(2024, 1, 2, 10, 20, tzinfo=timezone.utc), 100),
        ),
        ("0/P1DT30S", (0, timedelta(days=1, seconds=30))),
        ("P1DT30S/100", (timedelta(days=1, seconds=30), 100)),
        (
            "20240102T102000+00/20240102T102030+00",
            (
                datetime(2024, 1, 2, 10, 20, tzinfo=timezone.utc),
                datetime(2024, 1, 2, 10, 20, 30, tzinfo=timezone.utc),
            ),
        ),
        (
            "20240102T102000/20240102T102030",
            (
                FakeDatetime(2024, 1, 2, 10, 20, tzinfo=timezone(timedelta(hours=2))),
                FakeDatetime(
                    2024, 1, 2, 10, 20, 30, tzinfo=timezone(timedelta(hours=2))
                ),
            ),
        ),
        (
            "20240102T102000+00/P1DT30S",
            (
                datetime(2024, 1, 2, 10, 20, tzinfo=timezone.utc),
                timedelta(days=1, seconds=30),
            ),
        ),
        (
            "P1DT30S/20240102T102030+00",
            (
                timedelta(days=1, seconds=30),
                datetime(2024, 1, 2, 10, 20, 30, tzinfo=timezone.utc),
            ),
        ),
        (
            "20240102T102000+00/now",
            (datetime(2024, 1, 2, 10, 20, tzinfo=timezone.utc), "now"),
        ),
        ("PT30S/now", (timedelta(seconds=30), "now")),
        (
            "20240102T102000+00/..",
            (datetime(2024, 1, 2, 10, 20, tzinfo=timezone.utc), ".."),
        ),
        (
            "../20240102T102000+00",
            ("..", datetime(2024, 1, 2, 10, 20, tzinfo=timezone.utc)),
        ),
        (
            "@1704190800/@1704190830.123",
            (
                datetime(2024, 1, 2, 10, 20, 0, tzinfo=timezone.utc),
                datetime(2024, 1, 2, 10, 20, 30, 123000, tzinfo=timezone.utc),
            ),
        ),
        ("earliest/100", ("earliest", 100)),
        ("earliest/..", ("earliest", "..")),
        (
            "20240102T102030+00 - P1DT1H20M30S/..",
            (
                datetime(2024, 1, 1, 9, 0, 0, tzinfo=timezone.utc),
                "..",
            ),
        ),
        (
            "20240102T102030+00 + P1DT1H20M30S/..",
            (
                datetime(2024, 1, 3, 11, 41, 0, tzinfo=timezone.utc),
                "..",
            ),
        ),
        (
            "P1DT1H20M30S + 20240102T102030+00/..",
            (
                datetime(2024, 1, 3, 11, 41, 0, tzinfo=timezone.utc),
                "..",
            ),
        ),
    ],
)
def test_rewind_interval(value: str, expected):
    assert expected == RewindIntervalParamType().convert(value, None, None)


@freeze_time(tz_offset=2)
@pytest.mark.parametrize(
    "value,expected",
    [
        (
            "20240102T102000/T25M",
            (
                FakeDatetime(2024, 1, 2, 10, 20, tzinfo=timezone(timedelta(hours=2))),
                FakeDatetime(2024, 1, 2, 10, 25, tzinfo=timezone(timedelta(hours=2))),
            ),
        ),
        (
            "20240102T102000+00/T25M",
            (
                datetime(2024, 1, 2, 10, 20, tzinfo=timezone.utc),
                (datetime(2024, 1, 2, 10, 25, tzinfo=timezone.utc)),
            ),
        ),
        (
            "2023Y12M31DT25M/20240102T102030",
            (
                FakeDatetime(
                    2023, 12, 31, 10, 25, 30, tzinfo=timezone(timedelta(hours=2))
                ),
                FakeDatetime(
                    2024, 1, 2, 10, 20, 30, tzinfo=timezone(timedelta(hours=2))
                ),
            ),
        ),
    ],
)
def test_rewind_interval_with_replacing_components(value: str, expected):
    assert expected == RewindIntervalParamType().convert(value, None, None)


@pytest.mark.parametrize(
    "value,expected",
    [
        (
            "10:25/T1035",
            (
                FakeDatetime(2024, 1, 2, 10, 25, tzinfo=tzlocal()),
                FakeDatetime(2024, 1, 2, 10, 35, tzinfo=tzlocal()),
            ),
        ),
        (
            "10:25 + PT1M/T1035 - PT1M",
            (
                FakeDatetime(2024, 1, 2, 10, 26, 0, tzinfo=tzlocal()),
                FakeDatetime(2024, 1, 2, 10, 34, 0, tzinfo=tzlocal()),
            ),
        ),
    ],
)
@freeze_time("2024-01-02T10:20:30-01")
def test_rewind_interval_with_time_of_today(value: str, expected):
    assert expected == RewindIntervalParamType().convert(value, None, None)


@pytest.mark.parametrize(
    "value,invalid_part",
    [
        ("20240102T102070+00/PT30M", "20240102T102070+00"),
        ("20240102T102030+00/PT30", "PT30"),
        ("100/earliest", "'earliest'"),
        ("now/100", "'now'"),
    ],
)
def test_invalid_rewind_interval(value: str, invalid_part: str):
    with pytest.raises(click.BadParameter) as exc_info:
        RewindIntervalParamType().convert(value, None, None)
    assert invalid_part in str(exc_info.value)


@pytest.mark.parametrize(
    "interval,error",
    [
        ("PT10M/PT20M", "Two durations"),
        ("../..", "Two '..'"),
        ("PT1H/..", "Keyword '..'"),
        ("../PT1H", "Keyword '..'"),
        ("2024Y/PT1H", "Replacement components"),
        ("2024Y/..", "Replacement components"),
        ("earliest/2024Y", "Replacement components"),
    ],
)
def test_non_compatible_interval_parts(interval: str, error: str):
    with pytest.raises(click.BadParameter) as exc_info:
        RewindIntervalParamType().convert(interval, None, None)
    assert error in str(exc_info.value)
