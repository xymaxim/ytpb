import pytest

from ytpb.cli.utils.path import adjust_for_filename, AllowedCharacters


@pytest.mark.parametrize(
    "title,expected",
    [
        (
            "En direct : Titre de  la   vidéo — 24h/7 | Panorama, 360 / ? ",
            "En direct  Titre de  la   vidéo — 24h-7 - Panorama, 360",
        ),
        (
            "【LIVE】新宿駅前の様子 Shinjuku, Tokyo JAPAN【ライブカメラ】 | TBS NEWS DIG",  # noqa: E501
            "【LIVE】新宿駅前の様子 Shinjuku, Tokyo JAPAN【ライブカメラ】 - TBS NEWS DIG",  # noqa: E501
        ),
    ],
)
def test_adjust_title_for_filename_as_is(title, expected):
    assert expected == adjust_for_filename(title, separator=None, length=None)


@pytest.mark.parametrize(
    "title,expected",
    [
        (
            "En direct : Titre de  la   vidéo — 24h/7 | Panorama, 360 / ? ",
            "En-direct-Titre-de-la-vidéo—24h-7-Panorama,-360",
        ),
        (
            "【LIVE】新宿駅前の様子 Shinjuku, Tokyo JAPAN【ライブカメラ】 | TBS NEWS DIG",  # noqa: E501
            "【LIVE】新宿駅前の様子-Shinjuku,-Tokyo-JAPAN【ライブカメラ】-TBS-NEWS-DIG",  # noqa: E501
        ),
    ],
)
def test_adjust_title_for_filename_with_separator(title, expected):
    assert expected == adjust_for_filename(title, separator="-", length=None)


# def test_lofi():
#     title = "lofi hip hop radio 📚 - beats to relax/study to"
#     assert "lofi-hip-hop-radio--beats-to" == adjust_string_for_filename(title, separator="-", length=30, characters=AllowedCharacters.POSIX)
#     assert "lofi_hip_hop_radio_beats_to" == adjust_string_for_filename(title, separator="_", length=30, characters=AllowedCharacters.POSIX)


@pytest.mark.parametrize(
    "title,expected",
    [
        (
            "En direct Titre de  la   vidéo — 24h/7 | Panorama, 360 / ? ",
            "En direct Titre de  la   video -- 24h-7 - Panorama, 360",
        ),
        (
            "【LIVE】新宿駅前の様子 Shinjuku, Tokyo JAPAN【ライブカメラ】 | TBS NEWS DIG",  # noqa: E501
            "[(LIVE)] Xin Su Yi Qian noYang Zi  Shinjuku, Tokyo JAPAN[(raibukamera)]  - TBS NEWS DIG",  # noqa: E501
        ),
    ],
)
def test_adjust_title_for_filename_with_ascii_and_no_separator(title, expected):
    assert expected == adjust_for_filename(
        title, separator=None, length=None, characters=AllowedCharacters.ASCII
    )


@pytest.mark.parametrize(
    "title,expected",
    [
        (
            "En direct : Titre de  la   vidéo — 24h/7 | Panorama, 360 / ? ",
            "EndirectTitredelavideo--24h-7-Panorama,360",
        )
    ],
)
def test_adjust_title_for_filename_with_ascii_and_empty_separator(title, expected):
    assert expected == adjust_for_filename(
        title, separator="", length=None, characters=AllowedCharacters.ASCII
    )


@pytest.mark.parametrize(
    "title,expected",
    [
        (
            "En direct : Titre de  la   vidéo — 24h/7 | Panorama, 360 / ? ",
            "En direct Titre de la video -- 24h-7 - Panorama, 360",
        )
    ],
)
def test_adjust_title_for_filename_with_ascii_and_whitespace_separator(title, expected):
    assert expected == adjust_for_filename(
        title, separator=" ", length=None, characters=AllowedCharacters.ASCII
    )


@pytest.mark.parametrize(
    "title,expected",
    [
        (
            "En direct : Titre de  la   vidéo — 24h/7 | Panorama, 360 / ? ",
            "En-direct-Titre-de-la-video--24h-7-Panorama,-360",
        ),
        (
            "【LIVE】新宿駅前の様子 Shinjuku, Tokyo JAPAN【ライブカメラ】 | TBS NEWS DIG",  # noqa: E501
            "[(LIVE)]-Xin-Su-Yi-Qian-noYang-Zi-Shinjuku,-Tokyo-JAPAN[(raibukamera)]-TBS-NEWS-DIG",  # noqa: E501
        ),
    ],
)
def test_adjust_title_for_filename_with_ascii_and_separator(title, expected):
    assert expected == adjust_for_filename(
        title, separator="-", length=None, characters=AllowedCharacters.ASCII
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
            "Jackman_Maine_Newton_Field_Airport_Cam_Left",
            "_",
        ),
        (
            "Jackman Maine -  Newton Field Airport  -  Cam Left",
            "Jackman_Maine_Newton_Field_Airport_Cam_Left",
            "_",
        ),
        (
            "Jackman Maine — Newton Field Airport - Cam Left",
            "Jackman_Maine__Newton_Field_Airport_Cam_Left",
            "_",
        ),
    ],
)
def test_corner_cases_of_adjust_title_for_filename(title, expected, separator):
    assert expected == adjust_for_filename(
        title, separator=separator, characters=AllowedCharacters.ASCII
    )
    assert expected == adjust_for_filename(
        title, separator=separator, characters=AllowedCharacters.POSIX
    )


def test_adjust_title_for_filename_with_posix():
    title = "【LIVE】新宿駅前の様子 Shinjuku, Tokyo JAPAN | TBS NEWS DIG"

    expected = "LIVE-Xin-Su-Yi-Qian-noYang-Zi-Shinjuku-Tokyo-JAPAN-TBS-NEWS-DIG"
    assert expected == adjust_for_filename(
        title, separator=None, length=None, characters=AllowedCharacters.POSIX
    )

    expected = "LIVE_Xin_Su_Yi_Qian_noYang_Zi_Shinjuku_Tokyo_JAPAN_TBS_NEWS_DIG"
    assert expected == adjust_for_filename(
        title, separator="_", length=None, characters=AllowedCharacters.POSIX
    )

    expected = "LIVE-Xin-Su-Yi-Qian-noYang-Zi-Shinjuku-Tokyo-JAPAN-TBS-NEWS-DIG"
    assert expected == adjust_for_filename(
        title, separator="*", length=None, characters=AllowedCharacters.POSIX
    )


@pytest.mark.parametrize(
    "title,expected,length",
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
def test_adjust_title_for_filename_with_length(title, expected, length):
    assert expected == adjust_for_filename(title, separator=None, length=length)


@pytest.mark.parametrize(
    "title,expected,length",
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
def test_adjust_title_for_filename_with_length_and_separator(title, expected, length):
    assert expected == adjust_for_filename(
        title,
        separator="-",
        length=length,
        characters=AllowedCharacters.ASCII,
    )
