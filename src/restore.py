import subprocess
import click
from utils import color_macro, s3_url, check_folder_exists
from clint.textui import colored, puts
from datetime import datetime
import os

def do_restore(color, progress, date, bucket, jobname, target):
    # Colors
    yellow = color_macro(color, colored.yellow)
    cyan = color_macro(color, colored.cyan)
    red = color_macro(color, colored.red)
    green = color_macro(color, colored.green)

    # First check if the given backup exists
    # If no date specified, use most recent backup
    puts(f"Trying to restore {cyan(jobname)} from AWS S3 bucket {yellow(bucket)} to {yellow(target)}")

    if not check_folder_exists(target):
        raise RuntimeError(red(f"Folder {target} does not exists"))

    if not date:
        puts("No date supplied, trying to restore most recent backup")
        try:
            out = subprocess.check_output(["aws", "s3", "ls", s3_url(bucket, jobname + "/")]).decode("utf-8")
        except:
            raise RuntimeError(f"Could not list bucket {bucket}/{jobname}, please double check the name and jobname")

        dates = [x.rsplit(" ", 1)[1].strip("/") for x in out.splitlines()]
        dates_sorted = sorted(dates)
        date = dates_sorted[-1]
        puts(f"Most recent backup: {yellow(date)}")
    else:
        try:
            datetime.strptime(date, "%Y-%m-%d_%H-%M-%S")
        except:
            raise RuntimeError(f"date ({date}) has invalid date format, expected %Y-%m-%d_%H-%M-%S")

        try:
            puts(f"Checking if backup for {yellow(date)} exists...", newline=False)
            # Check if backup with that date actually exists
            out = subprocess.check_call(
                ["aws", "s3", "ls", s3_url(bucket, os.path.join(jobname, date))],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            puts(green("OK"))
        except:
            print()
            raise click.BadOptionUsage("date", red(f"No backup found for date {date}"))



    pass