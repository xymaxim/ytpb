import tempfile
from datetime import timedelta
from pathlib import Path

import av
from IPython import get_ipython
from IPython.display import Image


def display_video_frame_at(
    video_path: Path, at: timedelta, format: str | None = None, width: float = 480
):
    ss = at.total_seconds()
    with tempfile.NamedTemporaryFile(suffix=".jpg") as tmp:
        output_image_path = tmp.name
        get_ipython().run_cell(
            (
                f"!ffmpeg -loglevel error -y -ss {ss} -i {video_path} "
                f"-vframes 1 {output_image_path}"
            )
        )
        display(Image(output_image_path, width=width))


def display_first_video_frame(video_path: Path, format: str | None = None):
    with tempfile.NamedTemporaryFile(suffix=".jpg") as tmp:
        output_image_path = tmp.name
        with av.open(str(video_path)) as container:
            stream = container.streams.video[0]
            frame = next(container.decode(stream))
            image = frame.reformat(format=format).to_image()
            image.save(output_image_path, quality=80)
            display(Image(output_image_path, width=480))


def display_last_video_frame(video_path: Path, format: str | None = None):
    with tempfile.NamedTemporaryFile(suffix=".jpg") as tmp:
        output_image_path = tmp.name
        with av.open(str(video_path)) as container:
            stream = container.streams.video[0]
            *frames, last_frame = container.decode(stream)
            image = last_frame.reformat(format=format).to_image()
            image.save(output_image_path, quality=80)
            display(Image(output_image_path, width=480))
