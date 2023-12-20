from pathlib import Path

import pytest

from ytpb.ffmpeg import ffprobe_show_entries


def assert_number_of_streams(filepath: Path, expected: int):
    assert ffprobe_show_entries(filepath, "format=nb_streams") == str(expected)


def assert_approx_duration(filepath: Path, expected: float, abs: float = 2.2e-2):
    actual = float(ffprobe_show_entries(filepath, "format=duration"))
    approx_expected = pytest.approx(expected, abs=abs)
    if actual != approx_expected:
        raise AssertionError(
            f"Durations are not almost equal\n"
            f" - expected: {approx_expected}\n"
            f" + actual: {actual}"
        )
