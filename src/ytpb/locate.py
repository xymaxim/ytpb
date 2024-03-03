"""Provides locating a segment with the desired time."""

import math
import tempfile
from bisect import bisect_left
from functools import partial
from pathlib import Path

import requests
import structlog

from ytpb.download import compose_default_segment_filename, download_segment
from ytpb.exceptions import SegmentDownloadError, SequenceLocatingError
from ytpb.segment import Segment, SegmentMetadata
from ytpb.types import SegmentSequence, Timestamp
from ytpb.utils.remote import request_reference_sequence
from ytpb.utils.url import extract_parameter_from_url

logger = structlog.get_logger(__name__)

# Number of bytes sufficient to cover the YouTube metadata in segment
# files. Note that the minimum value varies for different media formats, so the
# value was determined empirically for all available formats.
PARTIAL_SEGMENT_SIZE_BYTES = 2000

# Absolute time difference tolerance (in seconds). See issue #5.
TIME_DIFF_TOLERANCE = 3e-2


class SequenceMetadataPair:
    def __init__(self, sequence: SegmentSequence, locator: "SegmentLocator"):
        self.locator = locator
        self.sequence = sequence

    @property
    def sequence(self) -> SegmentSequence:
        return self._sequence

    @sequence.setter
    def sequence(self, value: SegmentSequence):
        self._sequence = value
        self._metadata = self._download_segment_and_parse_metadata(value)

    @property
    def metadata(self):
        return self._metadata

    def _download_segment_and_parse_metadata(
        self, sequence: SegmentSequence
    ) -> SegmentMetadata:
        """Download a partial segment and parse metadata."""
        segment_filename = compose_default_segment_filename(
            sequence, self.locator.base_url
        )
        output_filename = segment_filename + ".part"
        downloaded_path = download_segment(
            sequence,
            self.locator.base_url,
            output_directory=self.locator.get_temp_directory(),
            output_filename=output_filename,
            size=PARTIAL_SEGMENT_SIZE_BYTES,
            session=self.locator.session,
            force_download=False,
        )
        with open(downloaded_path, "rb") as f:
            metadata = Segment.parse_youtube_metadata(f.read())
        return metadata


class SegmentLocator:
    """A locator which finds a segment with the desired time.

    The locating consists of three steps: (1) make one or two trial jumps based
    on the constant duration of segments (timeline may contain gaps, which leads
    to overestimation); (2) refine an estimated sequence number using a binary
    search if a candidate is not found (search domain is determined by two
    previous jumps); (3) check whether a target time falls into gap or not.
    """

    def __init__(
        self,
        base_url: str,
        reference_sequence: SegmentSequence | None = None,
        temp_directory: Path | None = None,
        session: requests.Session | None = None,
    ) -> None:
        self._temp_directory = temp_directory
        self.base_url = base_url
        self.session = session or requests.Session()

        if reference_sequence is None:
            reference_sequence = request_reference_sequence(base_url)
        self.reference = SequenceMetadataPair(reference_sequence, self)

        self.segment_duration = float(extract_parameter_from_url("dur", base_url))
        self.track: list[tuple[SegmentSequence, float]] = []

    def get_temp_directory(self):
        if self._temp_directory is None:
            self._temp_directory = tempfile.mkdtemp()
        return self._temp_directory

    def _download_full_segment(self, sequence: SegmentSequence) -> Path:
        downloaded_path = download_segment(
            sequence,
            self.base_url,
            output_directory=self.get_temp_directory(),
            session=self.session,
        )
        return downloaded_path

    def _find_time_diff(
        self, candidate: SequenceMetadataPair, desired_time: Timestamp
    ) -> float:
        return desired_time - candidate.metadata.ingestion_walltime

    def _get_bisected_segment_timestamp(
        self, sequence: SegmentSequence, *, target: Timestamp
    ) -> Timestamp:
        self.candidate.sequence = sequence
        current_diff_in_s = self._find_time_diff(self.candidate, target)
        self.track.append((sequence, current_diff_in_s))
        logger.debug(
            "Bisect step, time difference: %+f s",
            current_diff_in_s,
            seq=self.candidate.sequence,
            time=self.candidate.metadata.ingestion_walltime,
        )
        return self.candidate.metadata.ingestion_walltime

    def _refine_candidate_sequence(
        self, desired_time: Timestamp, end: bool
    ) -> tuple[SegmentSequence, bool]:
        """Refine an estimated sequence number and perform gap check."""
        first_jump_sequence, first_jump_diff = self.track[0]
        second_jump_sequence, second_jump_diff = self.track[1]

        # The direction of iteration: to the right (+1) or left (-1).
        direction = int(math.copysign(1, second_jump_diff))

        # Expand a search domain if it doesn't include a target. This can be
        # observed when the duration of segments just after a gap is
        # unexpectedly small, which brings underestimation.
        candidate_sequence = second_jump_sequence
        if first_jump_diff * second_jump_diff > 0:
            last_hope_jump = 4
            candidate_sequence += direction * last_hope_jump
            logger.debug("Search domain expanded to segment %d", candidate_sequence)

        domain_sequences = (first_jump_sequence, candidate_sequence)
        left, right = min(domain_sequences), max(domain_sequences)
        search_domain = range(left, right + 1)
        logger.debug("Start a binary search", left=left, right=right)

        bisect_key = partial(self._get_bisected_segment_timestamp, target=desired_time)
        found_index = bisect_left(search_domain, desired_time, key=bisect_key)
        self.candidate.sequence = search_domain[found_index - 1]

        # After the previous step the time difference is always positive.
        candidate_diff_in_s = self._find_time_diff(self.candidate, desired_time)
        if candidate_diff_in_s == 0:
            return self.candidate.sequence, False

        downloaded_path = self._download_full_segment(self.candidate.sequence)
        candidate_segment = Segment.from_file(downloaded_path)
        candidate_duration = candidate_segment.get_actual_duration()

        logger.debug(
            "Candidate time difference: %+f s, actual duration: %f s",
            candidate_diff_in_s,
            candidate_duration,
        )

        falls_into_gap = False
        if candidate_duration < candidate_diff_in_s - TIME_DIFF_TOLERANCE:
            falls_into_gap = True
            logger.debug("Input target time falls into a gap")
            if not end:
                self.candidate.sequence += 1
                current_diff_in_s = self._find_time_diff(self.candidate, desired_time)
                self.track.append((self.candidate.sequence, current_diff_in_s))
                logger.debug(
                    "Step to adjacent segment, time difference: %+f s",
                    current_diff_in_s,
                    seq=self.candidate.sequence,
                    time=self.candidate.metadata.ingestion_walltime,
                )

        return self.candidate.sequence, falls_into_gap

    def find_sequence_by_time(
        self, desired_time: Timestamp, end: bool = False
    ) -> SegmentSequence:
        """Find sequence number of a segment by the given timestamp."""
        logger.info(
            "Locating segment with a timestamp",
            target=desired_time,
            reference=self.reference.sequence,
        )

        # Starting from the reference, make one or two trial jumps (based on the
        # constant segment duration) to find a candidate or the desired segment.
        current_sequence = self.reference.sequence
        current_ingestion_time = self.reference.metadata.ingestion_walltime

        need_to_refine = False
        for jump_number in [1, 2]:
            estimated_diff_in_s = desired_time - current_ingestion_time
            jump_length_in_seq = int(estimated_diff_in_s // self.segment_duration)

            self.candidate = SequenceMetadataPair(
                current_sequence + jump_length_in_seq, self
            )
            current_sequence = self.candidate.sequence
            current_ingestion_time = self.candidate.metadata.ingestion_walltime
            current_diff_in_s = self._find_time_diff(self.candidate, desired_time)
            self.track.append((current_sequence, current_diff_in_s))

            logger.debug(
                "Jump %d, time difference: %+f s",
                jump_number,
                current_diff_in_s,
                seq=current_sequence,
                time=current_ingestion_time,
            )

            if 0 <= current_diff_in_s <= self.segment_duration + TIME_DIFF_TOLERANCE:
                break
        else:
            need_to_refine = True

        if need_to_refine:
            try:
                result = self._refine_candidate_sequence(desired_time, end)
            except SegmentDownloadError as exc:
                raise SequenceLocatingError(exc) from exc
        else:
            result = (self.candidate.sequence, False)

        logger.info("Segment has been located as %d", self.candidate.sequence)

        return result
