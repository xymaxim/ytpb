from typing import Any

import pytest

from ytpb.format_spec import query_items


class TestFormatSpecQuery:
    state = [
        {"a": 1},
        {"a": 2},
        {"a": 3},
    ]
    functions = {"first": lambda items: [items[0]] if len(items) > 0 else []}

    @pytest.mark.parametrize(
        "query,expected",
        [
            # Conditional expressions:
            ("a eq 1", [{"a": 1}]),
            ("a = 1", [{"a": 1}]),
            ("a <= 1", [{"a": 1}]),
            ("[a eq 1]", [{"a": 1}]),
            # Piped expressions:
            ("a le 2 | a le 1", [{"a": 1}]),
            ("a le 2 | a le 1 | a eq 1", [{"a": 1}]),
            ("a le 2 | a eq 0 | a eq 1", []),
            # Fallback expressions:
            ("a eq 1 ?: a eq 2", [{"a": 1}]),
            ("a eq 0 ?: a eq 2", [{"a": 2}]),
            ("a eq 0 ?: a eq 100", []),
            # Grouped expressions:
            ("(a eq 1)", [{"a": 1}]),
            ("(a le 2 | a le 1) | a eq 1", [{"a": 1}]),
            ("(a eq 0 ?: a eq 100) ?: a eq 1", [{"a": 1}]),
            # Expressions with function:
            ("a le 2 | first", [{"a": 1}]),
            ("a eq 0 | first", []),
            # Mixed expressions:
            ("a le 2 ?: a le 3 | first", [{"a": 1}, {"a": 2}]),
            ("a eq 0 | first ?: a le 2 ", [{"a": 1}, {"a": 2}]),
            ("a eq 0 | first ?: a le 2 | first", [{"a": 1}]),
            ("a eq 0 | first ?: a le 3 | a le 2 | first", [{"a": 1}]),
            ("a eq 0 | first ?: a le 3 | first | first", [{"a": 1}]),
            ("(a le 2 | first) ?: a le 3", [{"a": 1}]),
            ("(a eq 2 | first) ?: (a le 3 | first)", [{"a": 2}]),
            ("(a eq 0 | first) ?: (a le 3 | first)", [{"a": 1}]),
            # Others:
            ("all", [{"a": 1}, {"a": 2}, {"a": 3}]),
            ("none", []),
            ("''", []),
            ('""', []),
        ],
    )
    def test_query_expression(self, query: str, expected: list[dict[str, Any]]):
        assert expected == query_items(query, self.state, self.functions)
