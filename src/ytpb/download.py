"""Download media segments."""

import io
import os
from pathlib import Path
from typing import Callable, Generator
from urllib.parse import urljoin

import requests
import structlog

from ytpb.errors import SegmentDownloadError
from ytpb.types import SegmentSequence
from ytpb.utils.url import extract_media_type_from_url, extract_parameter_from_url

logger = structlog.get_logger(__name__)

SegmentOutputFilename = str | Callable[[SegmentSequence, str], str]


def _request_segment(
    sequence: SegmentSequence,
    base_url: str,
    size: int | None = None,
    session: requests.Session | None = None,
) -> requests.Response:
    get_function = session.get if session else requests.get

    headers = {}
    if size:
        headers["Range"] = f"bytes=0-{size}"

    response = get_function(urljoin(base_url, f"sq/{sequence}"), headers=headers)

    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError:
        exception = SegmentDownloadError(
            f"Failed to download segment {sequence}: {response.reason}", sequence
        )
        logger.error(exception, exc_info=True)
        raise exception from None

    if size and response.status_code == requests.codes.ok:
        logger.debug("Header 'Range' is ignored, downloaded all content")

    return response


def compose_default_segment_filename(sequence: SegmentSequence, base_url: str) -> str:
    itag = extract_parameter_from_url("itag", base_url)
    extension = extract_media_type_from_url(base_url)[1]
    return f"{sequence}.i{itag}.{extension}"


def save_segment_to_file(
    content: bytes,
    sequence: SegmentSequence,
    base_url: str,
    output_directory: Path,
    output_filename,
) -> Path:
    if callable(output_filename):
        output_filename_value = output_filename(sequence, base_url)
        output_path = Path(output_directory) / output_filename_value
    else:
        output_path = Path(output_directory) / output_filename

    with open(output_path, "wb") as f:
        f.write(content)

    return output_path


def download_segment(
    sequence: int,
    base_url: str,
    output_directory: Path,
    output_filename: SegmentOutputFilename = compose_default_segment_filename,
    size: int | None = None,
    session: requests.Session | None = None,
    force_download: bool = True,
) -> Path:
    """Downloads a segment to file.

    Args:
        sequence: A segment sequence number.
        base_url: A segment base URL.
        output_directory: Where to download a segment.
        output_filename: A segment output filename.
        size: An amount of bytes to download.
        session: A :class:`requests.Session` object.
        force_download: Whether to download a segment if it already exists.

    Returns:
        A path where a segment was downloaded.

    Raises:
        SegmentDownloadError: If failed to download a segment.
    """
    if callable(output_filename):
        output_filename_value = output_filename(sequence, base_url)
        path_to_download_to = Path(output_directory) / output_filename_value
    else:
        path_to_download_to = Path(output_directory) / output_filename

    if force_download or not os.path.isfile(path_to_download_to):
        with open(path_to_download_to, "wb") as f:
            response = _request_segment(sequence, base_url, size, session)
            f.write(response.content)

    return path_to_download_to


def download_segment_to_buffer(
    sequence: SegmentSequence,
    base_url: str,
    size: int | None = None,
    session: requests.Session | None = None,
) -> io.BytesIO:
    """Downloads a segment to buffer.

    Args:
        sequence: A segment sequence number.
        base_url: A segment base URL.
        size: An amount of bytes to download.
        session: A :class:`requests.Session` object.

    Returns:
        An :class:`io.BytesIO` object.

    Raises:
        SegmentDownloadError: If failed to download a segment.
    """
    response = _request_segment(sequence, base_url, size, session)
    return io.BytesIO(response.content)


def iter_segments(
    sequences: list[SegmentSequence],
    base_url: str,
    size: int | None = None,
    session: requests.Session | None = None,
) -> Generator[tuple[requests.Response, SegmentSequence, str], None, None]:
    """Iterates over segment sequence numbers and requests segments.

    Args:
        sequences: Segment sequence numbers.
        base_url: A segment base URL.
        size: An amount of bytes to download.
        session: A :class:`requests.Session` object.

    Yields:
        Tuples of a :class:`requests.Response` object, segment sequence number,
        and base URL.
    """
    for sequence in sequences:
        with _request_segment(sequence, base_url, size, session) as response:
            yield response, sequence, base_url
