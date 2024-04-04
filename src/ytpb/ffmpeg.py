import shlex
import subprocess
from pathlib import Path
from typing import Any

import structlog

from ytpb.errors import FFmpegRunError

logger = structlog.get_logger(__name__)


def run_ffmpeg(
    args: str | list[str], **subprocess_kwargs: Any
) -> subprocess.CompletedProcess:
    command = ["ffmpeg", "-v", "error", "-hide_banner", "-y"]

    if isinstance(args, str):
        command.extend(shlex.split(args))
    else:
        command.extend(args)

    cp = subprocess.run(command, **subprocess_kwargs)

    try:
        cp.check_returncode()
    except subprocess.CalledProcessError as e:
        logger.error("There was a problem running FFmpeg command.")
        raise FFmpegRunError from e

    return cp


def run_ffprobe(
    input_path: Path, args: str | list[str], **subprocess_kwargs: Any
) -> subprocess.CompletedProcess:
    command = ["ffprobe", "-v", "0", "-hide_banner"]

    if isinstance(args, str):
        command.extend(shlex.split(args))
    else:
        command.extend(args)
    command.append(input_path)

    cp = subprocess.run(command, **subprocess_kwargs)
    return cp


def ffprobe_show_entries(input_path: Path, entries_to_show: str) -> str:
    command_args = f"-show_entries {entries_to_show} -of default=nw=1:nk=1"
    cp = run_ffprobe(input_path, command_args, capture_output=True, check=True)
    output = cp.stdout.decode().rstrip("\n")
    return output


def ffmpeg_stream_copy(input_path: Path, output_path: Path):
    subprocess_kwargs = {"capture_output": True, "check": True}
    run_ffmpeg(f"-i {input_path} -c copy {output_path}", **subprocess_kwargs)
