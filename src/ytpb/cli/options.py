import functools
import logging
from dataclasses import fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import click

from ytpb.cli import parameters
from ytpb.cli.common import EARLIEST_DATE_TIMEDELTA
from ytpb.cli.custom import ConflictingOption, GlobalOption
from ytpb.cli.parameters import RewindIntervalParamType

from ytpb.utils.path import OUTPUT_PATH_PLACEHOLDER_RE


def validate_output_path(ctx: click.Context, param: click.Option, value: Path) -> Path:
    if value:
        pass
        # if matched := set(OUTPUT_PATH_PLACEHOLDER_RE.findall(str(value))):
        #     known_template_vars = [x.name for x in fields(OutputPathTemplateContext)]
        #     if not matched.issubset(known_template_vars):
        #         unknown_vars = matched - set(known_template_vars)
        #         unknown_vars_string = str(unknown_vars).strip("{}")
        #         raise click.BadParameter(
        #             f"Unknown or bad variable(s) provided: {unknown_vars_string}"
        #         )
    return value


def validate_start_date_not_too_far(
    ctx: click.Context, param: click.Option, value: datetime | str
) -> datetime | str:
    if isinstance(value, datetime):
        now = datetime.now(timezone.utc).astimezone(value.tzinfo)
        earliest_date = now - EARLIEST_DATE_TIMEDELTA
        if value <= earliest_date:
            raise click.BadParameter(
                "Start date is beyond the limit of 7 days. "
                "The earliest date is {}.".format(
                    earliest_date.isoformat(timespec="minutes")
                )
            )
    return value


def boundary_options(f):
    """A set of options which defines rewind interval."""

    f = click.option(
        "-p",
        "--preview",
        help="Run in preview mode.",
        is_flag=True,
    )(f)

    f = click.option(
        "-i",
        "--interval",
        metavar="INTERVAL",
        type=parameters.RewindIntervalParamType(),
        help="Time or segment interval to download.",
        required=True,
    )(f)

    return f


def output_options(f):
    f = click.option(
        "-o",
        "--output",
        type=click.Path(path_type=Path),
        help="Output file path (without extension).",
        default="<title>_<input_start_date>",
        callback=validate_output_path,
    )(f)

    return f


def config_options(f):
    f = click.option(
        "--config",
        "config_path",
        cls=GlobalOption,
        help="Specifies the path to a configuration file.",
        type=click.Path(path_type=Path),
        is_eager=True,
    )(f)

    f = click.option(
        "--no-config",
        cls=GlobalOption,
        help="Do not load user configuration file.",
        default=False,
        is_flag=True,
        is_eager=True,
    )(f)

    return f


def cache_options(f):
    f = click.option(
        "--force-update-cache",
        cls=ConflictingOption,
        conflicting_with=["no_cache"],
        help="Force to update cache.",
        is_flag=True,
    )(f)

    f = click.option(
        "--no-cache",
        cls=ConflictingOption,
        conflicting_with=["force_update_cache"],
        help="Do not use cache.",
        is_flag=True,
    )(f)

    return f


def logging_options(f):
    f = click.option(
        "--debug",
        "debug",
        cls=GlobalOption,
        help="Enable verbose output for debugging.",
        is_flag=True,
        is_eager=True,
    )(f)
    return f


yt_dlp_option = click.option(
    "-Y", "--yt-dlp", is_flag=True, help="Use yt-dlp to extract info."
)


no_cleanup_option = click.option(
    "--no-cleanup", is_flag=True, help="Do not clean up temporary files."
)
