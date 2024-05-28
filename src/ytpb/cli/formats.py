import re
from itertools import product

import click

ALIAS_RE = re.compile(r"@([\w<>=\-\\]+)(?!\s)?")


def expand_aliases(expression: str, aliases: dict[str, str]) -> str:
    source_alias: str = ""
    visited_aliases: set[str] = set()

    def _resolve_aliases(
        expression: str,
        aliases: dict[str, str],
        patterns: list[tuple[str, str]],
    ) -> str:
        nonlocal source_alias
        nonlocal visited_aliases

        resolved = expression
        for matched in ALIAS_RE.finditer(expression):
            full_alias = matched.group()
            name = matched.group(1)
            if name in visited_aliases:
                raise click.UsageError(
                    f"Cannot resolve circular alias {full_alias} in {source_alias}"
                )
            else:
                visited_aliases.add(name)
                source_alias = full_alias
            try:
                value = aliases[name]
            except KeyError:
                value = name
                for pattern, repl in patterns:
                    value, has_subbed = re.subn(pattern, repl, value)
                    if has_subbed:
                        break
                else:
                    raise click.UsageError(f"Unknown alias found: {full_alias}")
            resolved = resolved.replace(full_alias, value)

        if ALIAS_RE.match(resolved):
            return _resolve_aliases(resolved, aliases, patterns)

        return resolved

    patterns = [(k, v) for k, v in aliases.items() if "\\" in k]
    output = _resolve_aliases(expression, aliases, patterns)

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

PATTERN_ALIASES = {
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
    **PATTERN_ALIASES,
}
