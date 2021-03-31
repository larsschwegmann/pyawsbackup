import subprocess
import click
from clint.textui import puts, colored

from utils import check_folder_exists, color_macro

def do_backup(compress, encrypt, cert, storage_class, progress, color, dry_run, folder, bucket):
    # Colors
    yellow = color_macro(color, colored.yellow)
    blue = color_macro(color, colored.blue)
    cyan = color_macro(color, colored.cyan)
    red = color_macro(color, colored.red)

    # Check if source directory exists first
    if not check_folder_exists(folder):
        raise click.UsageError(f"no directory found at path {folder}")

    if dry_run:
        puts(f"Backing up {cyan(folder)} to local folder {cyan(dry_run)}")
    else:
        puts(f"Backing up {cyan(folder)} to AWS S3 bucket {yellow(bucket)} (class = {yellow(storage_class)})")

    pass