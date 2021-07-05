import os
import sys
import logging
import tempfile
import shlex
import subprocess
import hashlib
import random
import getpass
import atexit

from artiq import __artiq_dir__ as artiq_dir
from artiq.frontend.bit2bin import bit2bin

__all__ = ["LocalClient", "SSHClient"]

logger = logging.getLogger(__name__)


class Client:
    def upload(self, filename, rewriter=None):
        raise NotImplementedError

    def prepare_download(self, filename):
        raise NotImplementedError

    def download(self):
        raise NotImplementedError

    def run_command(self, cmd, **kws):
        raise NotImplementedError


class LocalClient(Client):
    def __init__(self):
        self._tmp = os.path.join(tempfile.gettempdir(), "artiq")

    def upload(self, filename, rewriter=None):
        logger.debug("Uploading {}".format(filename))
        if rewriter is None:
            return filename
        else:
            os.makedirs(self._tmp, exist_ok=True)
            with open(filename, 'rb') as local:
                rewritten = rewriter(local.read())
                tmp_filename = os.path.join(self._tmp, hashlib.sha1(rewritten).hexdigest())
                with open(tmp_filename, 'wb') as tmp:
                    tmp.write(rewritten)
            return tmp_filename

    def prepare_download(self, filename):
        logger.debug("Downloading {}".format(filename))
        return filename

    def download(self):
        pass

    def run_command(self, cmd, **kws):
        logger.debug("Executing {}".format(cmd))
        subprocess.check_call([arg.format(tmp=self._tmp, **kws) for arg in cmd])


class SSHClient(Client):
    def __init__(self, host, jump_host=None):
        if "@" in host:
            self.username, self.host = host.split("@")
        else:
            self.host = host
            self.username = None
        self.jump_host = jump_host
        self.ssh = None
        self.sftp = None
        self._tmpr = "/tmp/artiq-" + getpass.getuser()
        self._tmpl = tempfile.TemporaryDirectory(prefix="artiq")
        self._cached = []
        self._downloads = {}

    def get_ssh(self):
        if self.ssh is None:
            import paramiko
            logging.getLogger("paramiko").setLevel(logging.WARNING)

            if self.jump_host:
                proxy_cmd = "ssh -W {}:22 {}".format(self.host, self.jump_host)
                logger.debug("Using proxy command '{}'".format(proxy_cmd))
                proxy = paramiko.proxy.ProxyCommand(proxy_cmd)
            else:
                proxy = None

            self.ssh = paramiko.SSHClient()
            self.ssh.load_system_host_keys()
            self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.ssh.connect(self.host, username=self.username, sock=proxy)

            logger.debug("Connecting to {}".format(self.host))
        return self.ssh

    def get_transport(self):
        return self.get_ssh().get_transport()

    def get_sftp(self):
        if self.sftp is None:
            self.sftp = self.get_ssh().open_sftp()
            try:
                self._cached = self.sftp.listdir(self._tmpr)
            except OSError:
                self.sftp.mkdir(self._tmpr)
        return self.sftp

    def upload(self, filename, rewriter=lambda x: x):
        with open(filename, 'rb') as local:
            rewritten = rewriter(local.read())
            digest = hashlib.sha1(rewritten).hexdigest()
            remote_filename = "{}/{}".format(self._tmpr, digest)

        sftp = self.get_sftp()
        if digest in self._cached:
            logger.debug("Using cached {}".format(filename))
        else:
            logger.debug("Uploading {}".format(filename))
            # Avoid a race condition by writing into a temporary file
            # and atomically replacing
            with sftp.open(remote_filename + ".~", "wb") as remote:
                remote.write(rewritten)
            try:
                sftp.rename(remote_filename + ".~", remote_filename)
            except IOError:
                # Either it already exists (this is OK) or something else
                # happened (this isn't) and we need to re-raise
                sftp.stat(remote_filename)

        return remote_filename

    def prepare_download(self, filename):
        tmpname = "".join([random.Random().choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
                           for _ in range(6)])
        remote_filename = "{}/{}_{}".format(self._tmpr, tmpname, filename)

        _sftp = self.get_sftp()
        logger.debug("Downloading {}".format(filename))
        self._downloads[filename] = remote_filename

        return remote_filename

    def download(self):
        sftp = self.get_sftp()
        for filename, remote_filename in self._downloads.items():
            sftp.get(remote_filename, filename)

        self._downloads = {}

    def spawn_command(self, cmd, get_pty=False, **kws):
        chan = self.get_transport().open_session()
        chan.set_combine_stderr(True)
        if get_pty:
            chan.get_pty()
        cmd = " ".join([shlex.quote(arg.format(tmp=self._tmpr, **kws)) for arg in cmd])

        # Wrap command in a bash login shell
        cmd = "exec {}".format(cmd)
        cmd = "bash --login -c {}".format(shlex.quote(cmd))

        logger.debug("Executing: {}".format(cmd))
        chan.exec_command(cmd)
        return chan

    def drain(self, chan):
        while True:
            char = chan.recv(1)
            if char == b"":
                break
            sys.stderr.write(char.decode("utf-8", errors='replace'))

    def run_command(self, cmd, **kws):
        self.drain(self.spawn_command(cmd, **kws))

def build_dir (args):
    bin_dir = args.dir
    if bin_dir is None:
        bin_dir = os.path.join(artiq_dir, "board-support")

    needs_artifacts = not args.action or any(
        action in args.action
        for action in ["gateware", "rtm_gateware", "bootloader", "firmware", "load", "rtm_load"])
    variant = args.variant
    if needs_artifacts and variant is None:
        variants = []
        if args.srcbuild:
            for entry in os.scandir(bin_dir):
                if entry.is_dir():
                    variants.append(entry.name)
        else:
            prefix = args.target + "-"
            for entry in os.scandir(bin_dir):
                if entry.is_dir() and entry.name.startswith(prefix):
                    variants.append(entry.name[len(prefix):])
        if args.target == "sayma":
            try:
                variants.remove("rtm")
            except ValueError:
                pass
        if len(variants) == 0:
            raise FileNotFoundError("no variants found, did you install a board binary package?")
        elif len(variants) == 1:
            variant = variants[0]
        else:
            raise ValueError("more than one variant found for selected board, specify -V. "
                "Found variants: {}".format(" ".join(sorted(variants))))
    variant_dir = None
    rtm_variant_dir = None
    if needs_artifacts:
        if args.srcbuild:
            variant_dir = variant
        else:
            variant_dir = args.target + "-" + variant
        if args.target == "sayma":
            if args.srcbuild:
                rtm_variant_dir = "rtm"
            else:
                rtm_variant_dir = "sayma-rtm"
    return (variant, bin_dir, variant_dir, rtm_variant_dir)

def artifact_path(args, bin_dir, this_variant_dir, *path_filename):
    if args.srcbuild:
        # source tree - use path elements to locate file
        return os.path.join(bin_dir, this_variant_dir, *path_filename)
    else:
        # flat tree - all files in the same directory, discard path elements
        *_, filename = path_filename
        return os.path.join(bin_dir, this_variant_dir, filename)

def convert_gateware(bit_filename, header=False):
    bin_handle, bin_filename = tempfile.mkstemp(
        prefix="artiq_", suffix="_" + os.path.basename(bit_filename))
    with open(bit_filename, "rb") as bit_file, \
            open(bin_handle, "wb") as bin_file:
        if header:
            bin_file.write(b"\x00"*8)
        bit2bin(bit_file, bin_file)
        if header:
            magic = 0x5352544d  # "SRTM", see sayma_rtm target
            length = bin_file.tell() - 8
            bin_file.seek(0)
            bin_file.write(magic.to_bytes(4, byteorder="big"))
            bin_file.write(length.to_bytes(4, byteorder="big"))
    atexit.register(lambda: os.unlink(bin_filename))
    return bin_filename
