import csv
from pathlib import Path
from typing import NamedTuple

import pytest

from ytpb.locate import SegmentLocator, SequenceMetadataPair
from ytpb.segment import Segment, SegmentMetadata
from ytpb.types import SegmentSequence

from tests.conftest import TEST_DATA_PATH


def read_gap_case_fixture_data(path: Path) -> dict:
    class Row(NamedTuple):
        sequence: str
        ingestion_walltime_ms: str
        duration_s: str

    data = {}
    with open(path, encoding="utf-8") as f:
        reader = csv.reader(f, delimiter=",")
        next(reader)
        for fields in reader:
            row = Row(*fields)
            data[int(row.sequence)] = (
                float(row.ingestion_walltime_ms) / 1e6,
                float(row.duration_s),
            )

    return data


@pytest.fixture(scope="class")
def gap_case_fixture_factory(
    request: pytest.FixtureRequest, monkeyclass: pytest.MonkeyPatch
) -> None:
    request.cls.fixture_data = read_gap_case_fixture_data(request.cls.fixture_data_path)

    def _create_segment_metadata(sequence: SegmentSequence) -> SegmentMetadata:
        fake_required_fields = {
            "ingestion_uncertainty": 0,
            "stream_duration": 0,
            "max_dvr_duration": 0,
            "first_frame_time": 0,
            "first_frame_uncertainty": 0,
        }
        return SegmentMetadata(
            sequence_number=sequence,
            ingestion_walltime=request.cls.fixture_data[sequence][0],
            target_duration=2.0,
            **fake_required_fields,
        )

    def mock_download_segment(sequence: SegmentSequence, *args, **kwargs) -> Path:
        return Path(str(sequence))

    def mock_create_segment(sequence_as_path: Path) -> Segment:
        segment = Segment()
        segment.sequence = int(str(sequence_as_path))
        segment.metadata = _create_segment_metadata(segment.sequence)
        return segment

    def mock_get_actual_duration(class_obj: Segment) -> float:
        return request.cls.fixture_data[class_obj.sequence][1]

    def mock_download_segment_and_parse_metadata(
        class_obj: Segment, sequence: SegmentSequence
    ) -> SegmentMetadata:
        return _create_segment_metadata(sequence)

    monkeyclass.setattr("ytpb.locate.download_segment", mock_download_segment)
    monkeyclass.setattr(Segment, "from_file", mock_create_segment)
    monkeyclass.setattr(Segment, "get_actual_duration", mock_get_actual_duration)
    monkeyclass.setattr(
        SequenceMetadataPair,
        "_download_segment_and_parse_metadata",
        mock_download_segment_and_parse_metadata,
    )


@pytest.mark.usefixtures("gap_case_fixture_factory")
class BaseGapCase:
    fixture_data_path: str
    reference_sequence: int

    @classmethod
    def setup_class(cls):
        cls.test_base_url = "https://rr5---sn-5hneknee.googlevideo.com/videoplayback/expire/1679810403/ei/A4sfZK2bNI6HyQWm_ayoBQ/ip/0.0.0.0/id/kHwmzef842g.2/itag/140/source/yt_live_broadcast/requiressl/yes/spc/99c5CWjeTpgWlc2Ht4dNOPt0QhK37Bg/vprv/1/playlist_type/DVR/ratebypass/yes/mime/audio%2Fmp4/live/1/gir/yes/noclen/1/dur/2.000/keepalive/yes/fexp/24007246/sparams/expire,ei,ip,id,itag,source,requiressl,spc,vprv,playlist_type,ratebypass,mime,live,gir,noclen,dur/sig/AOq0QJ8wRQIhAPBxN7yXkU2fPTceJrT_lK4Xw6mT7xWGOjkOrV7Yeh8KAiAq1suuogbWY1qV3dAERpp5I-YUSlVRZQBFlqRpmH-5xQ%3D%3D/mh/XB/mm/44/mn/sn-5hneknee/ms/lva/mt/1679787559/mv/u/mvi/5/pl/24/lsparams/mh,mm,mn,ms,mv,mvi,pl/lsig/AG3C_xAwRQIgfNF-yRJyHRp2Uy4nuoe4-SExdFLMbippDYfUo9FMH0ACIQCEdJrPkdJIilz7Kr-cmdu1Nh3NOwRVdbndOsu-ubkChQ%3D%3D/"

    def setup_method(self):
        self.ssl = SegmentLocator(self.test_base_url, self.reference_sequence)


class TestGapCase1(BaseGapCase):
    fixture_data_path = f"{TEST_DATA_PATH}/gap-cases/gap-case-1-fixture.csv"
    reference_sequence = 7959630

    def test_S1(self):
        sequence, _, falls_in_gap, _ = self.ssl.find_sequence_by_time(1679788193.600278)
        assert (7959599, False) == (sequence, falls_in_gap)

    def test_E1(self):
        sequence, _, falls_in_gap, _ = self.ssl.find_sequence_by_time(
            1679788193.600278, end=True
        )
        assert (7959599, False) == (sequence, falls_in_gap)

    @pytest.mark.parametrize("reference", [None, 7959600, 7959601, 7959602])
    def test_S2(self, reference: int | None):
        target_time = 1679788196.600287
        expected_sequence = 7959600
        if reference is None:
            sequence, _, falls_in_gap, _ = self.ssl.find_sequence_by_time(target_time)
            assert (expected_sequence, False) == (sequence, falls_in_gap)
        else:
            sl = SegmentLocator(self.test_base_url, reference)
            sequence, _, falls_in_gap, _ = sl.find_sequence_by_time(target_time)
            assert (expected_sequence, False) == (sequence, falls_in_gap)

    @pytest.mark.parametrize("reference", [None, 7959600, 7959601, 7959602])
    def test_S3(self, reference: int | None):
        """For this case, two segments are possibly valid formally, depending on
        the chosen reference."""
        target_time = 1679788198.599000
        if reference in [None, 7959601]:
            expected_sequence = 7959601
        else:
            expected_sequence = 7959602
        if reference is None:
            sequence, _, falls_in_gap, _ = self.ssl.find_sequence_by_time(target_time)
            assert (expected_sequence, False) == (sequence, falls_in_gap)
        else:
            sl = SegmentLocator(self.test_base_url, reference)
            sequence, _, falls_in_gap, _ = sl.find_sequence_by_time(target_time)
            assert (expected_sequence, falls_in_gap) == (sequence, falls_in_gap)


class TestGapCase2(BaseGapCase):
    fixture_data_path = f"{TEST_DATA_PATH}/gap-cases/gap-case-2-fixture.csv"
    reference_sequence = 7947346

    def test_S1(self):
        sequence, _, falls_in_gap, _ = self.ssl.find_sequence_by_time(1679763599.262686)
        assert (7947333, False) == (sequence, falls_in_gap)

    def test_S2(self):
        sequence, _, falls_in_gap, _ = self.ssl.find_sequence_by_time(1679763601.235894)
        assert (7947334, False) == (sequence, falls_in_gap)

    def test_S3(self):
        sequence, _, falls_in_gap, _ = self.ssl.find_sequence_by_time(1679763611.742391)
        assert (7947335, True) == (sequence, falls_in_gap)

    def test_E3(self):
        sequence, _, falls_in_gap, _ = self.ssl.find_sequence_by_time(
            1679763611.742391, end=True
        )
        assert (7947334, True) == (sequence, falls_in_gap)

    @pytest.mark.xfail(
        reason=(
            "Overestimated due to large actual duration of segment 7947335 "
            "(the difference > TIME_DIFF_TOLERANCE; see issue #5)"
        )
    )
    def test_S4(self):
        sequence, _, falls_in_gap, _ = self.ssl.find_sequence_by_time(
            1679763626.506922, end=True
        )
        assert (7947335, False) == (sequence, falls_in_gap)


class TestGapCase3(BaseGapCase):
    fixture_data_path = f"{TEST_DATA_PATH}/gap-cases/gap-case-3-fixture.csv"
    reference_sequence = 7958122

    def test_S1(self):
        sequence, _, falls_in_gap, _ = self.ssl.find_sequence_by_time(1679785199.451019)
        assert (7958102, False) == (sequence, falls_in_gap)

    def test_S2(self):
        sequence, _, falls_in_gap, _ = self.ssl.find_sequence_by_time(1679785201.449813)
        assert (7958103, False) == (sequence, falls_in_gap)

    def test_S3(self):
        sequence, _, falls_in_gap, _ = self.ssl.find_sequence_by_time(1679785204.623643)
        assert (7958104, True) == (sequence, falls_in_gap)

    def test_E3(self):
        sequence, _, falls_in_gap, _ = self.ssl.find_sequence_by_time(
            1679785204.623643, end=True
        )
        assert (7958103, True) == (sequence, falls_in_gap)

    def test_S4(self):
        sequence, _, falls_in_gap, _ = self.ssl.find_sequence_by_time(1679785208.850441)
        assert sequence in (7958104, 7958105)
        assert False == falls_in_gap

    def test_S5(self):
        sequence, _, falls_in_gap, _ = self.ssl.find_sequence_by_time(1679785208.903407)
        assert (7958106, False) == (sequence, falls_in_gap)
