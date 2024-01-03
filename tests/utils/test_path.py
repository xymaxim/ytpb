import pytest

from ytpb.utils.path import (
    adjust_title_for_filename,
    format_title_for_filename,
    TitleAllowedCharacters,
)


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
