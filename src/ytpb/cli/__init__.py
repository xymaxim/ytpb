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
from typing import Any, cast, TextIO, TypeAlias

import click
import cloup
import jinja2
import structlog
import toml

from ytpb._version import __version__
from ytpb.cli.commands.capture import capture_group
from ytpb.cli.commands.download import download_command
from ytpb.cli.commands.mpd import mpd_group
from ytpb.cli.common import suppress_output
from ytpb.cli.config import (
    AddressableChainMap,
    DEFAULT_CONFIG,
    get_default_config_path,
    load_config_from_file,
    setup_logging,
    update_nested_dict,
)
from ytpb.cli.options import config_options, logging_options
from ytpb.cli.templating import FILTERS as TEMPLATE_FILTERS

ConfigMap: TypeAlias = AddressableChainMap

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


def find_option_name_by_flag(command: click.Command, flag: str) -> str:
    for option in command.params:
        for opt in option.opts:
            if flag == opt.lstrip("-"):
                return option.name
    raise click.UsageError(f"Cannot find option with flag '--{flag}'.")


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

    # FIXME: This all looks like one unbeatiful hack. Really hope there's
    # another way that doesn't require much effort. See also pallets/click#680.
    try:
        user_options = ctx.obj.config.maps[0]["options"]
    except KeyError:
        pass
    else:
        _invoked_subcommand = ctx.command.commands[ctx.invoked_subcommand]
        if isinstance(_invoked_subcommand, click.Group):
            leftover_args = sys.argv[sys.argv.index(_invoked_subcommand.name) + 1 :]
            deepest_name = [arg for arg in leftover_args if not arg.startswith("-")][0]
            deepest_command = _invoked_subcommand.commands[deepest_name]
            user_defaults = user_options[_invoked_subcommand.name][deepest_name]
        else:
            deepest_command = _invoked_subcommand
            user_defaults = user_options[deepest_command.name]

        user_defaults_renamed: dict[str, str] = {}
        for flag, value in user_defaults.items():
            option_name = find_option_name_by_flag(deepest_command, flag)
            user_defaults_renamed[option_name] = value

        if isinstance(_invoked_subcommand, click.Group):
            user_options[_invoked_subcommand.name] = {
                deepest_command.name: user_defaults_renamed
            }
        else:
            user_options[deepest_command.name] = user_defaults_renamed

        ctx.default_map = update_nested_dict(ctx.default_map, user_options)


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
@click.version_option(__version__, "-V", "--version", message="%(version)s")
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
        report_file_path = Path.cwd() / f"ytpb-{timestamp}.log"
        report_handle = open(report_file_path, "a", encoding="utf-8")
        sys.stdout = cast(
            TextIO, ReportStreamWrapper(ctx.obj.original_stdout, report_handle)
        )
        sys.stderr = cast(TextIO, ReportStreamWrapper(sys.stderr, report_handle))

        @atexit.register
        def sanitize_report_file() -> None:
            report_handle.close()
            with FileInput(report_handle.name, inplace=True) as fi:
                for line in fi:
                    print(re.sub(r"/ip/([\w.:]+)/", "/ip/0.0.0.0/", line), end="")

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

    ctx.obj.jinja_environment = jinja2.Environment()
    ctx.obj.jinja_environment.filters.update(TEMPLATE_FILTERS)


cli = deepcopy(base_cli)
cli.help = "A playback for YouTube live streams"
cli.section(
    "Top-level commands",
    download_command,
    capture_group,
    mpd_group,
)
