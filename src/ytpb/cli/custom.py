import collections

import click


class OrderedGroup(click.Group):
    def __init__(self, name=None, commands=None, **attrs):
        super().__init__(name, commands, **attrs)
        self.commands = commands or collections.OrderedDict()

    def list_commands(self, ctx):
        return self.commands


class RewindCommand(click.Command):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.params.insert(0, click.Option())


def get_parameter_by_name(name: str, ctx: click.Context) -> click.Parameter:
    return next((p for p in ctx.command.params if p.name == name), None)
