from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Protocol, TypeAlias

from ytpb.representations import AudioRepresentationInfo, VideoRepresentationInfo


class RelativeSegmentSequence(int): ...


Timestamp: TypeAlias = float

SegmentSequence: TypeAlias = int

AbsolutePointInStream: TypeAlias = datetime | SegmentSequence
RelativePointInStream: TypeAlias = timedelta | RelativeSegmentSequence
PointInStream: TypeAlias = AbsolutePointInStream | RelativePointInStream

AudioStream: TypeAlias = AudioRepresentationInfo
VideoStream: TypeAlias = VideoRepresentationInfo
AudioOrVideoStream: TypeAlias = AudioStream | VideoStream
SetOfStreams: TypeAlias = "Streams[AudioOrVideoStream]"


class AddressableMappingProtocol(Protocol):
    def traverse(self, address: str, default: Any, delimiter: str) -> Any: ...


@dataclass
class DateInterval:
    """Represents a closed date interval."""

    start: datetime
    end: datetime

    def __post_init__(self):
        if self.end < self.start:
            raise ValueError("End date occurs earlier in time than the start date")

    @property
    def duration(self) -> float:
        return (self.end - self.start).total_seconds()

    def __sub__(self, other: "DateInterval") -> tuple[float, float]:
        """Find difference between two date intervals as:
        [x1, y1] - [x2, y2] = [|x2 - x1|, |y2 - y1|].
        """
        return (
            (self.start - other.start).total_seconds(),
            (self.end - other.end).total_seconds(),
        )

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, DateInterval):
            return False
        return self.start == self.start and self.end == other.end

    def __ne__(self, other: Any) -> bool:
        return not self.__eq__(other)

    def __le__(self, other: "DateInterval") -> bool:
        return self.is_subinterval(other)

    def __contains__(self, value: datetime) -> bool:
        return self.start <= value <= self.end

    def __str__(self) -> str:
        return f"[{self.start.isoformat(), self.end.isoformat()}]"

    def is_subinterval(self, other: "DateInterval") -> bool:
        """Test whether the interval is completely included in other."""
        return self.start in other and self.end in other
