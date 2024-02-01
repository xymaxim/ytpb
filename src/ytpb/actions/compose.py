import copy
from datetime import datetime, timezone

from lxml import etree
from lxml.builder import E

from ytpb.exceptions import YtpbError
from ytpb.mpd import NAMESPACES as NS
from ytpb.playback import Playback, RewindInterval
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


def compose_static_mpd(
    playback: Playback, rewind_interval: RewindInterval, streams: SetOfStreams
) -> str:
    nsmap = {
        "xsi": "http://www.w3.org/2001/XMLSchema-instance",
        None: "urn:mpeg:DASH:schema:MPD:2011",
    }
    # Create the MPD tag
    mpd_element = etree.Element("MPD", nsmap=nsmap)

    some_base_url = next(iter(streams)).base_url

    segment_duration_s = float(extract_parameter_from_url("dur", some_base_url))
    segment_duration_ms = int(segment_duration_s) * int(S_TO_MS)
    rewind_length = rewind_interval.end.sequence - rewind_interval.start.sequence + 1
    range_duration_s = rewind_length * int(segment_duration_s)

    mpd_element.attrib.update(
        {
            f"{{{nsmap['xsi']}}}schemaLocation": (
                "urn:mpeg:DASH:schema:MPD:2011 DASH-MPD.xsd"
            ),
            "profiles": "urn:mpeg:dash:profile:isoff-main:2011",
            "type": "static",
            "mediaPresentationDuration": f"PT{range_duration_s}S",
        }
    )

    comment_element = etree.Comment(_build_top_level_comment_text(some_base_url))
    mpd_element.addprevious(comment_element)

    # Create and append the ProgramInformation tag
    title, url = playback.info.title, playback.info.url
    program_info_element = E.ProgramInformation(E.Title(title), E.Source(url))
    mpd_element.append(program_info_element)

    # Create the Period tag
    period_element = etree.Element("Period")
    period_element.attrib["duration"] = f"PT{range_duration_s}S"

    # Create the SegmentTemplate tag inside Period
    segment_template_element = etree.Element("SegmentTemplate")
    segment_template_element.attrib.update(
        {
            "media": "sq/$Number$",
            "startNumber": str(rewind_interval.start.sequence),
            "duration": str(segment_duration_ms),
            "timescale": "1000",
        }
    )

    mime_types_of_streams = sorted({s.mime_type for s in streams})
    for i, mime_type in enumerate(mime_types_of_streams):
        adaptation_set_element = etree.Element("AdaptationSet")
        adaptation_set_element.attrib.update(
            {"id": str(i), "mimeType": mime_type, "subsegmentAlignment": "true"}
        )

        # Append the SegmentTemplate tag into AdaptationSet
        adaptation_set_element.append(copy.deepcopy(segment_template_element))

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

    output = etree.tostring(
        etree.ElementTree(mpd_element),
        xml_declaration=True,
        encoding="UTF-8",
        pretty_print=True,
    )
    return output.decode()


def refresh_mpd(manifest_content: str, streams: SetOfStreams) -> str:
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
