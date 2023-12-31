from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import responses

from ytpb.config import DEFAULT_CONFIG
from ytpb.exceptions import BadCommandArgument, YtpbError
from ytpb.types import ConfigMap
from ytpb.utils.date import (
    build_style_parameters_from_spec,
    DurationFormatPattern,
    express_timedelta_in_words,
    format_duration,
    format_iso_datetime,
    format_iso_duration,
    format_timedelta,
    ISO8601DateStyleParameters,
)
from ytpb.utils.path import (
    adjust_title_for_filename,
    compose_excerpt_filename,
    expand_template_output_path,
    format_title_for_filename,
    TitleAllowedCharacters,
)
from ytpb.utils.remote import request_reference_sequence

from ytpb.utils.url import (
    extract_media_type_from_url,
    extract_parameter_from_url,
    normalize_video_url,
)


def test_extract_itag_from_url(audio_base_url):
    assert extract_parameter_from_url("itag", audio_base_url) == "140"


def test_extract_mime_type_from_url(audio_base_url):
    assert extract_media_type_from_url(audio_base_url) == ("audio", "mp4")


def test_request_reference_sequence(
    mocked_responses: responses.RequestsMock,
    audio_base_url: str,
) -> None:
    mocked_responses.head(audio_base_url, headers={"X-Head-Seqnum": "123"})
    assert request_reference_sequence(audio_base_url) == 123


def test_request_reference_sequence_with_missing_header_value(
    mocked_responses: responses.RequestsMock,
    audio_base_url: str,
) -> None:
    mocked_responses.head(audio_base_url, headers={})

    with pytest.raises(YtpbError):
        request_reference_sequence(audio_base_url)


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
            ISO8601DateStyleParameters(format="extended", precision="complete"),
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
            ISO8601DateStyleParameters(format="extended", precision="reduced"),
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
            ISO8601DateStyleParameters(format="basic", precision="complete"),
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
            ISO8601DateStyleParameters(format="basic", precision="reduced"),
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
            ISO8601DateStyleParameters(
                format=basic_or_extended, offset_format=offset_format
            ),
        )

    def test_use_z_for_utc(self):
        assert "20230809T102030Z" == format_iso_datetime(
            datetime.fromisoformat("2023-08-09T10:20:30+00:00"),
            ISO8601DateStyleParameters(use_z_for_utc=True),
        )
        assert "20230809T102030+01" == format_iso_datetime(
            datetime.fromisoformat("2023-08-09T10:20:30+01:00"),
            ISO8601DateStyleParameters(use_z_for_utc=True),
        )
        assert "20230809T102030+00" == format_iso_datetime(
            datetime.fromisoformat("2023-08-09T10:20:30+00:00"),
            ISO8601DateStyleParameters(use_z_for_utc=False),
        )

    def test_raise_with_naive_datetime(self):
        with pytest.raises(ValueError):
            format_iso_datetime(
                datetime.now(),
            )

    def test_raise_with_invalid_argument(self):
        with pytest.raises(ValueError):
            format_iso_datetime(
                datetime.now(timezone.utc), ISO8601DateStyleParameters(format="invalid")
            )
        with pytest.raises(ValueError):
            format_iso_datetime(
                datetime.now(timezone.utc),
                ISO8601DateStyleParameters(precision="invalid"),
            )
        with pytest.raises(ValueError):
            format_iso_datetime(
                datetime.now(timezone.utc),
                ISO8601DateStyleParameters(offset_format="invalid"),
            )


@pytest.mark.parametrize(
    "duration,expected",
    [
        (timedelta(seconds=0), "PT0S"),
        (timedelta(seconds=0.1), "PT0S"),
        (timedelta(seconds=0.5), "PT1S"),
        (timedelta(minutes=1), "PT1M"),
        (timedelta(hours=1), "PT1H"),
        (timedelta(hours=1, minutes=2, seconds=0), "PT1H2M"),
        (timedelta(hours=1, minutes=2, seconds=3), "PT1H2M3S"),
        (timedelta(hours=1, minutes=0, seconds=3), "PT1H3S"),
        (timedelta(hours=0, minutes=2, seconds=3), "PT2M3S"),
    ],
)
def test_format_iso_duration(duration, expected):
    assert expected == format_iso_duration(duration)


@pytest.mark.parametrize(
    "delta,expected",
    [
        (timedelta(hours=1), "PT1H"),
        (timedelta(hours=1, minutes=2), "PT1H2M"),
        (timedelta(hours=1, minutes=2, seconds=3), "PT1H2M3S"),
        (timedelta(hours=0, minutes=2, seconds=3), "PT2M3S"),
        (timedelta(hours=0, minutes=0, seconds=3), "PT3S"),
        (timedelta(hours=1, minutes=0, seconds=3), "PT1H3S"),
    ],
)
def test_format_duration(delta, expected: str):
    assert expected == format_duration(delta, DurationFormatPattern.ISO8601)


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
    "title,expected",
    [
        (
            "FRANCE 24 — EN DIRECT — Info et actualités internationales en continu 24h/24",  # noqa: E501
            "FRANCE 24 — EN DIRECT — Info et actualités internationales en continu 24h-24",  # noqa: E501
        ),
        (
            "🛑 LE JOURNAL TÉLÉVISÉ DE 20H - VENDREDI 24 NOVEMBRE 2023",
            "🛑 LE JOURNAL TÉLÉVISÉ DE 20H - VENDREDI 24 NOVEMBRE 2023",
        ),
        (
            "【LIVE】新宿駅前の様子 Shinjuku, Tokyo JAPAN【ライブカメラ】 | TBS NEWS DIG",  # noqa: E501
            "【LIVE】新宿駅前の様子 Shinjuku, Tokyo JAPAN【ライブカメラ】 | TBS NEWS DIG",  # noqa: E501
        ),
    ],
)
def test_adjust_title_for_filename_as_is(title, expected):
    assert expected == adjust_title_for_filename(title, separator=None, max_length=None)


@pytest.mark.parametrize(
    "title,expected",
    [
        (
            "FRANCE 24 — EN DIRECT — Info et actualités internationales en continu 24h/24",  # noqa: E501
            "FRANCE-24—EN-DIRECT—Info-et-actualités-internationales-en-continu-24h-24",
        ),
        (
            "🛑 LE JOURNAL TÉLÉVISÉ DE 20H - VENDREDI 24 NOVEMBRE 2023",
            "🛑-LE-JOURNAL-TÉLÉVISÉ-DE-20H-VENDREDI-24-NOVEMBRE-2023",
        ),
        (
            "【LIVE】新宿駅前の様子 Shinjuku, Tokyo JAPAN【ライブカメラ】 | TBS NEWS DIG",  # noqa: E501
            "【LIVE】新宿駅前の様子-Shinjuku,-Tokyo-JAPAN【ライブカメラ】-|-TBS-NEWS-DIG",  # noqa: E501
        ),
    ],
)
def test_adjust_title_for_filename_with_separator(title, expected):
    assert expected == adjust_title_for_filename(title, separator="-", max_length=None)


@pytest.mark.parametrize(
    "title,expected",
    [
        (
            "FRANCE 24 — EN DIRECT — Info et actualités internationales en continu 24h/24",  # noqa: E501
            "FRANCE 24 -- EN DIRECT -- Info et actualites internationales en continu 24h-24",  # noqa: E501
        ),
        (
            "🛑 LE JOURNAL TÉLÉVISÉ DE 20H - VENDREDI 24 NOVEMBRE 2023",
            "LE JOURNAL TELEVISE DE 20H - VENDREDI 24 NOVEMBRE 2023",
        ),
        (
            "【LIVE】新宿駅前の様子 Shinjuku, Tokyo JAPAN【ライブカメラ】 | TBS NEWS DIG",  # noqa: E501
            "[(LIVE)] Xin Su Yi Qian noYang Zi Shinjuku, Tokyo JAPAN[(raibukamera)] | TBS NEWS DIG",  # noqa: E501
        ),
    ],
)
def test_adjust_title_for_filename_with_ascii_and_no_separator(title, expected):
    assert expected == adjust_title_for_filename(
        title, separator=None, max_length=None, characters=TitleAllowedCharacters.ASCII
    )


@pytest.mark.parametrize(
    "title,expected",
    [
        (
            "FRANCE 24 — EN DIRECT — Info et actualités internationales en continu 24h/24",  # noqa: E501
            "FRANCE-24--EN-DIRECT--Info-et-actualites-internationales-en-continu-24h-24",  # noqa: E501
        ),
        (
            "🛑 LE JOURNAL TÉLÉVISÉ DE 20H - VENDREDI 24 NOVEMBRE 2023",
            "LE-JOURNAL-TELEVISE-DE-20H-VENDREDI-24-NOVEMBRE-2023",
        ),
        (
            "【LIVE】新宿駅前の様子 Shinjuku, Tokyo JAPAN【ライブカメラ】 | TBS NEWS DIG",  # noqa: E501
            "[(LIVE)]-Xin-Su-Yi-Qian-noYang-Zi-Shinjuku,-Tokyo-JAPAN[(raibukamera)]-|-TBS-NEWS-DIG",  # noqa: E501
        ),
    ],
)
def test_adjust_title_for_filename_with_ascii_and_separator(title, expected):
    assert expected == adjust_title_for_filename(
        title, separator="-", max_length=None, characters=TitleAllowedCharacters.ASCII
    )


@pytest.mark.parametrize(
    "title,expected,separator",
    [
        (
            "Jackman Maine - Newton Field Airport - Cam Left",
            "Jackman-Maine-Newton-Field-Airport-Cam-Left",
            "-",
        ),
        (
            "Jackman Maine -  Newton Field Airport  -  Cam Left",
            "Jackman-Maine-Newton-Field-Airport-Cam-Left",
            "-",
        ),
        (
            "Jackman Maine —  Newton Field Airport - Cam Left",
            "Jackman-Maine--Newton-Field-Airport-Cam-Left",
            "-",
        ),
        (
            "Jackman Maine - Newton Field Airport - Cam Left",
            "Jackman_Maine-Newton_Field_Airport-Cam_Left",
            "_",
        ),
        (
            "Jackman Maine -  Newton Field Airport  -  Cam Left",
            "Jackman_Maine-Newton_Field_Airport-Cam_Left",
            "_",
        ),
        (
            "Jackman Maine —  Newton Field Airport - Cam Left",
            "Jackman_Maine--Newton_Field_Airport-Cam_Left",
            "_",
        ),
    ],
)
def test_corner_cases_of_adjust_title_for_filename(title, expected, separator):
    assert expected == adjust_title_for_filename(
        title, separator=separator, characters=TitleAllowedCharacters.ASCII
    )
    assert expected == adjust_title_for_filename(
        title, separator=separator, characters=TitleAllowedCharacters.POSIX
    )


def test_adjust_title_for_filename_with_posix():
    title = "【LIVE】新宿駅前の様子 Shinjuku, Tokyo JAPAN | TBS NEWS DIG"

    expected = "LIVE-Xin-Su-Yi-Qian-noYang-Zi-Shinjuku-Tokyo-JAPAN-TBS-NEWS-DIG"
    assert expected == adjust_title_for_filename(
        title, separator=None, max_length=None, characters=TitleAllowedCharacters.POSIX
    )

    expected = "LIVE_Xin_Su_Yi_Qian_noYang_Zi_Shinjuku_Tokyo_JAPAN_TBS_NEWS_DIG"
    assert expected == adjust_title_for_filename(
        title, separator="_", max_length=None, characters=TitleAllowedCharacters.POSIX
    )

    expected = "LIVE-Xin-Su-Yi-Qian-noYang-Zi-Shinjuku-Tokyo-JAPAN-TBS-NEWS-DIG"
    assert expected == adjust_title_for_filename(
        title, separator="*", max_length=None, characters=TitleAllowedCharacters.POSIX
    )


@pytest.mark.parametrize(
    "title,expected,max_length",
    [
        (  # 1                                        42
            "FRANCE 24 — EN DIRECT — Info et actualités",
            "FRANCE 24 — EN DIRECT — Info et actualités",
            42,
        ),
        (  # 1                   21
            "FRANCE 24 — EN DIRECT — Info et actualités",
            "FRANCE 24 — EN DIRECT",
            21,
        ),
        (  # 1                  20
            "FRANCE 24 — EN DIRECT — Info et actualités",
            "FRANCE 24 — EN",
            20,
        ),
        (  # 1           13
            "FRANCE 24 — EN DIRECT — Info et actualités",
            "FRANCE 24",
            13,
        ),
    ],
)
def test_adjust_title_for_filename_with_max_length(title, expected, max_length):
    assert expected == adjust_title_for_filename(
        title, separator=None, max_length=max_length
    )


@pytest.mark.parametrize(
    "title,expected,max_length",
    [
        (
            "FRANCE 24—EN DIRECT—Info et actualités",
            #  1                        26
            # "FRANCE-24--EN-DIRECT--Info-et-actualités",
            "FRANCE-24--EN-DIRECT--Info",
            26,
        ),
        (
            "FRANCE 24—EN DIRECT—Info et actualités",
            #  1                       24
            # "FRANCE-24--EN-DIRECT--Info-et-actualités",
            "FRANCE-24--EN-DIRECT",
            24,
        ),
    ],
)
def test_adjust_title_for_filename_with_max_length_and_separator(
    title, expected, max_length
):
    assert expected == adjust_title_for_filename(
        title,
        separator="-",
        max_length=max_length,
        characters=TitleAllowedCharacters.ASCII,
    )


def test_format_title_for_filename_with_original_style():
    title = "【LIVE】新宿駅前の様子 Shinjuku, Tokyo JAPAN | TBS NEWS DIG"
    assert title == format_title_for_filename(title, style="original")
    assert title == format_title_for_filename(
        title, style="original", separator="-", lowercase=True
    )


@pytest.mark.parametrize(
    "title,expected,characters",
    [
        (
            "【LIVE】新宿駅前の様子 Shinjuku, Tokyo JAPAN | TBS NEWS DIG",
            "【LIVE】新宿駅前の様子 Shinjuku, Tokyo JAPAN | TBS NEWS DIG",
            TitleAllowedCharacters.UNICODE,
        ),
        (
            "【LIVE】新宿駅前の様子 Shinjuku, Tokyo JAPAN | TBS NEWS DIG",
            "[(LIVE)] Xin Su Yi Qian noYang Zi Shinjuku, Tokyo JAPAN | TBS NEWS DIG",
            TitleAllowedCharacters.ASCII,
        ),
        (
            "【LIVE】新宿駅前の様子 Shinjuku, Tokyo JAPAN | TBS NEWS DIG",
            "LIVE-Xin-Su-Yi-Qian-noYang-Zi-Shinjuku-Tokyo-JAPAN-TBS-NEWS-DIG",
            TitleAllowedCharacters.POSIX,
        ),
    ],
)
def test_format_title_for_filename_with_characters(title, expected, characters):
    assert expected == format_title_for_filename(
        title, style="custom", characters=characters
    )


class TestComposeExcerptOutputStem:
    prefix = "test"

    def test_without_postfix(self):
        assert "test_20230809T102030+00" == compose_excerpt_filename(
            self.prefix,
            datetime.fromisoformat("20230809T102030+00"),
        )

    def test_with_end_date_postfix(self):
        assert "test_20230809T102030+00_20230809T102034+00" == compose_excerpt_filename(
            self.prefix,
            datetime.fromisoformat("20230809T102030+00"),
            datetime.fromisoformat("20230809T102034+00"),
            duration_or_range="range",
        )

    def test_with_duration_postfix(self):
        assert "test_20230809T102030+00_PT4S" == compose_excerpt_filename(
            self.prefix,
            datetime.fromisoformat("20230809T102030+00"),
            datetime.fromisoformat("20230809T102034+00"),
            duration_or_range="duration",
        )

    def test_with_date_with_milliseconds(self):
        date = datetime.fromisoformat("20230809T102030+00")
        assert "test_20230809T102030+00" == compose_excerpt_filename(
            self.prefix,
            date.replace(microsecond=123_000),
        )
        assert "test_20230809T102030+00" == compose_excerpt_filename(
            self.prefix,
            date.replace(microsecond=789_000),
        )


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
        expected = ISO8601DateStyleParameters(
            format="extended",
        )
        assert expected == build_style_parameters_from_spec("extended")

    @pytest.mark.parametrize("spec", ["extended,complete", "extended, complete"])
    def test_parse_date_styles(self, spec):
        expected = ISO8601DateStyleParameters(
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
        assert None == build_style_parameters_from_spec("")
        assert None == build_style_parameters_from_spec(None)


@pytest.mark.parametrize(
    "stream_url_or_id",
    [
        "https://www.youtube.com/watch?v=kHwmzef842g",
        "https://www.youtube.com/watch?v=kHwmzef842g&param=value",
        "https://www.youtu.be/kHwmzef842g",
        "kHwmzef842g",
    ],
)
def test_normalize_video_url(stream_url_or_id):
    expected = "https://www.youtube.com/watch?v=kHwmzef842g"
    assert expected == normalize_video_url(stream_url_or_id)


@pytest.mark.parametrize(
    "stream_url_or_id",
    [
        "https://www.youtube.com/watch?v=kHwmzef842gxxx",
        "https://www.youtube.com/watch?v=kHwmzef",
        "https://www.youtu.be/kHwmzef842gxxx",
        "kHwmzef842gxxx",
        "kHwmzef",
    ],
)
def test_failed_normalize_video_url(stream_url_or_id):
    with pytest.raises(BadCommandArgument):
        normalize_video_url(stream_url_or_id)
