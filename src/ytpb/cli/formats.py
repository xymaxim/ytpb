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
                    value, has_subbed = re.subn(rf"^{pattern}", repl, value)
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


MEDIA_FORMAT_ALIASES = {"mp4": "format = mp4", "webm": "format = webm"}

CODECS_ALIASES = {
    "mp4a": "codecs contains mp4a",
    "avc1": "codecs contains avc1",
    "vp9": "codecs = vp9",
}

NAMED_QUALITY_ALIASES = {
    "low": "height = 144",
    "medium": "height = 480",
    "high": "height = 720",
    "FHD": "height = 1080",
    "2K": "height = 1440",
    "4K": "height = 2160",
}

ITAG_PATTERN_ALIAS = (r"\b(\d+)\b", r"itag = \1")
QUALITY_PATTERN_ALIAS = (r"(\d+)p\b", r"height = \1")
QUALITY_FPS_PATTERN_ALIAS = (r"(\d+)p(\d+)\b", r"[height = \1 and frame_rate = \2]")
QUALITY_OP_PATTERN_ALIAS = (r"([<>=]=?)(\d+)p\b", r"height \1 \2")
FPS_PATTERN_ALIAS = (r"(\d+)fps\b", r"frame_rate = \1")

PATTERN_ALIASES = dict(
    (
        ITAG_PATTERN_ALIAS,
        QUALITY_PATTERN_ALIAS,
        QUALITY_FPS_PATTERN_ALIAS,
        QUALITY_OP_PATTERN_ALIAS,
        FPS_PATTERN_ALIAS,
    ),
)

ALIASES: dict[str, str] = {
    **MEDIA_FORMAT_ALIASES,
    **NAMED_QUALITY_ALIASES,
    **CODECS_ALIASES,
    **PATTERN_ALIASES,
}
