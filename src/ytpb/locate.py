"""Provides locating segments by the desired time."""

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

logger = structlog.get_logger("locate")

# Number of bytes sufficient to cover the YouTube metadata in segment
# files. Note that the minimum value varies for different media formats, so the
# value was determined empirically for all available formats.
PARTIAL_SEGMENT_SIZE_BYTES = 2000


def find_time_diff_in_sequences(
    time1: Timestamp, time2: Timestamp, segment_duration: float
) -> int:
    return math.ceil((time2 - time1) / segment_duration)


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

    The location algorithm contains three steps: (1) roughly estimate a sequence
    number based on the constant duration of segments; (2) refine the
    pre-estimated sequence to find a candidate; (3) check if a candidate is not
    in a gap.
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
        """Refine the initial, pre-estimated sequence number using a binary
        search. This contains Step 2 and 3 of the algorithm.
        """
        current_diff_in_s = self._find_time_diff(self.candidate, desired_time)
        self.track.append((self.candidate.sequence, current_diff_in_s))
        logger.debug(
            "Made a jump to segment, time difference: %+f s",
            current_diff_in_s,
            seq=self.candidate.sequence,
            time=self.candidate.metadata.ingestion_walltime,
        )

        # The direction of iteration: to the right (1) or left (-1).
        direction = int(math.copysign(1, current_diff_in_s))

        search_domain_boundaries = (self.track[0][0], self.candidate.sequence)
        left, right = min(search_domain_boundaries), max(search_domain_boundaries)
        search_domain = range(left, right + 1)
        logger.debug("Start a binary search", left=left, right=right)

        bisect_key = partial(self._get_bisected_segment_timestamp, target=desired_time)
        bisect_left(search_domain, desired_time, key=bisect_key)

        refined_sequence: SegmentSequence

        falls_into_gap = False
        if current_diff_in_s == 0:
            refined_sequence = self.candidate.sequence
        else:
            # Download a full candidate segment and check its duration:
            downloaded_path = self._download_full_segment(self.candidate.sequence)
            candidate_segment = Segment.from_file(downloaded_path)
            candidate_duration = candidate_segment.get_actual_duration()

            candidate_diff_in_s = current_diff_in_s
            logger.debug(
                "Candidate time difference: %+f s, actual duration: %+f s",
                candidate_diff_in_s,
                candidate_duration,
            )

            # Step 3. Finally, check if the desired date falls into a gap.
            if candidate_duration < abs(candidate_diff_in_s):
                falls_into_gap = True
                logger.debug("Input target time falls into a gap")
                changed_to_adjacent = False
                if candidate_diff_in_s < 0:
                    if end:
                        self.candidate.sequence -= 1
                        changed_to_adjacent = True
                else:
                    if not end:
                        self.candidate.sequence += 1
                        changed_to_adjacent = True
                if changed_to_adjacent:
                    self.track.append(
                        (
                            self.candidate.sequence,
                            self._find_time_diff(self.candidate, desired_time),
                        )
                    )
                    logger.debug(
                        "Step to adjacent segment, time difference: %+f s",
                        self.track[-1][1],
                        seq=self.candidate.sequence,
                        time=self.candidate.metadata.ingestion_walltime,
                    )

            refined_sequence = self.candidate.sequence

        return refined_sequence, falls_into_gap

    def find_sequence_by_time(
        self, desired_time: Timestamp, end: bool = False
    ) -> SegmentSequence:
        """Find sequence number of a segment by the given timestamp."""
        logger.info(
            "Locating segment with a timestamp",
            target=desired_time,
            reference=self.reference.sequence,
        )

        # Step 1. Make a trial jump to the desired sequence based on the
        # constant segment duration to find an initial candidate segment.
        diff_in_seq = find_time_diff_in_sequences(
            desired_time,
            self.reference.metadata.ingestion_walltime,
            self.segment_duration,
        )
        estimated_sequence = self.reference.sequence - diff_in_seq
        logger.debug("Initial candidate segment estimated as %d", estimated_sequence)

        self.candidate = SequenceMetadataPair(estimated_sequence, self)
        initial_diff_in_s = self._find_time_diff(self.candidate, desired_time)
        self.track.append((self.candidate.sequence, initial_diff_in_s))

        # The jump length value could be negative or positive.
        jump_length_in_seq = int(initial_diff_in_s // self.segment_duration)

        logger.debug(
            "Initial time difference: %+f s, %d segments",
            initial_diff_in_s,
            abs(jump_length_in_seq),
            seq=self.candidate.sequence,
            time=self.candidate.metadata.ingestion_walltime,
        )

        # Step 2. Refine the previously estimated sequence if needed.
        need_to_refine = True

        if jump_length_in_seq == 0:
            need_to_refine = False

        output: tuple[SegmentSequence, bool]
        if need_to_refine:
            try:
                self.candidate.sequence += jump_length_in_seq
                output = self._refine_candidate_sequence(desired_time, end)
            except SegmentDownloadError as exc:
                raise SequenceLocatingError(exc) from exc
        else:
            output = (self.candidate.sequence, False)

        logger.info("Segment has been located as %d", self.candidate.sequence)

        return output
