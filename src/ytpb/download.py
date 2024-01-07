import io
import os
from pathlib import Path
from typing import Callable
from urllib.parse import urljoin

import requests
import structlog

from ytpb.exceptions import SegmentDownloadError
from ytpb.types import SegmentSequence
from ytpb.utils.url import extract_media_type_from_url, extract_parameter_from_url

logger = structlog.get_logger(__name__)

_SegmentOutputFilename = str | Callable[[SegmentSequence, str], str]


def compose_default_segment_filename(sequence: SegmentSequence, base_url: str) -> str:
    itag = extract_parameter_from_url("itag", base_url)
    extension = extract_media_type_from_url(base_url)[1]
    return f"{sequence}.i{itag}.{extension}"


def _make_request_for_segment(
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


def download_segment(
    sequence: int,
    base_url: str,
    output_directory: Path,
    output_filename: _SegmentOutputFilename = compose_default_segment_filename,
    size: int | None = None,
    session: requests.Session | None = None,
    force_download: bool = True,
) -> Path:
    if callable(output_filename):
        output_filename_value = output_filename(sequence, base_url)
        path_to_download_to = Path(output_directory) / output_filename_value
    else:
        path_to_download_to = Path(output_directory) / output_filename

    if force_download or not os.path.isfile(path_to_download_to):
        with open(path_to_download_to, "wb") as f:
            response = _make_request_for_segment(sequence, base_url, size, session)
            f.write(response.content)

    return path_to_download_to


def download_segment_to_buffer(
    sequence: SegmentSequence,
    base_url: str,
    size: int | None = None,
    session: requests.Session | None = None,
) -> io.BytesIO:
    response = _make_request_for_segment(sequence, base_url, size, session)
    return io.BytesIO(response.content)
