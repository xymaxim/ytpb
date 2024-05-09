import shlex
import subprocess
from pathlib import Path
from typing import Any

import structlog

from ytpb.errors import FFmpegRunError

logger = structlog.get_logger(__name__)


def run_ffmpeg(
    args: str | list[str | Path], **subprocess_kwargs: Any
) -> subprocess.CompletedProcess:
    command = ["ffmpeg", "-v", "error", "-hide_banner", "-y"]
    if isinstance(args, str):
        command.extend(shlex.split(args))
    else:
        command.extend(args)

    logger.debug(" ".join([str(x) for x in command]))
    cp = subprocess.run(command, **subprocess_kwargs)
    try:
        cp.check_returncode()
    except subprocess.CalledProcessError as e:
        logger.error("There was a problem running FFmpeg command.")
        raise FFmpegRunError from e

    return cp
