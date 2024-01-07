from collections.abc import Iterator
from datetime import datetime

import av
import structlog
from PIL import Image

from ytpb.locate import SegmentLocator
from ytpb.playback import Playback
from ytpb.segment import Segment
from ytpb.types import SegmentSequence

logger = structlog.get_logger(__name__)


def extract_frame_as_image(
    segment: Segment, target_date: datetime, last_as_fallback: bool = True
) -> Image:
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
    base_url: str,
    reference_sequence: SegmentSequence,
) -> Iterator[Image, Segment]:
    number_of_targets = len(target_dates)
    previous_sequence = reference_sequence
    for i, target_date in enumerate(target_dates):
        sl = SegmentLocator(
            base_url,
            reference_sequence=previous_sequence,
            temp_directory=playback.get_temp_directory(),
            session=playback.session,
        )
        is_end = i == number_of_targets - 1
        found_sequence, _ = sl.find_sequence_by_time(target_date.timestamp(), is_end)
        previous_sequence = found_sequence

        segment = playback.get_downloaded_segment(found_sequence, base_url)
        image = extract_frame_as_image(segment, target_date)

        yield image, segment
