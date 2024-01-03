from datetime import timedelta
from pathlib import Path

import av
import structlog
from PIL import Image

logger = structlog.get_logger(__name__)


def capture_frame(segment_path: Path, target_offset: timedelta) -> Image:
    target_offset_seconds = target_offset.total_seconds()
    with av.open(str(segment_path)) as container:
        stream = container.streams.video[0]
        target_pts = stream.start_time + target_offset_seconds / stream.time_base
        previous_frame: av.VideoFrame = None
        for current_frame in container.decode(stream):
            if current_frame.pts >= target_pts:
                break
            previous_frame = current_frame
        else:
            message = "Target offset is out of the video, use last frame"
            logger.debug(message, offset=target_offset_seconds)
    target_frame = previous_frame or current_frame
    return target_frame.to_image()
