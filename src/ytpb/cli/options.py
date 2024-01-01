from datetime import datetime, timezone
from pathlib import Path
from textwrap import fill
from typing import Callable

import click
from PIL import Image

from ytpb.cli import parameters
from ytpb.cli.common import EARLIEST_DATE_TIMEDELTA
from ytpb.cli.custom import ConflictingOption, GlobalOption

from ytpb.utils.path import OUTPUT_PATH_PLACEHOLDER_RE


def validate_output_path(template_context_class) -> Callable[..., Path]:
    def wrapper(ctx: click.Context, param: click.Option, value: Path) -> Path:
        if matched := set(OUTPUT_PATH_PLACEHOLDER_RE.findall(str(value))):
            known_template_vars = template_context_class.__annotations__.keys()
            if not matched.issubset(known_template_vars):
                unknown_vars = matched - set(known_template_vars)
                unknown_vars_string = str(unknown_vars).strip("{}")
                raise click.BadParameter(
                    f"Unknown variable(s) found: {unknown_vars_string}. "
                    f"Option value: '{value}'."
                )
        return value

    return wrapper


def validate_image_output_path(template_context_class) -> Callable[..., Path]:
    def wrapper(ctx: click.Context, param: click.Option, value: Path) -> Path:
        if not value.suffix:
            raise click.BadParameter("Image extension must be provided.")

        extensions = Image.registered_extensions()
        allowed_extensions = {ext for ext, f in extensions.items() if f in Image.SAVE}
        if value.suffix not in allowed_extensions:
            tip = fill(
                "Choose one of: {}".format(", ".join(sorted(allowed_extensions)))
            )
            raise click.BadParameter(
                f"Format '{value.suffix}' is not supported.\n\n{tip}"
            )

        return validate_output_path(template_context_class)(ctx, param, value)

    return wrapper


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
        help="Time or segment interval.",
        required=True,
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
