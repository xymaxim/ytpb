"""Mutable set of streams."""

from collections.abc import MutableSet
from typing import Any, Callable, Iterator, Self

from ytpb.format_spec import query_items, QueryFunction
from ytpb.types import AudioOrVideoStream, AudioStream, SetOfStreams, VideoStream

__all__ = ("Streams",)


def stream_comparison_function(stream: AudioOrVideoStream):
    match stream:
        case AudioStream():
            return (stream.mime_type, stream.audio_sampling_rate)
        case VideoStream():
            return (stream.mime_type, stream.height, stream.frame_rate)


class Streams(MutableSet):
    """Represents a mutable set of
    :class:`ytpb.representations.RepresentationInfo` objects."""

    def __init__(self, iterable: list[AudioOrVideoStream] | None = None) -> None:
        self._elements = set()
        for value in iterable or []:
            if not isinstance(value, AudioOrVideoStream):
                raise ValueError
            self._elements.add(value)

    @classmethod
    def from_dicts(cls, dicts: list[dict]):
        streams = cls()
        stream: AudioOrVideoStream
        for stream_dict in dicts:
            if "audio" in stream_dict["mime_type"]:
                stream = AudioStream(**stream_dict)
            else:
                stream = VideoStream(**stream_dict)
            streams.add(stream)
        return streams

    def __len__(self):
        return len(self._elements)

    def __ior__(self, other: Self) -> Self:
        self.update(other)
        return self

    def __iter__(self) -> Iterator[AudioOrVideoStream]:
        return iter(self._elements)

    def __contains__(self, item: Any) -> bool:
        for stream in self:
            if stream.itag == item.itag:
                return True
        return False

    def add(self, value: AudioOrVideoStream):
        """Adds a stream."""
        self._elements.add(value)

    def discard(self, value: AudioOrVideoStream):
        """Removes a stream."""
        try:
            self._elements.remove(value)
        except KeyError:
            pass

    def get_by_itag(self, itag: str) -> AudioOrVideoStream | None:
        """Gets a stream by an itag value."""
        for stream in self:
            if stream.itag == itag:
                return stream
        return None

    def filter(self, predicate: Callable[[AudioOrVideoStream], bool]) -> SetOfStreams:
        """Filters streams by a predicate function.

        Args:
            predicate: A predicate function.

        Examples:
            Get only video streams::

              from ytpb.types import VideoStream
              playback.streams.filter(lambda x: x.type == "video")

        Returns:
            A new instance of this class with filtered streams.
        """
        return self.__class__(list(filter(predicate, self._elements)))

    def query(
        self,
        format_spec: str,
        functions: dict[str, QueryFunction] | None = None,
    ) -> list[AudioOrVideoStream]:
        """Queries streams by a format spec.

        Notes:
            Check for attributes is strict. This means that the following code
            will fail with :class:`.QueryError` because audio streams don't have
            the ``height`` attribute::

                audio_streams.query("height eq 1080")

        References:
            https://ytpb.readthedocs.io/en/latest/reference.html#format-spec

        Args:
            format_spec: A format spec.
            functions: Additional query functions to be used in a format
                spec. For built-in functions, see
                :const:`ytpb.format_spec.FUNCTIONS`.

        Returns:
            A list of queried streams.

        Raises:
            QueryError: If failed to query streams with the given format spec.
        """
        return query_items(format_spec, self._elements, functions)
