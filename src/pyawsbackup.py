import click
from functools import reduce

from utils import check_dependencies
from backup import do_backup

# Custom Click extension
class RefinementOption(click.Option):
    def __init__(self, *args, **kwargs):
        self.refines  = kwargs.pop("refines")
        assert self.refines, "'refines' parameter is required"
        assert len(self.refines) > 0, "'refines' parameter needs to have atleast 1 element"
        super(RefinementOption, self).__init__(*args, **kwargs)

    def handle_parse_result(self, ctx, opts, args):
        we_are_present = self.name in opts
        other_present = reduce(lambda acc, x: acc and x in opts, self.refines, False)

        if not other_present and we_are_present:
            if len(self.refines) > 1:
                raise click.UsageError(f"Illegal usage: {self.name} requires one of the options {', '.join(self.refines)}")
            else:
                raise click.UsageError(f"Illegal usage: {self.name} requires option {self.refines[0]}")

        return super(RefinementOption, self).handle_parse_result(ctx, opts, args)

# CLI Setup
@click.group()
def cli():
    pass


@cli.command(name="backup")
@click.option("--compress", "-c", default=False, is_flag=True)
@click.option("--encrypt", "-e", default=False, is_flag=True)
@click.option("--cert", cls=RefinementOption, refines=["encrypt"], default="test")
@click.option("--storage-class", type=click.Choice([
    # Taken from https://docs.aws.amazon.com/cli/latest/reference/s3/cp.html#options
    "STANDARD",
    "REDUCED_REDUNDANCY",
    "STANDARD_IA",
    "ONEZONE_IA",
    "INTELLIGENT_TIERING",
    "GLACIER",
    "DEEP_ARCHIVE",
]), default="STANDARD")
@click.option("--progress/--no-progress", default=True, is_flag=True)
@click.option("--color/--no-color", default=True, is_flag=True)
@click.option("--dry-run", type=str)
@click.argument("folder")
@click.argument("bucket")
def backup(compress, encrypt, cert, storage_class, progress, color, dry_run, folder, bucket):
    check_dependencies(compress, encrypt, progress)
    do_backup(compress, encrypt, cert, storage_class, progress, color, dry_run, folder, bucket)
    pass

@cli.command(name="restore")
@click.argument("folder")
def restore(folder):
    pass


if __name__ == '__main__':
    cli(auto_envvar_prefix='PYAWSBACKUP')
