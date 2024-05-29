import re
from typing import Any, Callable

import pycond as pc
import structlog

from ytpb.errors import QueryError
from ytpb.types import AudioOrVideoStream

logger = structlog.get_logger(__name__)

FORMAT_SPEC_RE = re.compile(
    r"^(?:(?P<function>[\w\-]+)\((?P<expr>[^\(\)]+)\)|(?P<just_expr>[^\(\)]+))$"
)

pc.ops_use_symbolic_and_txt(allow_single_eq=True)


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


def make_filter_from_expression(expression: str):
    return pc.make_filter(
        expression,
        autoconv_lookups=True,
        lookup=custom_lookup,
        ops_thru=treat_none_as_false,
    )
