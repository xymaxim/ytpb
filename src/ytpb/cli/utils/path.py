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


class AllowedCharacters(enum.StrEnum):
    UNICODE = enum.auto()
    ASCII = enum.auto()
    POSIX = enum.auto()


def sanitize_for_filename(value: str, replacement: str = "-") -> str:
    chars_to_replace = ("|", "/")
    for char in chars_to_replace:
        value = value.replace(char, replacement)
    normalized = unicodedata.normalize("NFKC", value)
    return pathvalidate.sanitize_filename(normalized)


def sanitize_filepath(value: Path) -> Path:
    return pathvalidate.sanitize_filepath(value)


def posixify_for_filename(value: str, separator: str = "-"):
    posix_characters_re = re.compile(r"[^\w\-.]+", flags=re.ASCII)

    if not posix_characters_re.match(separator):
        actual_separator = separator
    else:
        actual_separator = "-"

    output = unidecode.unidecode(value, "ignore")
    output = re.sub(rf"(?:\s+)?({actual_separator}+)(?:\s+)?", r"\1", output)
    output = posix_characters_re.sub(actual_separator, output)

    if output != actual_separator:
        output = output.strip(actual_separator)

    return output


def adjust_for_filename(
    value: str,
    characters: AllowedCharacters = AllowedCharacters.UNICODE,
    length: int = 255,
    separator: str | None = None,
) -> str:
    fallback_separator = "-"
    dashes_pattern = r"(?:\s+)?([{0}]+)(?:\s+)?".format("".join(DASHES))

    output = sanitize_for_filename(value, fallback_separator)

    is_separator_non_empty = separator is not None and separator != " "
    if is_separator_non_empty or characters == AllowedCharacters.POSIX:
        # For visual appeal, replace dashes and surrounding spaces with dashes
        # to replace them afterward (in parentheses) with a separator
        # symbol. For example: 'A B - C D' -> 'A_B-C_D' (-> 'A_B_C_D').
        output = re.sub(dashes_pattern, r"\1", output)

    actual_separator: str | None = None
    if characters == AllowedCharacters.POSIX:
        actual_separator = posixify_for_filename(separator or fallback_separator)
        output = posixify_for_filename(output, actual_separator)
    else:
        match characters:
            case AllowedCharacters.UNICODE:
                actual_separator = separator
            case AllowedCharacters.ASCII:
                actual_separator = separator and unidecode.unidecode(
                    separator, "replace", fallback_separator
                )
                output = unidecode.unidecode(output, "ignore")

        # Replace multiple consecutive spaces with a single space.
        if separator is not None:
            output = re.sub(r"\s+", " ", output)

    if length and len(output) > length:
        output = textwrap.shorten(
            output,
            length,
            placeholder="",
            break_on_hyphens=True,
            break_long_words=False,
        )
        output = re.sub(dashes_pattern + "$", "", output)

    # For the POSIX case, the output is already with spaces replaced.
    if is_separator_non_empty and characters != AllowedCharacters.POSIX:
        output = re.sub(dashes_pattern, r"\1", output)
        output = output.replace(" ", actual_separator)

    is_actual_non_empty = actual_separator and actual_separator != " "
    if is_actual_non_empty and actual_separator != fallback_separator:
        output = output.replace(fallback_separator, actual_separator)

    output = output.strip(fallback_separator + " ")

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
