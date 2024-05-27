import pytest

from ytpb.cli.utils.path import adjust_for_filename, AllowedCharacters


@pytest.mark.parametrize(
    "title,expected",
    [
        (
            "En direct : Titre de  la   vidéo — 24h/7 | Panorama, 360 / ? ",
            "En direct Titre de la vidéo — 24h-7 - Panorama, 360",
        ),
        (
            "【LIVE】新宿駅前の様子 Shinjuku, Tokyo JAPAN【ライブカメラ】 | TBS NEWS DIG",  # noqa: E501
            "【LIVE】新宿駅前の様子 Shinjuku, Tokyo JAPAN【ライブカメラ】 - TBS NEWS DIG",  # noqa: E501
        ),
    ],
)
def test_adjust_for_filename_as_is(title, expected):
    assert expected == adjust_for_filename(title, length=255)


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
def test_adjust_for_filename_with_separator(title, expected):
    assert expected == adjust_for_filename(title, separator="-", length=255)


@pytest.mark.parametrize(
    "title,expected",
    [
        (
            "En direct : Titre de  la   vidéo — 24h/7 | Panorama, 360 / ? ",
            "EndirectTitredelavideo--24h-7-Panorama,360",
        )
    ],
)
def test_adjust_for_filename_with_ascii_and_empty_separator(title, expected):
    assert expected == adjust_for_filename(
        title, separator="", length=255, characters=AllowedCharacters.ASCII
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
def test_adjust_for_filename_with_ascii_and_whitespace_separator(title, expected):
    assert expected == adjust_for_filename(
        title, separator=" ", length=255, characters=AllowedCharacters.ASCII
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
            "[(LIVE)]-Xin-Su-Yi-Qian-noYang-Zi--Shinjuku,-Tokyo-JAPAN[(raibukamera)]-TBS-NEWS-DIG",  # noqa: E501
        ),
    ],
)
def test_adjust_for_filename_with_ascii_and_separator(title, expected):
    assert expected == adjust_for_filename(
        title, separator="-", length=255, characters=AllowedCharacters.ASCII
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
            "Jackman Maine — Newton Field Airport - Cam Left",
            "Jackman_Maine--Newton_Field_Airport-Cam_Left",
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


def test_adjust_for_filename_with_posix():
    title = "【LIVE】新宿駅前の様子 Shinjuku, Tokyo JAPAN | TBS NEWS DIG"

    expected = "LIVE_Xin_Su_Yi_Qian_noYang_Zi_Shinjuku_Tokyo_JAPAN-TBS_NEWS_DIG"
    assert expected == adjust_for_filename(
        title, separator="_", length=255, characters=AllowedCharacters.POSIX
    )

    expected = "LIVE-Xin-Su-Yi-Qian-noYang-Zi-Shinjuku-Tokyo-JAPAN-TBS-NEWS-DIG"
    assert expected == adjust_for_filename(
        title, separator="*", length=255, characters=AllowedCharacters.POSIX
    )


@pytest.mark.parametrize(
    "title,expected,length",
    [
        (
            "En direct : Titre de la vidéo",
            #  1              16
            # "En direct : Titre de la vidéo"
            "En_direct_Titre",
            16,
        ),
        (
            "En direct : Titre de la vidéo",
            #  1          12
            # "En direct : Titre de la vidéo"
            "En_direct",
            12,
        ),
    ],
)
def test_adjust_for_filename_with_length_and_separator(title, expected, length):
    assert expected == adjust_for_filename(
        title,
        separator="_",
        length=length,
        characters=AllowedCharacters.ASCII,
    )
