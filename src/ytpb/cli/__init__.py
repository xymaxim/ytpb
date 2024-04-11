import atexit
import logging
import os
import re
import sys
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from fileinput import FileInput
from pathlib import Path
from typing import Any, cast, TextIO

import click
import cloup
import structlog
import toml

from ytpb.cli.commands.capture import capture_group
from ytpb.cli.commands.download import download_command
from ytpb.cli.commands.mpd import mpd_group

from ytpb.cli.common import suppress_output
from ytpb.cli.options import config_options, logging_options
from ytpb.config import (
    ALL_ALIASES,
    DEFAULT_CONFIG,
    get_default_config_path,
    load_config_from_file,
    setup_logging,
    update_nested_dict,
)
from ytpb.types import ConfigMap

logger = structlog.get_logger(__name__)


@dataclass
class ReportStreamWrapper:
    stream: TextIO
    file: TextIO

    def write(self, message: str) -> None:
        self.stream.write(message)
        self.file.write(message)

    def __getattr__(self, attr: str) -> Any:
        return getattr(self.stream, attr)


@dataclass
class ContextObject:
    """This object is referenced as `ctx.obj`."""

    config: ConfigMap = field(default_factory=lambda: ConfigMap(DEFAULT_CONFIG))
    original_stdout: TextIO = field(default_factory=lambda: sys.stdout)


def load_config_into_context(ctx: click.Context, path: Path) -> dict:
    try:
        config_dict = load_config_from_file(path)
    except FileNotFoundError as e:
        raise click.FileError(
            filename=path,
            hint=str(e),
        )
    except toml.TomlDecodeError as e:
        raise click.FileError(
            filename=path,
            hint=f"Could not load configuration file.\n{e}",
        )

    ctx.ensure_object(ContextObject)
    ctx.obj.config = ctx.obj.config.new_child(config_dict)

    default_map_from_config = ctx.obj.config["options"]
    ctx.default_map = update_nested_dict(ctx.default_map, default_map_from_config)

    try:
        ALL_ALIASES.update(ctx.obj.config["general"]["aliases"])
    except KeyError:
        pass


@cloup.group(invoke_without_command=True)
@cloup.option_group(
    "Global options",
    config_options,
    logging_options,
    click.option(
        "-q",
        "--quiet",
        help="Supress all normal output.",
        default=False,
        is_flag=True,
        is_eager=True,
    ),
)
@click.version_option(None, "-V", "--version", message="%(version)s")
@click.pass_context
def base_cli(
    ctx: click.Context,
    config_path: Path,
    no_config: bool,
    debug: bool,
    report: bool,
    quiet: bool,
) -> None:
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())
        ctx.exit()

    ctx.ensure_object(ContextObject)
    ctx.default_map = ctx.obj.config["options"]

    if quiet:
        suppress_output()

    if report:
        debug = True
        os.environ["NO_COLOR"] = "1"

        timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d-%H%M%S")
        report_handle = open(Path.cwd() / f"ytpb-{timestamp}.log", "a")
        sys.stdout = cast(
            TextIO, ReportStreamWrapper(ctx.obj.original_stdout, report_handle)
        )
        sys.stderr = cast(TextIO, ReportStreamWrapper(sys.stderr, report_handle))

        @atexit.register
        def sanitize_report_file() -> None:
            report_handle.close()
            with FileInput(report_handle.name, inplace=True) as fi:
                for line in fi:
                    print(re.sub("/ip/([\w.:]+)/", "/ip/0.0.0.0/", line), end="")

    setup_logging(logging.DEBUG if debug else logging.WARNING)

    if not no_config:
        if config_path:
            logger.info("Using configuration from '%s' via --config", config_path)
            load_config_into_context(ctx, config_path)
        else:
            default_config_path = get_default_config_path()
            if default_config_path.exists():
                logger.info("Using configuration from '%s'", default_config_path)
                load_config_into_context(ctx, default_config_path)
    else:
        if config_path:
            raise click.UsageError("Conflicting --config and --no-config options given")


cli = deepcopy(base_cli)

cli.help = "A playback for YouTube live streams"
cli.section(
    "Top-level commands",
    download_command,
    capture_group,
    mpd_group,
)
