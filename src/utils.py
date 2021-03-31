import click
import subprocess
import os

from clint.textui import colored

def check_dependencies(compression, crypto, progress):
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

    if progress:
        try:
            subprocess.check_call(["which", "pv"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except:
            raise click.BadOptionUsage("progress", "option progress (default) requires pv in your $PATH")


def check_folder_exists(folder):
    return os.path.exists(folder) and os.path.isdir(folder)


def color_macro(color, func):
    if color:
        return func
    else:
        return lambda x, y, z: x