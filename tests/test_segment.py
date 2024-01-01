from dataclasses import asdict

import pytest

from ytpb.segment import Segment


def test_segment_metadata_parsing() -> None:
    content = b"Sequence-Number: 1150301\r\nIngestion-Walltime-Us: 1679329555339525\r\nIngestion-Uncertainty-Us: 85\r\nStream-Duration-Us: 5751479780030\r\nMax-Dvr-Duration-Us: 14400000000\r\nTarget-Duration-Us: 5000000\r\nFirst-Frame-Time-Us: 1679329560650712\r\nFirst-Frame-Uncertainty-Us: 87\r\nEncoding-Alias: L1_Bg\r\n"
    segment = Segment()
    segment.local_path = "test"
    assert asdict(segment.parse_youtube_metadata(content)) == {
        "sequence_number": 1150301,
        "ingestion_walltime": 1679329555.339525,
        "ingestion_uncertainty": 8.5e-5,
        "stream_duration": 5751479.780030,
        "max_dvr_duration": 14400.0,
        "target_duration": 5.0,
        "first_frame_time": 1679329560.650712,
        "first_frame_uncertainty": 8.7e-5,
        "encoding_alias": "L1_Bg",
        "streamable": None,
    }


def test_another_segment_metadata_parsing() -> None:
    content = b"Sequence-Number: 19447394\r\nIngestion-Walltime-Us: 1703082200383647\r\nIngestion-Uncertainty-Us: 80\r\nStream-Duration-Us: 38894190937000\r\nMax-Dvr-Duration-Us: 7200000000\r\nTarget-Duration-Us: 2000000\r\nStreamable: T\r\nFirst-Frame-Time-Us: 1703082201132871\r\nFirst-Frame-Uncertainty-Us: 83\r\nEncoding-Alias: L1_Bg\r\n"
    segment = Segment()
    segment.local_path = "test"
    assert asdict(segment.parse_youtube_metadata(content)) == {
        "sequence_number": 19447394,
        "ingestion_walltime": 1703082200.383647,
        "ingestion_uncertainty": 8.0e-5,
        "stream_duration": 38894190.937000,
        "max_dvr_duration": 7200.0,
        "target_duration": 2.0,
        "first_frame_time": 1703082201.132871,
        "first_frame_uncertainty": 8.3e-5,
        "encoding_alias": "L1_Bg",
        "streamable": "T",
    }


def test_get_actual_duration(audio_segment: Segment) -> None:
    assert pytest.approx(audio_segment.get_actual_duration()) == 1.996916
