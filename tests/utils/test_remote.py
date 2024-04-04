import pytest
import responses

from ytpb.errors import YtpbError
from ytpb.utils.remote import request_reference_sequence


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
