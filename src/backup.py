import subprocess
import click
import os
import json
import sys
from datetime import datetime
from clint.textui import colored, indent
from utils import check_folder_exists, color_macro, s3_url


def get_s3_pipe(s3_url, storage_class, input):
    cmd = ["aws", "s3", "cp", "-", s3_url]
    if storage_class:
        cmd.append("--storage-class")
        cmd.append(storage_class)

    aws = subprocess.Popen(
        cmd,
        stdin=input if input else subprocess.PIPE,
        stdout=subprocess.DEVNULL
    )
    return aws


def get_pv_pipe(input):
    pv = subprocess.Popen(
        ["pv", "-f"],
        stdin=input if input else subprocess.PIPE,
        stdout=subprocess.PIPE
    )
    return pv


def get_openssl_pipe_symmetric(key, input):
    if sys.platform == "linux":
        cmd = ["openssl", "enc", "-aes-256-ctr", "-salt", "-pass", f"pass:{key}", "-pbkdf2"]
    elif sys.platform == "darwin":
        # macos ships with LibreSSL which doesnt support -pbkdf2 for whatever reason
        cmd = ["openssl", "enc", "-aes-256-ctr", "-salt", "-pass", f"pass:{key}"]

    openssl = subprocess.Popen(
        cmd,
        stdin=input if input else subprocess.PIPE,
        stdout=subprocess.PIPE
    )
    return openssl


def get_openssl_pipe_asymmetric(cert):
    openssl = subprocess.Popen(
        ["openssl", "rsautl", "-encrypt", "-pubin", "-inkey", cert],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE
    )
    return openssl


def get_tar_pipe(folder, compress):
    tar_name = "gtar" if sys.platform == "darwin" else "tar"
    if compress:
        #if sys.platform == "darwin":
        #    raise RuntimeError("Compression with zstd not supported on macos with BSD tar")
        backup_cmd = [tar_name, "-I", "zstd", "--warning=no-file-changed", "-C", "/", "-cf", "-", folder]
    else:
        backup_cmd = [tar_name, "--warning=no-file-changed", "-C", "/", "-cf", "-", folder]

    backup_tar = subprocess.Popen(
        backup_cmd,
        stdout=subprocess.PIPE
    )
    return backup_tar


def build_upload_pipeline_symmetric(input, dry_run, progress, encrypt, key, storage_class, bucket, destfile):
    # Build subprocess chain
    pipe = [input]

    if encrypt:
        openssl = get_openssl_pipe_symmetric(key, pipe[-1].stdout)
        pipe.append(openssl)

    if progress:
        pv = get_pv_pipe(pipe[-1].stdout)
        pipe.append(pv)

    if dry_run:
        # TODO use dd
        pass
    else:
        aws = get_s3_pipe(s3_url(bucket, destfile), storage_class, pipe[-1].stdout)
        pipe.append(aws)

    return pipe


def build_upload_pipeline_asymmetric(dry_run, progress, encrypt, cert, storage_class, bucket, destfile):
    # Build subprocess pipeline chain
    pipe = []
    if encrypt:
        openssl = get_openssl_pipe_asymmetric(cert)
        pipe.append(openssl)

    if progress:
        pv = get_pv_pipe(pipe[-1].stdout if len(pipe) > 0 else None)
        pipe.append(pv)

    if dry_run:
        # TODO use dd
        pass
    else:
        aws = get_s3_pipe(s3_url(bucket, destfile), storage_class, pipe[-1].stdout if len(pipe) > 0 else None)
        pipe.append(aws)

    return pipe


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

    #if compress and sys.platform == "darwin":
    #    raise RuntimeError("Compression not support on macOS")

    # Check if source directory exists first
    if not check_folder_exists(folder):
        raise click.UsageError(f"no directory found at src path {folder}")

    if dry_run and not check_folder_exists(bucket):
        raise click.UsageError(f"no directory found at dest path {bucket}")

    # Print what we are going to do
    if dry_run:
        print(f"Backing up {cyan(folder)} to local folder {cyan(bucket)} (dry-run)")
    else:
        print(f"Backing up {cyan(folder)} to AWS S3 bucket {yellow(bucket)} (class = {yellow(storage_class)})")

    print(f"Jobname: {cyan(jobname)}")


    # Create the parent directory first
    jobdir_name = os.path.join(jobname, date)
    if dry_run:
        # Create directory locally
        print("Creating job directory...", end="")
        try:
            jobdir = os.path.join(bucket, jobdir_name)
            os.mkdir(jobdir)
            print(green("DONE"))
        except:
            raise RuntimeError(f"Could not create job directory at path {jobdir}")

    tarkey = None
    listkey = None
    if encrypt:
        # Generate symmetric keys for tar + list
        print("Generating symmetric keys for encryption...", end="", flush=True)
        try:
            tarkey = subprocess.check_output(
                ["openssl", "rand", "-hex", "16"],
                stderr=subprocess.DEVNULL
            ).decode("utf-8").splitlines()[0]
            listkey = subprocess.check_output(
                ["openssl", "rand", "-hex", "16"],
                stderr=subprocess.DEVNULL
            ).decode("utf-8").splitlines()[0]
            print(green("DONE"), flush=True)
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

        print("Sending Metafile...", end="" if not progress else "\n", flush=True)

        # Build chain from back to front
        meta_pipeline = build_upload_pipeline_asymmetric(dry_run, progress, encrypt, cert, None, bucket,
                                                         os.path.join(jobdir_name, meta_name))
        meta_pipeline[0].communicate(meta_bin)
        for i in range(1, len(meta_pipeline)):
            meta_pipeline[i - 1].stdout.close()
            meta_pipeline[i].wait()

        print(green("DONE"), flush=True)

    # Send file list
    print("Sending file list...", flush=True)
    file_list_name = f"{jobname}.list.aes" if encrypt else f"{jobname}.list"

    filelist_tar = subprocess.Popen(
        ["bsdtar", "-C", "/", "-cf", "-", "--format", "mtree", "--options=sha256", folder],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL
    )

    file_list_pipeline = build_upload_pipeline_symmetric(filelist_tar, dry_run, False, encrypt, listkey, None, bucket,
                                                         os.path.join(jobdir_name, file_list_name))

    for i in range(1, len(file_list_pipeline)):
        file_list_pipeline[i - 1].stdout.close()
        file_list_pipeline[i].wait()

    print(green("DONE"), flush=True)

    # Send actual backup
    print("Sending backup...", flush=True)
    backup_name = f"{jobname}.tar"
    if compress:
        backup_name = f"{backup_name}.zstd"
    if encrypt:
        backup_name = f"{backup_name}.aes"

    backup_tar = get_tar_pipe(folder, compress)

    backup_pipeline = build_upload_pipeline_symmetric(backup_tar, dry_run, progress, encrypt, tarkey, storage_class, bucket,
                                                      os.path.join(jobdir_name, backup_name))

    for i in range(1, len(backup_pipeline)):
        backup_pipeline[i - 1].stdout.close()
        backup_pipeline[i].wait()

    print(green("DONE"))
