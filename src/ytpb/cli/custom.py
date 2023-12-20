import collections

import click


class GlobalOption(click.Option):
    def __init__(self, *args, **kwargs):
        self.is_global = True
        super().__init__(*args, **kwargs)


class OrderedGroup(click.Group):
    def __init__(self, name=None, commands=None, **attrs):
        super().__init__(name, commands, **attrs)
        self.commands = commands or collections.OrderedDict()

    def list_commands(self, ctx):
        return self.commands


class ConflictingOption(click.Option):
    def __init__(self, *args, **kwargs):
        self.conflicting_options = set(kwargs.pop("conflicting_with", []))
        super().__init__(*args, **kwargs)

    def handle_parse_result(self, ctx, options, args):
        conflicted_with = self.conflicting_options.intersection(options)
        if conflicted_with and self.name in options:
            conflicted_param_hints = [
                get_parameter_by_name(name, ctx).get_error_hint(ctx)
                for name in conflicted_with
            ]
            raise click.UsageError(
                "Option {0} is conflicting with {1}.".format(
                    self.get_error_hint(ctx), ", ".join(conflicted_param_hints)
                )
            )
        return super().handle_parse_result(ctx, options, args)


class RewindCommand(click.Command):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.params.insert(0, click.Option())

        
def get_parameter_by_name(name: str, ctx: click.Context) -> click.Parameter:
    return next((p for p in ctx.command.params if p.name == name), None)
