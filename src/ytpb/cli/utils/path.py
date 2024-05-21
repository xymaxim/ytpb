import enum
import re
import textwrap
import unicodedata
from pathlib import Path

import pathvalidate
import unidecode


DASHES = [
    "\u002D",  # HYPHEN-MINUS
    "\u2010",  # HYPHEN
    "\u2011",  # NON-BREAKING HYPHEN
    "\u2012",  # FIGURE DASH
    "\u2013",  # EN DASH
    "\u2014",  # EM DASH
    "\u2015",  # HORIZONTAL BAR
]


class TitleAllowedCharacters(enum.StrEnum):
    UNICODE = enum.auto()
    ASCII = enum.auto()
    POSIX = enum.auto()


def sanitize_filename(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    output = pathvalidate.sanitize_filename(
        normalized, replacement_text="-", platform="POSIX"
    )
    return output


def posixify_filename(value: str, separator: str = "-"):
    posix_characters_re = re.compile(r"[^\w\-.]+", flags=re.ASCII)

    if not posix_characters_re.match(separator):
        actual_separator = separator
    else:
        actual_separator = "-"

    output = unidecode.unidecode(value, "replace", " ")
    output = posix_characters_re.sub(actual_separator, output)
    # Strip the space if a title started with a non-POSIX character.
    output = output.lstrip(actual_separator)

    return output


def adjust_title_for_filename(
    title: str,
    characters: TitleAllowedCharacters = TitleAllowedCharacters.UNICODE,
    max_length: int | None = None,
    separator: str | None = None,
) -> str:
    fallback_separator = "-"
    dashes_pattern = r"(?:\s+)?([{0}]+)(?:\s+)?".format("".join(DASHES))

    if separator:
        # For visual appeal, replace dashes and surrounding spaces with
        # dashes. Compare, e.g.: 'A_B_-_C_D' and 'A_B-C_D' (we prefer this one).
        title = re.sub(dashes_pattern, r"\1", title)

    if characters == TitleAllowedCharacters.POSIX:
        output = posixify_filename(title, separator or fallback_separator)
    else:
        output = sanitize_filename(title)

        actual_separator: str

        match characters:
            case TitleAllowedCharacters.UNICODE:
                actual_separator = separator
            case TitleAllowedCharacters.ASCII:
                actual_separator = separator and unidecode.unidecode(
                    separator, "replace", fallback_separator
                )
                output = unidecode.unidecode(output, "replace", " ")
                # Strip the space if a title started with a non-converted character.
                output = output.lstrip()

        # Replace multiple consecutive spaces with a single space. This can be
        # in an original title, as well as after converting a title using ASCII
        # codec (non-converted characters are replaced with a space).
        output = re.sub(r"\s+", " ", output)

    if max_length and len(output) > max_length:
        output = textwrap.shorten(output, max_length, placeholder="")
        output = re.sub(dashes_pattern + "$", "", output)

    if separator and characters != TitleAllowedCharacters.POSIX:
        # For the POSIX case, the output is already with spaces replaced after
        # the posixify_filename() function.
        output = re.sub(r"\s", actual_separator, output)

    return output


def try_get_relative_path(path: Path, other: Path | None = None) -> Path:
    try:
        return path.relative_to(other or Path.cwd())
    except ValueError:
        return path


def remove_directories_between(top: Path, until: Path) -> None:
    until.rmdir()
    directory = until.resolve()
    while directory != top.resolve():
        directory = directory.parent
        directory.rmdir()
