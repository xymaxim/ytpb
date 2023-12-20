from datetime import datetime

import click
import pytest

from ytpb.cli.parameters import (
    DurationParamType,
    FormatSpecParamType,
    FormatSpecType,
    ISODateTimeParamType,
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
