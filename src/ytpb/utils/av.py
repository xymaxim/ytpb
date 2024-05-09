from pathlib import Path

import av


def _get_stream_or_raise(streams, stream_selection: dict[str, int]):
    return streams.get(stream_selection)[0]


def show_number_of_streams(input_path: Path) -> int:
    with av.open(input_path) as container:
        return len(container.streams)


def show_codec_name(input_path: Path, stream_selection: dict[str, int]) -> str:
    with av.open(input_path) as container:
        stream = _get_stream_or_raise(container.streams, stream_selection)
        return stream.codec_context.name


def show_duration(input_path: Path, stream_selection: dict[str, int]) -> float:
    with av.open(input_path) as container:
        return container.duration / 1e6


def show_metadata(input_path: Path) -> dict[str, str]:
    with av.open(input_path) as container:
        return container.metadata
