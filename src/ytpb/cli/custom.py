import collections

import click


def get_parameter_by_name(name: str, ctx: click.Context) -> click.Parameter:
    return next((p for p in ctx.command.params if p.name == name), None)
