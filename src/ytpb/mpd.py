import io
from dataclasses import dataclass
from functools import total_ordering

from lxml import etree


NAMESPACES = {
    "mpd": "urn:mpeg:DASH:schema:MPD:2011",
    "yt": "http://youtube.com/yt/2012/10/10",
}


@total_ordering
@dataclass(frozen=True)
class VideoQuality:
    height: int
    frame_rate: float

    @classmethod
    def from_string(cls, value: str) -> "VideoQuality":
        try:
            height, frame_rate = value.split("p")
            return cls(int(height), float(frame_rate or 30))
        except ValueError:
            raise ValueError("Value not formatted as video quality")

    def __str__(self) -> str:
        if self.frame_rate == 30:
            return f"{self.height}p"
        else:
            return f"{self.height}p{self.frame_rate:.2g}"

    def __eq__(self, other) -> bool:
        return str(self) == str(other)

    def __gt__(self, other) -> bool:
        if isinstance(other, str):
            other = type(self).from_string(other)
        if self.height > other.height:
            return True
        elif self.height == other.height and self.frame_rate > other.frame_rate:
            return True
        else:
            return False


@dataclass(frozen=True, slots=True)
class RepresentationInfo:
    itag: str
    mime_type: str
    codecs: str
    base_url: str

    @property
    def format(self):
        "An alias for a MIME subtype."
        return self.mime_type.split("/")[1]

    def __repr__(self):
        return f"{type(self).__name__}(itag={self.itag})"


@dataclass(frozen=True, repr=False)
class AudioRepresentationInfo(RepresentationInfo):
    audio_sampling_rate: int


@dataclass(frozen=True, repr=False)
class VideoRepresentationInfo(RepresentationInfo):
    width: int
    height: int
    frame_rate: int

    @property
    def quality(self) -> VideoQuality:
        return VideoQuality(self.height, self.frame_rate)


def _eval_local_xpath(element: etree.Element, node: str) -> list[etree.Element]:
    return element.xpath(".//*[local-name() = $node]", node=node)


def strip_manifest(manifest: etree.Element) -> bytes:
    with io.BytesIO() as output_stream:
        etree.strip_elements(manifest, f"{{{NAMESPACES['mpd']}}}SegmentList")
        manifest.write(output_stream, pretty_print=True)
        return output_stream.getvalue()


def extract_representations_info(manifest_content: str) -> list[RepresentationInfo]:
    representations_info: list[RepresentationInfo] = []

    manifest = etree.fromstring(manifest_content.encode())

    adaptation_sets = manifest.xpath("//mpd:AdaptationSet", namespaces=NAMESPACES)
    for adaptation in adaptation_sets:
        mime_type = adaptation.get("mimeType")
        is_audio = "audio" in mime_type

        representations = _eval_local_xpath(adaptation, "Representation")
        for repr_ in representations:
            itag = repr_.get("id")
            base_repr_kwargs = dict(
                itag=itag,
                mime_type=mime_type,
                codecs=repr_.get("codecs"),
                base_url=_eval_local_xpath(repr_, "BaseURL")[0].text,
            )

            if is_audio:
                info = AudioRepresentationInfo(
                    **base_repr_kwargs,
                    audio_sampling_rate=int(repr_.get("audioSamplingRate")),
                )
            else:
                info = VideoRepresentationInfo(
                    **base_repr_kwargs,
                    width=int(repr_.get("width")),
                    height=int(repr_.get("height")),
                    frame_rate=int(repr_.get("frameRate")),
                )
            representations_info.append(info)

    return representations_info
