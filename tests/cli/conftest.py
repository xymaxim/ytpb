""" Fixtures for the CLI tests."""

import contextlib
import os
from collections.abc import Callable
from functools import partial
from pathlib import Path

import pytest
from click.testing import CliRunner

from ytpb.cli import cli


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
    runner = CliRunner()
    with isolated_filesystem(tmp_path):
        yield partial(runner.invoke, cli)
