import re
from itertools import product

import click

ALIAS_RE = re.compile(r"@([\w<>=\-\\]+)(?!\s)?")


def expand_aliases(expression: str, aliases: dict[str, str]) -> str:
    def _resolve_alias(
        name: str, aliases: dict[str, str], patterns: list[tuple[str, str]]
    ) -> str:
        resolved = name
        try:
            resolved = aliases[name]
        except KeyError:
            for pattern, repl in patterns:
                resolved = re.sub(pattern, repl, name)
        if resolved == name:
            raise click.UsageError(f"Unknown alias found: '{name}'")
        if "@" in resolved:
            raise click.UsageError(
                f"Cannot resolve nested alias(es) in @{name}: '{resolved}'"
            )
        return resolved

    output = expression

    for name in ALIAS_RE.findall(output):
        patterns = [(k, v) for k, v in aliases.items() if "\\" in k]
        value = _resolve_alias(name, aliases, patterns)
        output = output.replace(f"@{name}", value)

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
