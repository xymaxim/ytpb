from datetime import datetime, timedelta, timezone

import pytest

from ytpb.cli.utils.date import (
    build_style_parameters_from_spec,
    DurationFormatPattern,
    express_timedelta_in_words,
    format_duration,
    format_iso_datetime,
    format_timedelta,
    ISODateStyleParameters,
)


class TestFormatDatetime:
    @pytest.mark.parametrize(
        "date,expected",
        [
            ("2023-08-09T10+01:00", "2023-08-09T10:00:00+01"),
            ("2023-08-09T10:20+01:00", "2023-08-09T10:20:00+01"),
            ("2023-08-09T10:20:30+01:00", "2023-08-09T10:20:30+01"),
            ("2023-08-09T10:00:00.123+01:00", "2023-08-09T10:00:00+01"),
        ],
    )
    def test_extended_format_and_complete_precision(self, date, expected):
        assert expected == format_iso_datetime(
            datetime.fromisoformat(date),
            ISODateStyleParameters(format="extended", precision="complete"),
        )

    @pytest.mark.parametrize(
        "date,expected",
        [
            ("2023-08-09T00+01:00", "2023-08-09T00+01"),
            ("2023-08-09T10+01:00", "2023-08-09T10+01"),
            ("2023-08-09T10:20+01:00", "2023-08-09T10:20+01"),
            ("2023-08-09T10:20:30+01:00", "2023-08-09T10:20:30+01"),
            ("2023-08-09T10:00:00.123+01:00", "2023-08-09T10:00:00+01"),
        ],
    )
    def test_extended_format_and_reduced_precision(self, date, expected):
        assert expected == format_iso_datetime(
            datetime.fromisoformat(date),
            ISODateStyleParameters(format="extended", precision="reduced"),
        )

    @pytest.mark.parametrize(
        "date,expected",
        [
            ("2023-08-09T10+01:00", "20230809T100000+01"),
            ("2023-08-09T10:20+01:00", "20230809T102000+01"),
            ("2023-08-09T10:20:30+01:00", "20230809T102030+01"),
            ("2023-08-09T10:00:00.123+01:00", "20230809T100000+01"),
        ],
    )
    def test_basic_format_and_complete_precision(self, date, expected):
        assert expected == format_iso_datetime(
            datetime.fromisoformat(date),
            ISODateStyleParameters(format="basic", precision="complete"),
        )

    @pytest.mark.parametrize(
        "date,expected",
        [
            ("2023-08-09T10+01:00", "20230809T10+01"),
            ("2023-08-09T10:20+01:00", "20230809T1020+01"),
            ("2023-08-09T10:20:30+01:00", "20230809T102030+01"),
            ("2023-08-09T10:00:00.123+01:00", "20230809T100000+01"),
        ],
    )
    def test_basic_format_and_reduced_precision(self, date, expected):
        assert expected == format_iso_datetime(
            datetime.fromisoformat(date),
            ISODateStyleParameters(format="basic", precision="reduced"),
        )

    @pytest.mark.parametrize(
        "basic_or_extended,offset_format,expected",
        [
            ("basic", "hh", "20230809T102030+01"),
            ("basic", "hhmm", "20230809T102030+0100"),
            ("extended", "hh", "2023-08-09T10:20:30+01"),
            ("extended", "hhmm", "2023-08-09T10:20:30+01:00"),
        ],
    )
    def test_utc_offset_formats(self, basic_or_extended, offset_format, expected):
        assert expected == format_iso_datetime(
            datetime.fromisoformat("2023-08-09T10:20:30+01:00"),
            ISODateStyleParameters(
                format=basic_or_extended, offset_format=offset_format
            ),
        )

    def test_use_z_for_utc(self):
        assert "20230809T102030Z" == format_iso_datetime(
            datetime.fromisoformat("2023-08-09T10:20:30+00:00"),
            ISODateStyleParameters(use_z_for_utc=True),
        )
        assert "20230809T102030+01" == format_iso_datetime(
            datetime.fromisoformat("2023-08-09T10:20:30+01:00"),
            ISODateStyleParameters(use_z_for_utc=True),
        )
        assert "20230809T102030+00" == format_iso_datetime(
            datetime.fromisoformat("2023-08-09T10:20:30+00:00"),
            ISODateStyleParameters(use_z_for_utc=False),
        )

    def test_raise_with_naive_datetime(self):
        with pytest.raises(ValueError):
            format_iso_datetime(
                datetime.now(),
            )

    def test_raise_with_invalid_argument(self):
        with pytest.raises(ValueError):
            format_iso_datetime(
                datetime.now(timezone.utc), ISODateStyleParameters(format="invalid")
            )
        with pytest.raises(ValueError):
            format_iso_datetime(
                datetime.now(timezone.utc),
                ISODateStyleParameters(precision="invalid"),
            )
        with pytest.raises(ValueError):
            format_iso_datetime(
                datetime.now(timezone.utc),
                ISODateStyleParameters(offset_format="invalid"),
            )


class TestFormatDuration:
    @pytest.mark.parametrize(
        "duration,expected",
        [
            (timedelta(hours=1), "PT1H"),
            (timedelta(hours=1, minutes=2), "PT1H2M"),
            (
                timedelta(hours=1, minutes=2, seconds=30),
                "PT1H2M30S",
            ),
            (timedelta(hours=0, minutes=2, seconds=30), "PT2M30S"),
            (
                timedelta(hours=0, minutes=0, seconds=30),
                "PT30S",
            ),
            (timedelta(hours=0, minutes=0, seconds=30.123), "PT30S"),
            (timedelta(hours=1, minutes=0, seconds=30), "PT1H30S"),
            (timedelta(seconds=123), "PT2M3S"),
        ],
    )
    def test_iso_pattern(self, duration: timedelta, expected: str):
        assert expected == format_duration(duration, DurationFormatPattern.ISO)

    @pytest.mark.parametrize(
        "duration,expected",
        [
            (timedelta(hours=1), "01:00:00"),
            (timedelta(hours=1, minutes=2), "01:02:00"),
            (
                timedelta(hours=1, minutes=2, seconds=30),
                "01:02:30",
            ),
            (timedelta(hours=0, minutes=2, seconds=30), "00:02:30"),
            (
                timedelta(hours=0, minutes=0, seconds=30),
                "00:00:30",
            ),
            (timedelta(hours=0, minutes=0, seconds=30.123), "00:00:30"),
            (timedelta(hours=1, minutes=0, seconds=30), "01:00:30"),
            (timedelta(seconds=123), "00:02:03"),
        ],
    )
    def test_numeric_pattern(self, duration: timedelta, expected: str):
        assert expected == format_duration(duration, DurationFormatPattern.NUMERIC)

    @pytest.mark.parametrize(
        "duration,expected",
        [
            (timedelta(hours=1), "1 h"),
            (timedelta(hours=1, minutes=2), "1 h 2 m"),
            (
                timedelta(hours=1, minutes=2, seconds=30),
                "1 h 2 m 30 s",
            ),
            (timedelta(hours=0, minutes=2, seconds=30), "2 m 30 s"),
            (
                timedelta(hours=0, minutes=0, seconds=30),
                "30 s",
            ),
            (timedelta(hours=0, minutes=0, seconds=30.123), "30 s"),
            (timedelta(hours=1, minutes=0, seconds=30), "1 h 30 s"),
            (timedelta(seconds=123), "2 m 3 s"),
        ],
    )
    def test_sentence_pattern(self, duration: timedelta, expected: str):
        assert expected == format_duration(duration, DurationFormatPattern.SENTENCE)

    @pytest.mark.parametrize(
        "duration,expected",
        [
            (timedelta(hours=1), "1h"),
            (timedelta(hours=1, minutes=2), "1h2m"),
            (
                timedelta(hours=1, minutes=2, seconds=30),
                "1h2m30s",
            ),
            (timedelta(hours=0, minutes=2, seconds=30), "2m30s"),
            (
                timedelta(hours=0, minutes=0, seconds=30),
                "30s",
            ),
            (timedelta(hours=0, minutes=0, seconds=30.123), "30s"),
            (timedelta(hours=1, minutes=0, seconds=30), "1h30s"),
            (timedelta(seconds=123), "2m3s"),
        ],
    )
    def test_hms_pattern(self, duration: timedelta, expected: str):
        assert expected == format_duration(duration, DurationFormatPattern.HMS)


@pytest.mark.parametrize(
    "delta,expected",
    [
        (timedelta(hours=1), "an hour"),
        (timedelta(hours=1, minutes=14), "an hour"),
        (timedelta(hours=1, minutes=15), "1.5 hours"),
        (timedelta(hours=1, minutes=44), "1.5 hours"),
        (timedelta(hours=1, minutes=45), "2 hours"),
        (timedelta(hours=1, minutes=44, seconds=30), "2 hours"),
        (timedelta(minutes=1), "a minute"),
        (timedelta(minutes=45), "an hour"),
        (timedelta(minutes=44), "44 minutes"),
        (timedelta(minutes=44, seconds=29), "44 minutes"),
        (timedelta(minutes=44, seconds=30), "an hour"),
        (timedelta(seconds=45), "less than a minute"),
        (timedelta(seconds=10), "a moment"),
    ],
)
def test_express_timedelta_in_words(delta, expected):
    assert expected == express_timedelta_in_words(delta)


@pytest.mark.parametrize(
    "duration,expected",
    [
        (timedelta(seconds=0), "+00:00"),
        (timedelta(seconds=1.123), "+00:01"),
        (timedelta(seconds=-1.123), "-00:01"),
        (timedelta(seconds=121.100), "+02:01"),
        (timedelta(hours=1, seconds=3), "+01:00:03"),
    ],
)
def test_format_timedelta(duration, expected):
    result = format_timedelta(duration, use_ms_precision=False)
    assert result == expected


@pytest.mark.parametrize(
    "duration,expected",
    [
        (timedelta(seconds=0), "+00:00.000"),
        (timedelta(seconds=0.1), "+00:00.100"),
        (timedelta(seconds=1.123789), "+00:01.124"),
    ],
)
def test_format_timedelta_with_ms_precision(duration, expected):
    result = format_timedelta(duration, use_ms_precision=True)
    assert result == expected


class TestBuildStyleParametersFromSpec:
    def test_parse_single_date_style(self):
        expected = ISODateStyleParameters(
            format="extended",
        )
        assert expected == build_style_parameters_from_spec("extended")

    @pytest.mark.parametrize("spec", ["extended,complete", "extended, complete"])
    def test_parse_date_styles(self, spec):
        expected = ISODateStyleParameters(
            format="extended",
            precision="complete",
        )
        assert expected == build_style_parameters_from_spec(spec)

    def test_mutually_exlusive_styles(self):
        with pytest.raises(ValueError) as exc_info:
            build_style_parameters_from_spec("basic,extended")
        message = "Mutually exclusive styles provided: 'basic' and 'extended'"
        assert message == str(exc_info.value)

    def test_unknown_styles(self):
        with pytest.warns() as record:
            build_style_parameters_from_spec("unknown")
        assert str(record[0].message) == "Ignoring unknown style(s): unknown"

        with pytest.warns() as record:
            build_style_parameters_from_spec("unknown,invalid")
        assert str(record[0].message) == "Ignoring unknown style(s): invalid, unknown"

    def test_empty_or_none_style(self):
        assert None is build_style_parameters_from_spec("")
        assert None is build_style_parameters_from_spec(None)
