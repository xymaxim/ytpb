from datetime import datetime, timezone
from pathlib import Path
from textwrap import fill
from typing import Callable

import click
from cloup.constraints import constraint, mutually_exclusive
from jinja2 import TemplateSyntaxError
from jinja2.meta import find_undeclared_variables
from PIL import Image

from ytpb.cli import parameters
from ytpb.cli.common import EARLIEST_DATE_TIMEDELTA
from ytpb.cli.templating import check_is_template


def validate_output_path(template_context_class) -> Callable[..., Path]:
    def wrapper(ctx: click.Context, param: click.Option, value: Path) -> Path:
        if check_is_template(str(value)):
            try:
                parsed = ctx.obj.jinja_environment.parse(str(value))
            except TemplateSyntaxError as exc:
                raise click.BadParameter(
                    f"Bad template syntax, line {exc.lineno}: {exc}"
                )
            undeclared_variables = find_undeclared_variables(parsed)
            context_variables = set(template_context_class.__annotations__.keys())
            if not undeclared_variables.issubset(context_variables):
                unknown_variables = undeclared_variables - context_variables
                raise click.BadParameter(
                    "Unknown template variable(s) found: {}.".format(
                        str(unknown_variables).strip("{}")
                    )
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


interval_option = click.option(
    "-i",
    "--interval",
    metavar="INTERVAL",
    type=parameters.RewindIntervalParamType(),
    help="Time or segment interval.",
    required=True,
)


def config_options(f):
    f = click.option(
        "-C",
        "--config",
        "config_path",
        help="Specifies a path to a configuration file.",
        type=click.Path(path_type=Path),
        is_eager=True,
    )(f)

    f = click.option(
        "--no-config",
        help="Do not load any configuration files.",
        default=False,
        is_flag=True,
        is_eager=True,
    )(f)

    return f


def cache_options(f):
    f = click.option(
        "--force-update-cache",
        help="Force to update cache.",
        is_flag=True,
    )(f)

    f = click.option(
        "--no-cache",
        help="Do not use cache.",
        is_flag=True,
    )(f)

    f = constraint(mutually_exclusive, ["no_cache", "force_update_cache"])(f)

    return f


def logging_options(f):
    f = click.option(
        "--report",
        help="Dump all output to a file. It implies --debug.",
        is_flag=True,
        is_eager=True,
    )(f)

    f = click.option(
        "--debug",
        "debug",
        help="Enable verbose output for debugging.",
        is_flag=True,
        is_eager=True,
    )(f)

    return f


yt_dlp_option = click.option(
    "-Y", "--yt-dlp", is_flag=True, help="Use yt-dlp to extract info."
)


keep_temp_option = click.option(
    "--keep-temp", is_flag=True, help="Keep temporary files."
)
