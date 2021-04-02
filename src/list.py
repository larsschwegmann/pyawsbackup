import subprocess
import sys
import os
from utils import color_macro, s3_url
from clint.textui import puts, colored
from datetime import datetime

def do_list_buckets(color):
    cyan = color_macro(color, colored.cyan)
    out = subprocess.check_output(["aws", "s3", "ls"]).decode("utf-8")
    for line in out.splitlines():
        [date, name] = line.rsplit(" ", 1)
        puts(cyan(name))

def do_list(jobname, color, bucket):
    cyan = color_macro(color, colored.cyan)

    try:
        out = subprocess.check_output(["aws", "s3", "ls", s3_url(bucket, None)]).decode("utf-8")
    except:
        raise RuntimeError(f"Could not list bucket {bucket}, please double check the name")

    backups = [x.rsplit(" ", 1)[1].strip("/") for x in out.splitlines()]
    backup_map = dict()
    for backup in backups:
        if jobname and not jobname == backup:
            continue

        try:
            dir_out = subprocess.check_output(["aws", "s3", "ls", s3_url(bucket, backup + "/")]).decode("utf-8")
        except:
            raise RuntimeError(f"Could not list bucket {bucket}, please double check the name")

        backup_map[backup] = [x.rsplit(" ", 1)[1].strip("/") for x in dir_out.splitlines()]

    if jobname:
        for date in backup_map[jobname]:
            puts(date)
    else:
        for backup in backups:
            dates_sorted = sorted(backup_map[backup])
            most_recent = dates_sorted[-1]
            puts(f"{cyan(backup)}\t\t {most_recent}")


def do_list_filelist(color, date, bucket, jobname):
    cyan = color_macro(color, colored.cyan)
    red = color_macro(color, colored.red)
    green = color_macro(color, colored.green)
    yellow = color_macro(color, colored.yellow)

    if not date:
        print("No date supplied, listing most recent backup", file=sys.stderr)
        try:
            out = subprocess.check_output(["aws", "s3", "ls", s3_url(bucket, jobname + "/")]).decode("utf-8")
        except:
            raise RuntimeError(f"Could not list bucket {bucket}/{jobname}, please double check the name and jobname")

        dates = [x.rsplit(" ", 1)[1].strip("/") for x in out.splitlines()]
        dates_sorted = sorted(dates)
        date = dates_sorted[-1]
        print(f"Most recent backup: {yellow(date)}", file=sys.stderr)
    else:
        try:
            datetime.strptime(date, "%Y-%m-%d_%H-%M-%S")
        except:
            raise RuntimeError(f"date ({date}) has invalid date format, expected %Y-%m-%d_%H-%M-%S")

        try:
            print(f"Checking if backup for {yellow(date)} exists...", end="", file=sys.stderr)
            # Check if backup with that date actually exists
            out = subprocess.check_call(
                ["aws", "s3", "ls", s3_url(bucket, os.path.join(jobname, date))],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            print(green("OK"))
        except:
            print()
            raise click.BadOptionUsage("date", red(f"No backup found for date {date}"))

    # List contents of folder
    try:
        backup_files = subprocess.check_output(
            ["aws", "s3", "ls", s3_url(bucket, os.path.join(jobname, date) + "/")]
        ).decode("utf-8")
        backup_files = [x.rsplit(" ", 1)[1].strip("/") for x in backup_files.splitlines()]
    except:
        raise RuntimeError(f"Could not list contents of {bucket}/{jobname}/{date}")



