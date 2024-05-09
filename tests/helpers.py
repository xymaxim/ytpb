from datetime import timezone
from pathlib import Path

import pytest

from ytpb.utils.av import show_duration, show_number_of_streams


def assert_number_of_streams(file_path: Path, expected: int):
    assert show_number_of_streams(file_path) == expected


def assert_approx_duration(file_path: Path, expected: float, abs: float = 2.2e-2):
    actual = show_duration(file_path, {"video": 0})
    approx_expected = pytest.approx(expected, abs=abs)
    if actual != approx_expected:
        raise AssertionError(
            "Durations are not almost equal\n"
            f" - expected: {approx_expected}\n"
            f" + actual: {actual}"
        )


# See https://github.com/spulec/freezegun/issues/348.
def patched_freezgun_astimezone(self, tz=None):
    from freezegun.api import datetime_to_fakedatetime, real_datetime

    return datetime_to_fakedatetime(
        real_datetime.astimezone(self, timezone(self._tz_offset()))
    )
