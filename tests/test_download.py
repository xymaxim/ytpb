import os
from pathlib import Path
from urllib.parse import urljoin

import responses

from ytpb.download import download_segment


def test_download_segment(
    add_responses_callback_for_segment_urls, audio_base_url: str, tmp_path: Path
) -> None:
    # Given:
    add_responses_callback_for_segment_urls(urljoin(audio_base_url, r"sq/\w+"))

    # When:
    output_path = download_segment(7959120, audio_base_url, tmp_path)

    # Then:
    assert output_path == tmp_path / "7959120.i140.mp4"
    assert os.path.exists(output_path)


def test_download_segment_with_custom_output_filename(
    mocked_responses: responses.RequestsMock, audio_base_url: str, tmp_path: Path
) -> None:
    mocked_responses.get(urljoin(audio_base_url, "sq/0"))

    # When:
    output_path = download_segment(0, audio_base_url, tmp_path, "custom")

    # Then:
    assert output_path == tmp_path / "custom"
    assert os.path.exists(output_path)


def test_download_segment_with_custom_callable_output_filename(
    mocked_responses: responses.RequestsMock, audio_base_url: str, tmp_path: Path
) -> None:
    mocked_responses.get(urljoin(audio_base_url, "sq/0"))

    def custom_output_filename(sequence, base_url):
        assert sequence == 0
        assert base_url == audio_base_url
        return "custom"

    # When:
    output_path = download_segment(0, audio_base_url, tmp_path, custom_output_filename)

    # Then:
    assert output_path == tmp_path / "custom"
    assert os.path.exists(output_path)
