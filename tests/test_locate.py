import csv
import logging
from pathlib import Path
from typing import NamedTuple
from unittest.mock import MagicMock, patch

import pytest
import responses

from conftest import TEST_DATA_PATH
from ytpb.locate import SequenceLocator, SequenceMetadataPair

from ytpb.segment import Segment, SegmentMetadata
from ytpb.types import SegmentSequence


def read_gap_case_fixture_data(path: Path) -> dict:
    class Row(NamedTuple):
        sequence: str
        ingestion_walltime_ms: str
        duration_s: str

    data = {}
    with open(path) as f:
        reader = csv.reader(f, delimiter=",")
        column_names = next(reader)
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
        self.ssl = SequenceLocator(self.test_base_url, self.reference_sequence)


class TestGapCase1(BaseGapCase):
    """Test gap case 1 -- no gaps."""

    fixture_data_path = f"{TEST_DATA_PATH}/gap-cases/gap-case-1-fixture.csv"
    reference_sequence = 7959630

    def test_S1(self):
        assert self.ssl.find_sequence_by_time(1679788193.600278) == 7959599

    def test_E1(self):
        assert self.ssl.find_sequence_by_time(1679788193.600278, end=True) == 7959599

    @pytest.mark.xfail
    def test_S2(self):
        assert self.ssl.find_sequence_by_time(1679788196.600287) == 7959600

    def test_S3(self):
        assert self.ssl.find_sequence_by_time(1679788198.599000) == 7959601


class TestGapCase2(BaseGapCase):
    fixture_data_path = f"{TEST_DATA_PATH}/gap-cases/gap-case-2-fixture.csv"
    reference_sequence = 7947346

    def test_S1(self):
        assert self.ssl.find_sequence_by_time(1679763599.262686) == 7947333

    def test_S2(self):
        assert self.ssl.find_sequence_by_time(1679763601.235894) == 7947334

    def test_S3(self):
        assert self.ssl.find_sequence_by_time(1679763611.742391) == 7947335

    def test_E3(self):
        assert self.ssl.find_sequence_by_time(1679763611.742391, end=True) == 7947334

    @pytest.mark.xfail
    def test_S4(self, caplog):
        caplog.set_level(logging.DEBUG)
        sequence = self.ssl.find_sequence_by_time(1679763626.506922)
        assert sequence == 7947335
        assert "gap" not in caplog.text


class TestGapCase3(BaseGapCase):
    fixture_data_path = f"{TEST_DATA_PATH}/gap-cases/gap-case-3-fixture.csv"
    reference_sequence = 7958122

    def test_S1(self):
        assert self.ssl.find_sequence_by_time(1679785199.451019) == 7958102

    def test_S2(self):
        assert self.ssl.find_sequence_by_time(1679785201.449813) == 7958103

    def test_S3(self):
        assert self.ssl.find_sequence_by_time(1679785204.623643) == 7958104

    def test_E3(self):
        assert self.ssl.find_sequence_by_time(1679785204.623643, end=True) == 7958103

    def test_S4(self):
        assert self.ssl.find_sequence_by_time(1679785208.850441) == 7958104

    def test_S5(self):
        assert self.ssl.find_sequence_by_time(1679785208.903407) == 7958106
