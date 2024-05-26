import re
from itertools import product

ALIAS_RE = re.compile(r"@([\w<>=-\\]+)(?!\s)?")


def expand_aliases(expression: str, aliases: dict[str, str]) -> str:
    output = expression
    for name, value in aliases.items():
        full_alias = f"@{name}"
        if "\\" in name:
            output = re.sub(full_alias, value, output)
        else:
            output = output.replace(full_alias, value)
    assert "@" not in output, "Unexpanded aliases remain"
    return output


MEDIA_FORMAT_ALIASES = {"mp4": "format eq mp4", "webm": "format eq webm"}

video_quality_heights = (144, 240, 360, 480, 720, 1080, 1440, 2160)
VIDEO_QUALITY_30FPS_ALIASES = {
    f"{height}p": f"height eq {height} and frame_rate eq 30"
    for height in video_quality_heights
}
VIDEO_QUALITY_30FPS_ALIASES.update(
    {
        f"{height}p30": f"height eq {height} and frame_rate eq 30"
        for height in video_quality_heights
    }
)

VIDEO_QUALITY_60FPS_ALIASES = {
    f"{height}p60": f"height eq {height} and frame_rate eq 60"
    for height in [720, 1080, 1440, 2160]
}

VIDEO_QUALITY_WITH_OPERATOR_ALIASES = {
    f"{operator}{height}p": f"height {operator_name} {height}"
    for (operator, operator_name), height in product(
        [("<", "lt"), ("<=", "le"), (">", "gt"), (">=", "ge")], video_quality_heights
    )
}

NAME_QUALITY_ALIASES = {
    "low": "height eq 144",
    "medium": "height eq 480",
    "high": "height eq 720",
    "FHD": "height eq 1080",
    "2K": "height eq 1440",
    "4K": "height eq 2160",
}

FRAME_PER_SECOND_ALIASES = {"30fps": "frame_rate eq 30", "60fps": "frame_rate eq 60"}

PATTERNED_ALIASES = {
    # @123 = itag eq 123
    r"(\d+)\b": r"itag eq \1",
}

ALIASES: dict[str, str] = {
    **MEDIA_FORMAT_ALIASES,
    **VIDEO_QUALITY_30FPS_ALIASES,
    **VIDEO_QUALITY_60FPS_ALIASES,
    **VIDEO_QUALITY_WITH_OPERATOR_ALIASES,
    **NAME_QUALITY_ALIASES,
    **FRAME_PER_SECOND_ALIASES,
    **PATTERNED_ALIASES,
}
