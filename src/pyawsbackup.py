import click
from functools import reduce
from clint.textui import puts, colored
from utils import check_dependencies, supports_pv, color_macro
from backup import do_backup
from list import do_list, do_list_buckets, do_list_filelist
from restore import do_restore

# Custom Click extension
class RefinementOption(click.Option):
    def __init__(self, *args, **kwargs):
        self.refines  = kwargs.pop("refines")
        assert self.refines, "'refines' parameter is required"
        assert len(self.refines) > 0, "'refines' parameter needs to have atleast 1 element"
        super(RefinementOption, self).__init__(*args, **kwargs)

    def handle_parse_result(self, ctx, opts, args):
        we_are_present = self.name in opts
        other_present = reduce(lambda acc, x: acc or x in opts, self.refines, False)

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
@click.option("--jobname", type=str)
@click.option("--progress/--no-progress", default=True, is_flag=True)
@click.option("--color/--no-color", default=True, is_flag=True)
@click.option("--dry-run", default=False, is_flag=True)
@click.argument("folder")
@click.argument("bucket")
def backup(compress, encrypt, cert, storage_class, jobname, progress, color, dry_run, folder, bucket):
    check_dependencies(compress, encrypt)
    yellow = color_macro(color, colored.yellow)
    pv_support = supports_pv()
    if not pv_support:
        puts(f"{yellow('Warning')}: progress enabled, but pv not found in PATH. Falling back to no-progress")
    do_backup(compress, encrypt, cert, storage_class, jobname, progress and pv_support, color, dry_run, folder, bucket)
    pass

@cli.command(name="list-buckets")
@click.option("--color/--no-color", default=True, is_flag=True)
def list_buckets(color):
    check_dependencies(False, False)
    do_list_buckets(color)

@cli.command(name="list")
@click.option("--jobname", type=str)
@click.option("--color/--no-color", default=True, is_flag=True)
@click.argument("bucket")
def list(jobname, color, bucket):
    check_dependencies(False, False)
    do_list(jobname, color, bucket)

@cli.command(name="list-content")
@click.option("--color/--no-color", default=True, is_flag=True)
@click.option("--date", type=str)
@click.argument("bucket")
@click.argument("jobname")
def list_contents(color, date, bucket, jobname):
    do_list_filelist(color, date, bucket, jobname)

@cli.command(name="restore")
@click.option("--color/--no-color", default=True, is_flag=True)
@click.option("--progress/--no-progress", default=True, is_flag=True)
@click.option("--date", type=str)
@click.argument("bucket")
@click.argument("jobname")
@click.argument("target")
def restore(color, progress, date, bucket, jobname, target):
    yellow = color_macro(color, colored.yellow)
    pv_support = supports_pv()
    if not pv_support:
        puts(f"{yellow('Warning')}: progress enabled, but pv not found in PATH. Falling back to no-progress")
    do_restore(color, progress and pv_support, date, bucket, jobname, target)


if __name__ == '__main__':
    cli(auto_envvar_prefix='PYAWSBACKUP')
