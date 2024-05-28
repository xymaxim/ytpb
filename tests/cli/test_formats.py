import click
import pytest
from ytpb.cli.formats import expand_aliases


@pytest.mark.parametrize(
    "aliases,spec,expected",
    [
        ({"a": "itag eq 140"}, "@a", "itag eq 140"),
        (
            {"a": "itag eq 140", "b": "format eq mp4"},
            "@a and @b",
            "itag eq 140 and format eq mp4",
        ),
        ({r"(\d+)\b": r"itag eq \1"}, "@140", "itag eq 140"),
    ],
)
def test_expand_non_nested_aliases(aliases: dict[str, str], spec: str, expected: str):
    assert expected == expand_aliases(spec, aliases)


@pytest.mark.parametrize(
    "aliases,spec,expected",
    [
        ({"a": "@aa", "aa": "itag eq 140"}, "@a", "itag eq 140"),
        (
            {"a": "@aa and @bb", "aa": "itag eq 140", "bb": "format eq mp4"},
            "@a",
            "itag eq 140 and format eq mp4",
        ),
    ],
)
def test_expand_nested_aliases(aliases: dict[str, str], spec: str, expected: str):
    assert expected == expand_aliases(spec, aliases)


@pytest.mark.parametrize(
    "aliases,spec",
    [
        ({}, "@x"),
        ({}, "@x and @y"),
        ({"a": "@x"}, "@a"),
    ],
)
def test_expand_unknown_aliases(aliases: dict[str, str], spec: str):
    with pytest.raises(click.UsageError) as exc_info:
        expand_aliases(spec, aliases)
    assert "Unknown alias found: @x" == str(exc_info.value)


@pytest.mark.parametrize(
    "aliases,spec,error",
    [
        ({"a": "@a"}, "@a", "Cannot resolve circular alias @a in @a"),
        ({"a": "@b", "b": "@a"}, "@a", "Cannot resolve circular alias @a in @b"),
        (
            {"a": "@b", "b": "@c", "c": "@a and test"},
            "@a",
            "Cannot resolve circular alias @a in @c",
        ),
    ],
)
def test_expand_circular_dependent_aliases(
    aliases: dict[str, str], spec: str, error: str
):
    with pytest.raises(click.UsageError) as exc_info:
        expand_aliases(spec, aliases)
    assert error == str(exc_info.value)
