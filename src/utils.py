import click
import subprocess
import os

from clint.textui import colored

def check_dependencies(compression, crypto):
    try:
        subprocess.check_call(["which", "tar"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except:
        raise click.UsageError("pyawsbackup requires the tar utility to be installed in your $PATH")

    try:
        subprocess.check_call(["which", "aws"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except:
        raise click.UsageError("pyawsbackup requires the aws cli to be installed in your $PATH")

    if crypto:
        try:
            subprocess.check_call(["which", "openssl"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except:
            raise click.BadOptionUsage("encrypt", "option encrypt requires openssl in your $PATH")

    if compression:
        try:
            subprocess.check_call(["which", "zstd"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except:
            raise click.BadOptionUsage("compress", "option compress requires zstd in your $PATH")


def supports_pv():
    try:
        subprocess.check_call(["which", "pv"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except:
        return False


def check_folder_exists(folder):
    return os.path.exists(folder) and os.path.isdir(folder)


def color_macro(color, func):
    if color:
        return func
    else:
        return lambda *args: args[0]


def s3_url(bucket, path):
    if path:
        return f"s3://{bucket}/{path}"
    else:
        return f"s3://{bucket}"