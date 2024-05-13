"""Actions to compose and refresh MPEG-DASH MPDs."""

import copy
from datetime import datetime, timezone

from lxml import etree
from lxml.builder import E

from ytpb.errors import YtpbError
from ytpb.playback import Playback, RewindInterval
from ytpb.representations import NAMESPACES as NS
from ytpb.segment import SegmentMetadata
from ytpb.streams import SetOfStreams
from ytpb.utils.other import S_TO_MS
from ytpb.utils.url import extract_parameter_from_url


def _build_top_level_comment_text(base_url: str) -> str:
    expire_date = datetime.fromtimestamp(
        int(extract_parameter_from_url("expire", base_url)), timezone.utc
    )
    expire_date_string = expire_date.astimezone().isoformat()
    result = f"This file is created with ytpb, and expires at {expire_date_string}"
    return result


def _compose_mpd_skeleton(playback, streams):
    nsmap = {
        "xsi": "http://www.w3.org/2001/XMLSchema-instance",
        None: "urn:mpeg:DASH:schema:MPD:2011",
    }
    # Create the MPD tag
    mpd_element = etree.Element("MPD", nsmap=nsmap)

    mpd_element.attrib.update(
        {
            f"{{{nsmap['xsi']}}}schemaLocation": (
                "urn:mpeg:DASH:schema:MPD:2011 DASH-MPD.xsd"
            ),
            "profiles": "urn:mpeg:dash:profile:isoff-main:2011",
        }
    )

    some_base_url = next(iter(streams)).base_url

    comment_element = etree.Comment(_build_top_level_comment_text(some_base_url))
    mpd_element.addprevious(comment_element)

    # Create and append the ProgramInformation tag
    title, url = playback.info.title, playback.info.url
    program_info_element = E.ProgramInformation(E.Title(title), E.Source(url))
    mpd_element.append(program_info_element)

    # Create the Period tag
    period_element = etree.Element("Period")

    mime_types_of_streams = sorted({s.mime_type for s in streams})
    for i, mime_type in enumerate(mime_types_of_streams):
        adaptation_set_element = etree.Element("AdaptationSet")
        adaptation_set_element.attrib.update(
            {"id": str(i), "mimeType": mime_type, "subsegmentAlignment": "true"}
        )

        filtered_by_mime_type = streams.filter(lambda s: s.mime_type == mime_type)
        for stream in sorted(filtered_by_mime_type, key=lambda s: s.itag):
            representation_element = etree.Element("Representation")
            representation_element.attrib.update(
                {"id": stream.itag, "codecs": stream.codecs, "startWithSAP": "1"}
            )
            if "audio" in mime_type:
                representation_element.attrib.update(
                    {
                        "audioSamplingRate": str(stream.audio_sampling_rate),
                    }
                )
            else:
                representation_element.attrib.update(
                    {
                        "width": str(stream.width),
                        "height": str(stream.height),
                        "maxPlayoutRate": "1",
                        "frameRate": str(stream.frame_rate),
                    }
                )

            # Append the BaseURL tag
            representation_element.append(E("BaseURL", stream.base_url))

            # Append the Representation tag into AdaptationSet
            adaptation_set_element.append(representation_element)

        period_element.append(adaptation_set_element)

        # Finally, append the Period tag into MPD
        mpd_element.append(period_element)

    return mpd_element


def compose_static_mpd(
    playback: Playback, rewind_interval: RewindInterval, streams: SetOfStreams
) -> str:
    """Composes a static MPEG-DASH MPD."""
    mpd_element = _compose_mpd_skeleton(playback, streams)

    some_base_url = next(iter(streams)).base_url

    rewind_length = rewind_interval.end.sequence - rewind_interval.start.sequence + 1
    segment_duration_s = float(extract_parameter_from_url("dur", some_base_url))
    range_duration_s = rewind_length * int(segment_duration_s)

    mpd_element.attrib.update(
        {"type": "static", "mediaPresentationDuration": f"PT{range_duration_s}S"}
    )

    period_element = mpd_element.find(".//Period", namespaces=NS)
    period_element.attrib["duration"] = f"PT{range_duration_s}S"

    segment_template_element = etree.Element("SegmentTemplate")
    segment_template_element.attrib.update(
        {
            "media": "sq/$Number$",
            "startNumber": str(rewind_interval.start.sequence),
            "duration": str(int(segment_duration_s) * int(S_TO_MS)),
            "timescale": "1000",
        }
    )

    for element in period_element.findall(".//Representation", namespaces=NS):
        element.insert(1, copy.deepcopy(segment_template_element))

    output = etree.tostring(
        etree.ElementTree(mpd_element),
        xml_declaration=True,
        encoding="UTF-8",
        pretty_print=True,
    )

    return output.decode()


def compose_dynamic_mpd(
    playback: Playback, rewind_metadata: SegmentMetadata, streams: SetOfStreams
) -> str:
    """Composes a dynamic MPEG-DASH MPD."""
    mpd_element = _compose_mpd_skeleton(playback, streams)
    mpd_element.attrib["profiles"] = "urn:mpeg:dash:profile:isoff-live:2011"

    mpd_element.attrib.update(
        {
            "type": "dynamic",
            "availabilityStartTime": datetime.fromtimestamp(
                rewind_metadata.ingestion_walltime, timezone.utc
            ).isoformat(timespec="milliseconds"),
        }
    )

    period_element = mpd_element.find(".//Period", namespaces=NS)
    period_element.attrib["start"] = f"PT{rewind_metadata.stream_duration}S"

    segment_template_element = etree.Element("SegmentTemplate")
    segment_template_element.attrib.update(
        {
            "media": "sq/$Number$",
            "startNumber": str(rewind_metadata.sequence_number),
            "timescale": "1000",
        }
    )

    segment_duration_ms = int(rewind_metadata.target_duration * S_TO_MS)
    segment_template_element.append(
        E("SegmentTimeline", E("S", d=str(segment_duration_ms), r="-1"))
    )

    for element in period_element.findall(".//Representation", namespaces=NS):
        element.insert(1, copy.deepcopy(segment_template_element))

    output = etree.tostring(
        etree.ElementTree(mpd_element),
        xml_declaration=True,
        encoding="UTF-8",
        pretty_print=True,
    )

    return output.decode()


def refresh_mpd(manifest_content: str, streams: SetOfStreams) -> str:
    """Refreshes segment base URLs in a composed MPEG-DASH MPD."""
    manifest = etree.fromstring(manifest_content.encode())

    representation_elements = manifest.xpath("//mpd:Representation", namespaces=NS)
    for representation in representation_elements:
        base_url_element = representation.xpath(".//mpd:BaseURL", namespaces=NS)[0]
        if stream := streams.get_by_itag(itag := representation.get("id")):
            base_url_element.text = stream.base_url
        else:
            raise YtpbError(f"No stream with itag '{itag}' in the streams")

    comment_element: etree._Comment = manifest.xpath("/comment()")[0]
    comment_element.text = _build_top_level_comment_text(base_url_element.text)
    manifest.addprevious(comment_element)

    output = etree.tostring(
        etree.ElementTree(manifest),
        xml_declaration=True,
        encoding="UTF-8",
        pretty_print=True,
    )
    return output.decode()
