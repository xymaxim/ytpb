from datetime import timezone
from pathlib import Path

import av
import pytest


def assert_number_of_streams(file_path: Path, expected: int):
    with av.open(file_path) as container:
        assert len(container.streams) == expected


def assert_approx_duration(file_path: Path, expected: float, abs: float = 2.2e-2):
    with av.open(file_path) as container:
        actual = container.duration / 1e6

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
