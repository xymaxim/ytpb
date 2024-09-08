import re
from operator import attrgetter
from typing import Any, Callable, Protocol, Sequence

import click
import lark
import pycond as pc
import structlog

from ytpb.errors import QueryError
from ytpb.types import AudioOrVideoStream

logger = structlog.get_logger(__name__)

pc.ops_use_symbolic_and_txt(allow_single_eq=True)

ALIAS_RE = re.compile(r"@([\w<>=\-\\]+[\?!]?)")

GRAMMAR = r"""
    start: query

    query: expression

    ?expression: ALL -> all
               | NONE -> none
               | conditional_expression
               | fallback_expression
               | piped_expression
               | "(" expression ")" -> group
    conditional_expression: condition
    piped_expression: expression ("|" (expression | function))+ -> pipe
    fallback_expression: expression ("?:" expression)+

    condition: CONDITION_STRING

    function.2: FUNCTION_NAME

    ALL.3: "all"
    NONE.4: "none" | "''" | "\"\""
    CONDITION_STRING: /[@a-z0-9_\.,<>=!:\[\]'"\s]+/i
    FUNCTION_NAME: /[a-z0-9_\-]+/i

    %import common.WS_INLINE
    %ignore WS_INLINE
"""


class QueryFunction(Protocol):
    def __call__(
        self, streams: list[AudioOrVideoStream]
    ) -> list[AudioOrVideoStream]: ...


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
        if isinstance(state, dict):
            attribute_value = state[attribute]
        else:
            attribute_value = getattr(state, attribute)
    except (AttributeError, KeyError) as e:
        raise QueryError(f"Unknown attribute in format spec: '{attribute}'") from e
    return attribute_value, target


def make_filter_from_expression(expression: str):
    return pc.make_filter(
        expression,
        autoconv_lookups=True,
        lookup=custom_lookup,
        ops_thru=treat_none_as_false,
    )


def parse_expression(value: str) -> lark.Tree:
    return lark.Lark(GRAMMAR, start="query").parse(value)


def execute_query[
    T
](
    tree: lark.Tree,
    items: Sequence[T],
    functions: dict[str, QueryFunction] | None = None,
) -> Sequence[T]:
    def _process_query_tree(tree: lark.Tree, items: Sequence[T]) -> Sequence[T]:
        match tree.data:
            case "all":
                return items
            case "none":
                return []
            case "conditional_expression":
                (condition_node,) = tree.children[0].children
                condition_value = condition_node.value.strip()
                condition_filter = make_filter_from_expression(condition_value)
                queried = list(filter(condition_filter, items))
            case "function":
                assert functions, "No query functions are provided"
                if not items:
                    return items
                function_name = tree.children[0].value
                try:
                    function = functions[function_name]
                except KeyError:
                    raise QueryError(f"Cannot find '{function_name}' query function")
                queried = function(items)
            case "pipe":
                queried = items
                for node in tree.children:
                    queried = _process_query_tree(node, queried)
            case "fallback_expression":
                for node in tree.children:
                    if queried := _process_query_tree(node, items):
                        break
            case "group":
                queried = _process_query_tree(tree.children[0], items)
            case _:
                queried = items
        return queried

    return _process_query_tree(tree, items)


def query_items[
    T
](
    expression: str,
    items: Sequence[T],
    functions: dict[str, QueryFunction] | None = None,
) -> Sequence[T]:
    all_functions = FUNCTIONS | (functions or {})
    tree = parse_expression(expression)
    return execute_query(tree.children[0], items, all_functions)


def best(streams: list[AudioOrVideoStream]) -> list[AudioOrVideoStream]:
    """Gets the best stream in terms of quality (height and frame rate)."""
    return [sorted(streams, key=attrgetter("quality"))[-1]]


def worst(streams: list[AudioOrVideoStream]) -> list[AudioOrVideoStream]:
    """Gets the worst stream in terms of quality (height and frame rate)."""
    return [sorted(streams, key=attrgetter("quality"))[0]]


FUNCTIONS: dict[str, QueryFunction] = {
    "best": best,
    "worst": worst,
}
