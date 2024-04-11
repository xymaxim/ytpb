"""Actions to capture frames as images."""

from collections.abc import Iterator
from datetime import datetime

import av
import structlog
from PIL import Image

from ytpb.locate import SegmentLocator
from ytpb.playback import Playback
from ytpb.segment import Segment
from ytpb.types import AudioOrVideoStream, SegmentSequence

logger = structlog.get_logger(__name__)


def extract_frame_as_image(
    segment: Segment, target_date: datetime, last_as_fallback: bool = True
) -> Image.Image:
    """Extracts a frame as image from a segment.

    Args:
        segment: A :class:`~ytpb.segment.Segment` object.
        target_date: A frame target date.
        last_as_fallback: Whether to use a last frame as a fallback if the
          target date is out of a video.

    Returns:
        An extracted image as a :class:`PIL.Image.Image` object.
    """
    target_offset = (target_date - segment.ingestion_start_date).total_seconds()
    with av.open(str(segment.local_path)) as container:
        stream = container.streams.video[0]
        target_pts = stream.start_time + target_offset / stream.time_base
        previous_frame: av.VideoFrame = None
        for current_frame in container.decode(stream):
            if current_frame.pts >= target_pts:
                break
            previous_frame = current_frame
        else:
            if last_as_fallback:
                message = "Target date is out of the video"
                logger.debug(f"{message}, use last frame", date=target_date)
            else:
                raise ValueError(message)
    return (previous_frame or current_frame).to_image()


def capture_frames(
    playback: Playback,
    target_dates: list[datetime],
    stream: AudioOrVideoStream,
    reference_sequence: SegmentSequence | None = None,
) -> Iterator[Image.Image, Segment]:
    """Captures frames as images.

    Examples:
        Here's an example of capturing frames from one day every hour::

          from datetime import datetime, timedelta, timezone

          best_stream, = playback.streams.query(
              "best(type eq video and format eq mp4 and frame_rate eq 30)"
          )
          start_date = datetime(2024, 1, 2, 0, tzinfo=timezone.utc)
          dates_to_capture = [start_date + timedelta(hours=h) for h in range(25)]

          captured = capture_frames(
              playback, dates_to_capture, best_stream
          )
          for i, (image, _) in enumerate(captured):
              image.save(f"output-{i:02d}.jpg", quality=80)

    Args:
        playback: A :class:`~ytpb.playback.Playback` object.
        target_dates: A list of dates to capture.
        stream: A stream to which segments used for capturing belongs.
        reference_sequence: A segment sequence number used as a start reference.

    Returns:
        An iterator with pairs of a captured frame and corresponding segment.
    """
    number_of_targets = len(target_dates)
    previous_sequence = reference_sequence
    for i, target_date in enumerate(target_dates):
        sl = SegmentLocator(
            stream.base_url,
            reference_sequence=previous_sequence,
            temp_directory=playback.get_temp_directory(),
            session=playback.session,
        )
        is_end = i == number_of_targets - 1
        found_sequence, *_ = sl.find_sequence_by_time(target_date.timestamp(), is_end)
        previous_sequence = found_sequence

        segment = playback.get_segment(found_sequence, stream)
        image = extract_frame_as_image(segment, target_date)

        yield image, segment
