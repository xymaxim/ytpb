import re
from typing import Any, Callable

import pycond as pc

import structlog

from ytpb.config import ALIAS_EXPAND_FUNCTIONS, ALL_ALIASES
from ytpb.errors import QueryError
from ytpb.types import AudioOrVideoStream

logger = structlog.get_logger(__name__)

ALIAS_RE = re.compile(r"@([\w<>=-]+)(?!\s)?")
FORMAT_SPEC_RE = re.compile(
    r"^(?:(?P<function>[\w\-]+)\((?P<expr>[^\(\)]+)\)|(?P<just_expr>[^\(\)]+))$"
)


def _expand_aliases(expression: str, aliases: dict[str, str]) -> str:
    for f in ALIAS_EXPAND_FUNCTIONS:
        expression = f(expression)

    all_aliases = ALL_ALIASES | aliases
    for matched in ALIAS_RE.finditer(expression):
        alias_with_symbol = matched.group()
        alias = matched.group(1)
        try:
            aliased_value = all_aliases[alias]
            expression = expression.replace(alias_with_symbol, aliased_value)
        except KeyError:
            raise QueryError(
                f"Unknown alias in format spec: '{alias_with_symbol}'"
            ) from None
    return expression


def treat_none_as_false(operator_function: Callable, a: Any, b: Any) -> bool:
    if a is None:
        return False
    else:
        return operator_function(a, b)


def custom_lookup(
    attribute: str, target: str | int, cfg: dict, state: AudioOrVideoStream, **kwargs
) -> tuple[str, str | int]:
    """Custom lookup function for audio and video streams (representations) with
    the existence check of attributes."""
    try:
        if isinstance(attribute, tuple):
            raise QueryError(
                "Attribute incorrectly matched in format spec: '{}'".format(
                    " ".join(attribute)
                )
            )
        attribute_value = getattr(state, attribute)
    except AttributeError as e:
        raise QueryError(f"Unknown attribute in format spec: '{attribute}'") from e
    return attribute_value, target


def make_filter_from_expression(expression: str, aliases: dict[str, str] | None = None):
    if ALIAS_RE.search(expression):
        expression = _expand_aliases(expression, aliases or {})
        logger.debug(f"Expression with alias(es) expanded as '{expression}'")
    output = pc.make_filter(
        expression,
        autoconv_lookups=True,
        lookup=custom_lookup,
        ops_thru=treat_none_as_false,
    )
    return output
