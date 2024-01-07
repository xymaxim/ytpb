import logging
from dataclasses import dataclass
from pathlib import Path

import click
import cloup
import structlog
import toml

from ytpb.cli.commands.capture import capture_group
from ytpb.cli.commands.download import download_command
from ytpb.cli.commands.mpd import mpd_group
from ytpb.cli.options import config_options, logging_options
from ytpb.config import (
    DEFAULT_CONFIG,
    get_default_config_path,
    load_config_from_file,
    setup_logging,
    update_nested_dict,
)
from ytpb.types import ConfigMap

logger = structlog.get_logger()


@dataclass
class ContextObject:
    """This object is referenced as `ctx.obj`."""

    config = ConfigMap(DEFAULT_CONFIG)


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
    ctx.obj.config.new_child(config_dict)

    default_map_from_config = config_dict["options"]
    ctx.default_map = update_nested_dict(ctx.default_map, default_map_from_config)


@cloup.group(invoke_without_command=True)
@cloup.option_group(
    "Global options",
    config_options,
    logging_options,
)
@click.pass_context
def cli(ctx: click.Context, config_path: Path, no_config: bool, debug: bool) -> None:
    """This is a main entry point of the CLI."""
    ctx.ensure_object(ContextObject)
    ctx.default_map = ctx.obj.config["options"]

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


cli.section(
    "Top-level commands",
    capture_group,
    download_command,
    mpd_group,
)
