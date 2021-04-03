import subprocess
import click
import os
import json
import sys
from datetime import datetime
from clint.textui import puts, colored, indent
from utils import check_folder_exists, color_macro, s3_url


def get_s3_pipe(s3_url, storage_class):
    cmd = ["aws", "s3", "cp", "-", s3_url]
    if storage_class:
        cmd.append("--storage-class")
        cmd.append(storage_class)

    aws = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        # stderr=subprocess.DEVNULL
        # universal_newlines=True
    )
    return aws


def get_pv_pipe(stdout):
    pv = subprocess.Popen(
        ["pv", "-f", "-i", "5"],
        stdin=subprocess.PIPE,
        stdout=stdout,
        # stderr=subprocess.PIPE
        # universal_newlines=True
    )
    return pv


def get_openssl_pipe_symmetric(key, stdout):
    if sys.platform == "linux":
        cmd = ["openssl", "enc", "-aes-256-ctr", "-salt", "-pass", f"pass:{key}", "-pbkdf2"]
    elif sys.platform == "darwin":
        # macos ships with LibreSSL which doesnt support -pbkdf2 for whatever reason
        cmd = ["openssl", "enc", "-aes-256-ctr", "-salt", "-pass", f"pass:{key}"]

    openssl = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=stdout,
        # stderr=subprocess.DEVNULL
        # universal_newlines=True
    )
    return openssl


def get_openssl_pipe_asymmetric(cert, stdout):
    openssl = subprocess.Popen(
        ["openssl", "rsautl", "-encrypt", "-pubin", "-inkey", cert],
        stdin=subprocess.PIPE,
        stdout=stdout,
        # stderr=subprocess.DEVNULL
        # universal_newlines=True
    )
    return openssl


def get_tar_pipe(folder, compress, stdout):
    if sys.platform == "linux":
        if compress:
            backup_cmd = ["tar", "-I", "zstd", "--warning=no-file-changed", "-C", "/", "-cf", "-", folder]
        else:
            backup_cmd = ["tar", "--warning=no-file-changed", "-C", "/", "-cf", "-", folder]

        backup_tar = subprocess.Popen(
            backup_cmd,
            stdout=stdout,
            # stderr=subprocess.DEVNULL
            # universal_newlines=True
        )
        return backup_tar
    elif sys.platform == "darwin":
        # tar -I only work with GNU tar, macos ships with BSD tar
        zstd = None
        if compress:
            zstd = subprocess.Popen(
                ["zstd"],
                stdin=subprocess.PIPE,
                stdout=stdout,
                # stderr=subprocess.DEVNULL
                # universal_newlines=True
            )

        backup_tar = subprocess.Popen(
            ["tar", "--warning=no-file-changed", "-C", "/", "-cf", "-", folder],
            stdout=zstd.stdin if zstd else stdout,
            # stderr=subprocess.DEVNULL
            # universal_newlines=True
        )
        return backup_tar


def build_upload_pipeline_symmetric(dry_run, progress, encrypt, key, storage_class, bucket, destfile):
    # Build subprocess chain
    # tar (with/without compression if compress) | openssl (if encrypt) | pv (if progress) | aws cp ( if not dry-run ) / fd (if dry-run)
    # Pipe logic inspired by https://stackoverflow.com/a/9164238/1043495

    # Build chain from back to front
    if dry_run:
        outfile = os.path.join(bucket, destfile)
        out = open(outfile, "wb")
        next_output = out
    else:
        aws = get_s3_pipe(s3_url(bucket, destfile), storage_class)
        next_output = aws

    if progress:
        input = next_output.stdin if hasattr(next_output, "stdin") else next_output
        pv = get_pv_pipe(input)
        next_output = pv

    if encrypt:
        input = next_output.stdin if hasattr(next_output, "stdin") else next_output
        openssl = get_openssl_pipe_symmetric(key, input)
        next_output = openssl

    if dry_run:
        return (next_output, out)
    else:
        return next_output


def build_upload_pipeline_asymmetric(dry_run, progress, encrypt, cert, storage_class, bucket, destfile):
    # Build subprocess chain
    # tar (with/without compression if compress) | openssl (if encrypt) | pv (if progress) | aws cp ( if not dry-run ) / fd (if dry-run)
    # Pipe logic inspired by https://stackoverflow.com/a/9164238/1043495

    # Build chain from back to front
    if dry_run:
        outfile = os.path.join(bucket, destfile)
        out = open(outfile, "wb")
        next_output = out
    else:
        aws = get_s3_pipe(s3_url(bucket, destfile), storage_class)
        next_output = aws

    if progress:
        input = next_output.stdin if hasattr(next_output, "stdin") else next_output
        pv = get_pv_pipe(input)
        next_output = pv

    if encrypt:
        input = next_output.stdin if hasattr(next_output, "stdin") else next_output
        openssl = get_openssl_pipe_asymmetric(cert, input)
        next_output = openssl

    if dry_run:
        return (next_output, out)
    else:
        return next_output


# Encryption logic heavily inspired and partly adopted by https://github.com/leanderseidlitz/aws-backup/blob/master/awsbackup.sh
def do_backup(compress, encrypt, cert, storage_class, jobname, progress, color, dry_run, folder, bucket):
    # Colors
    yellow = color_macro(color, colored.yellow)
    cyan = color_macro(color, colored.cyan)
    red = color_macro(color, colored.red)
    green = color_macro(color, colored.green)

    date = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    if not jobname:
        jobname = os.path.basename(os.path.normpath(folder))

    # Check if source directory exists first
    if not check_folder_exists(folder):
        raise click.UsageError(f"no directory found at src path {folder}")

    if dry_run and not check_folder_exists(bucket):
        raise click.UsageError(f"no directory found at dest path {bucket}")

    # Print what we are going to do
    if dry_run:
        puts(f"Backing up {cyan(folder)} to local folder {cyan(bucket)} (dry-run)")
    else:
        puts(f"Backing up {cyan(folder)} to AWS S3 bucket {yellow(bucket)} (class = {yellow(storage_class)})")

    puts(f"Jobname: {cyan(jobname)}")


    # Create the parent directory first
    jobdir_name = os.path.join(jobname, date)
    if dry_run:
        # Create directory locally
        puts("Creating job directory...", newline=False)
        try:
            jobdir = os.path.join(bucket, jobdir_name)
            os.mkdir(jobdir)
            puts(green("DONE"))
        except:
            raise RuntimeError(f"Could not create job directory at path {jobdir}")

    tarkey = None
    listkey = None
    if encrypt:
        # Generate symmetric keys for tar + list
        puts("Generating symmetric keys for encryption...", newline=False)
        sys.stdout.flush()
        try:
            tarkey = subprocess.check_output(
                ["openssl", "rand", "-hex", "16"],
                stderr=subprocess.DEVNULL
            ).decode("utf-8"),
            listkey = subprocess.check_output(
                ["openssl", "rand", "-hex", "16"],
                stderr=subprocess.DEVNULL
            ).decode("utf-8"),
            puts(green("DONE"))
            sys.stdout.flush()
        except:
            raise RuntimeError(f"Could not generate symmetric keys for backup job")

        # Generate Metafile contents
        meta_content = {
            "tarkey": tarkey,
            "listkey": listkey
        }

        meta_bin = json.dumps(meta_content).encode("utf-8")
        if encrypt:
            meta_name = f"{jobname}.meta.enc"
        else:
            meta_name = f"{jobname}.meta"

        puts("Sending Metafile...", newline=False)
        sys.stdout.flush()

        # Build chain from back to front
        meta_pipeline = build_upload_pipeline_asymmetric(dry_run, progress, encrypt, cert, None, bucket,
                                                         os.path.join(jobdir_name, meta_name))
        if dry_run:
            (meta_pipeline, meta_outfile) = meta_pipeline
        meta_pipeline.communicate(meta_bin)

        if dry_run:
            meta_outfile.close()

        puts(green("DONE"))
        sys.stdout.flush()

    # Send file list
    puts("Sending file list...")
    sys.stdout.flush()
    file_list_name = f"{jobname}.list.aes" if encrypt else f"{jobname}.list"
    file_list_pipeline = build_upload_pipeline_symmetric(dry_run, progress, encrypt, listkey, None, bucket,
                                                         os.path.join(jobdir_name, file_list_name))
    if dry_run:
        (file_list_pipeline, file_list_outfile) = file_list_pipeline
    pipeline_input = file_list_pipeline.stdin if hasattr(file_list_pipeline, "stdin") else file_list_pipeline
    filelist_tar = subprocess.Popen(
        ["tar", "-C", "/", "-cf", "-", "--format", "mtree", "--options=sha256", folder],
        stdout=pipeline_input,
        stderr=subprocess.DEVNULL
    )
    filelist_tar.wait()
    if dry_run:
        file_list_outfile.close()

    puts(green("DONE"))
    sys.stdout.flush()

    # Send actual backup
    puts("Sending backup...")
    sys.stdout.flush()
    backup_name = f"{jobname}.tar"
    if compress:
        backup_name = f"{backup_name}.zstd"
    if encrypt:
        backup_name = f"{backup_name}.aes"

    backup_pipeline = build_upload_pipeline_symmetric(dry_run, progress, encrypt, tarkey, storage_class, bucket,
                                                      os.path.join(jobdir_name, backup_name))
    if dry_run:
        (backup_pipeline, backup_outfile) = backup_pipeline

    pipeline_input = backup_pipeline.stdin if hasattr(backup_pipeline, "stdin") else backup_pipeline

    backup_tar = get_tar_pipe(folder, compress, pipeline_input)
    backup_tar.wait()
    if dry_run:
        backup_outfile.close()

    puts(green("DONE"))
    sys.stdout.flush()
