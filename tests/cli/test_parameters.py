from datetime import datetime, timezone

import click
import pytest
from dateutil.tz import tzlocal
from freezegun import freeze_time
from freezegun.api import FakeDatetime
from timedelta_isoformat import timedelta

from ytpb.cli.parameters import (
    DurationParamType,
    FormatSpecParamType,
    FormatSpecType,
    ISODateTimeParamType,
    RewindIntervalParamType,
)


@pytest.mark.parametrize(
    "value,seconds",
    [
        ("3s", 3),
        ("30.123s", 30.123),
        ("1h2m30s", 3750),
        ("1H2M30S", 3750),
        ("1h30s", 3630),
        ("1h63s", 3663),
    ],
)
def test_valid_duration(value, seconds):
    assert DurationParamType().convert(value, None, None) == seconds


@pytest.mark.parametrize(
    "value",
    [
        "",
        "-3s",
        "3s2m",
        "x1h2m",
        "1hx2m",
        "1h2",
    ],
)
def test_invalid_duration(value):
    with pytest.raises(click.BadParameter):
        assert DurationParamType().convert(value, None, None)


class TestISODateTimeParamType:
    @pytest.mark.parametrize(
        "value",
        [
            "2023-03-25T23:33:55+00:00",
            "2023-03-25T20:33:55-03:00",
            "2023-03-25T20:33:55-03",
            "2023-03-25T23:33:55Z",
            "20230325T203355-0300",
            "20230325T203355-03",
            "20230325T233355Z",
        ],
    )
    def test_convert_date_in_basic_and_extended_formats(self, value: str):
        expected_datetime = datetime.fromisoformat("2023-03-25T23:33:55+00:00")
        assert expected_datetime == ISODateTimeParamType().convert(value, None, None)

    @pytest.mark.parametrize(
        "value",
        [
            "2023-03-25T23:33:55.001Z",
            "2023-03-25T23:33:55,001Z",
        ],
    )
    def test_convert_date_with_milliseconds_precision(self, value: str):
        expected_datetime = datetime.fromisoformat("2023-03-25T23:33:55.001+00:00")
        assert expected_datetime == ISODateTimeParamType().convert(value, None, None)

    def test_convert_date_without_timezone_offset(self):
        local_utc_offset = datetime.now().astimezone().strftime("%z")
        expected_datetime = datetime.fromisoformat(
            f"2023-03-25T23:33:55{local_utc_offset}"
        )
        actual_datetime = ISODateTimeParamType().convert(
            "2023-03-25T23:33:55", None, None
        )
        assert expected_datetime.timestamp() == actual_datetime.timestamp()

    def test_bad_isodatetime_parameter(self):
        with pytest.raises(click.exceptions.BadParameter):
            ISODateTimeParamType().convert("fail", None, None)


def test_none_format_spec():
    spec_type = FormatSpecType.AUDIO
    assert FormatSpecParamType(spec_type).convert("none", None, None) == None
    assert FormatSpecParamType(spec_type).convert("", None, None) == None


def test_format_spec_without_function():
    expected = "mime_type contains audio and [format eq mp4]"
    actual = FormatSpecParamType(FormatSpecType.AUDIO).convert(
        "format eq mp4", None, None
    )
    assert expected == actual


def test_format_spec_with_function():
    expected = "function(mime_type contains audio and [format eq mp4])"
    actual = FormatSpecParamType(FormatSpecType.AUDIO).convert(
        "function(format eq mp4)", None, None
    )
    assert expected == actual


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
                datetime(2024, 1, 2, 10, 20),
                datetime(2024, 1, 2, 10, 20, 30),
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
    ],
)
def test_input_rewind_interval(value: str, expected):
    assert expected == RewindIntervalParamType().convert(value, None, None)


@pytest.mark.parametrize(
    "value,expected",
    [
        (
            "20240102T102000/T25M",
            (datetime(2024, 1, 2, 10, 20), (datetime(2024, 1, 2, 10, 25))),
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
            (datetime(2023, 12, 31, 10, 25, 30), (datetime(2024, 1, 2, 10, 20, 30))),
        ),
    ],
)
def test_input_rewind_interval_with_lettered_end(value: str, expected):
    assert expected == RewindIntervalParamType().convert(value, None, None)


@pytest.mark.parametrize(
    "value,expected",
    [
        (
            "10:25/10:35",
            (
                FakeDatetime(2024, 1, 2, 10, 25, tzinfo=tzlocal()),
                FakeDatetime(2024, 1, 2, 10, 35, tzinfo=tzlocal()),
            ),
        ),
    ],
)
@freeze_time("2024-01-02T10:20:30-01")
def test_input_rewind_interval_with_time_of_today(value: str, expected):
    assert expected == RewindIntervalParamType().convert(value, None, None)
