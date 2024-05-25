import pytest

from ytpb.errors import QueryError
from ytpb.streams import AudioOrVideoStream, AudioStream, Streams


def test_abstract_methods(streams_in_list: list[AudioOrVideoStream]):
    streams = Streams(streams_in_list)

    assert len(streams) == len(streams_in_list)
    assert isinstance(next(iter(streams)), AudioOrVideoStream)

    unknown_stream = AudioStream(
        itag="0",
        mime_type="test",
        codecs="test",
        audio_sampling_rate=0,
        base_url="test",
    )
    assert streams_in_list[0] in streams
    assert unknown_stream not in streams


def test_filter(streams_in_list: list[AudioOrVideoStream]):
    streams = Streams(streams_in_list)
    filtered = streams.filter(lambda x: isinstance(x, AudioStream))
    assert len(filtered) == 2
    assert isinstance(next(iter(filtered)), AudioStream)


def test_non_empty_query(streams_in_list: list[AudioOrVideoStream]):
    streams = Streams(streams_in_list)
    assert streams.query("itag eq 244") == [streams.get_by_itag("244")]


def test_empty_query(streams_in_list: list[AudioOrVideoStream]):
    assert Streams(streams_in_list).query("itag eq 0") == []


@pytest.mark.parametrize(
    "format_spec",
    [
        "function(cond1",
        "function(cond1) and cond2",
        "function()",
        "(cond1 and cond2)",
    ],
)
def test_invalid_query(format_spec: str, streams_in_list: list[AudioOrVideoStream]):
    with pytest.raises(QueryError) as exc_info:
        Streams(streams_in_list).query(format_spec)
    assert "Format spec is invalid" in str(exc_info.value)


def test_query_with_function(streams_in_list: list[AudioOrVideoStream]):
    streams = Streams(streams_in_list)
    assert streams.query("best(format eq webm)") == [streams.get_by_itag("271")]


def test_union(streams_in_list: list[AudioOrVideoStream]):
    a, b, *_ = streams_in_list
    assert Streams([a, b]) == Streams([a]) | Streams([b])
