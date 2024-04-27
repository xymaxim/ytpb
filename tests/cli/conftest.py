""" Fixtures for the CLI tests."""

import contextlib
import os
import sys
from collections.abc import Callable, Sequence
from functools import partial
from pathlib import Path

import pytest
from click import Command
from click.testing import CliRunner, Result

from ytpb.cli import cli


class CustomCliRunner(CliRunner):
    def invoke(
        self, cli: Command, args: str | Sequence[str] | None = None, **kwargs
    ) -> Result:
        sys.argv = args
        return super().invoke(cli, args, **kwargs)


@contextlib.contextmanager
def isolated_filesystem(path: Path):
    old_cwd = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(old_cwd)


@pytest.fixture()
def ytpb_cli_invoke(tmp_path: Path) -> Callable:
    runner = CustomCliRunner()
    with isolated_filesystem(tmp_path):
        yield partial(runner.invoke, cli)
