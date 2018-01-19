import os
import sys
import logging
import tempfile
import shutil
import shlex
import subprocess
import hashlib

__all__ = ["LocalClient", "SSHClient"]

logger = logging.getLogger(__name__)


class Client:
    def transfer_file(self, filename, rewriter=None):
        raise NotImplementedError

    def run_command(self, cmd, **kws):
        raise NotImplementedError


class LocalClient(Client):
    def __init__(self):
        self._tmp = os.path.join(tempfile.gettempdir(), "artiq")

    def transfer_file(self, filename, rewriter=None):
        logger.debug("Transferring {}".format(filename))
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

    def run_command(self, cmd, **kws):
        logger.debug("Executing {}".format(cmd))
        subprocess.check_call([arg.format(tmp=self._tmp, **kws) for arg in cmd])


class SSHClient(Client):
    def __init__(self, host):
        self.host = host
        self.ssh = None
        self.sftp = None
        self._tmp = "/tmp/artiq"
        self._cached = []

    def get_ssh(self):
        if self.ssh is None:
            import paramiko
            logging.getLogger("paramiko").setLevel(logging.WARNING)
            self.ssh = paramiko.SSHClient()
            self.ssh.load_system_host_keys()
            self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.ssh.connect(self.host)
            logger.debug("Connecting to {}".format(self.host))
        return self.ssh

    def get_transport(self):
        return self.get_ssh().get_transport()

    def get_sftp(self):
        if self.sftp is None:
            self.sftp = self.get_ssh().open_sftp()
            try:
                self._cached = self.sftp.listdir(self._tmp)
            except OSError:
                self.sftp.mkdir(self._tmp)
        return self.sftp

    def transfer_file(self, filename, rewriter=lambda x: x):
        sftp = self.get_sftp()
        with open(filename, 'rb') as local:
            rewritten = rewriter(local.read())
            digest = hashlib.sha1(rewritten).hexdigest()
            remote_filename = os.path.join(self._tmp, digest)
            if digest in self._cached:
                logger.debug("Using cached {}".format(filename))
            else:
                logger.debug("Transferring {}".format(filename))
                with sftp.open(remote_filename, 'wb') as remote:
                    remote.write(rewritten)
        return remote_filename

    def spawn_command(self, cmd, get_pty=False, **kws):
        chan = self.get_transport().open_session()
        chan.set_combine_stderr(True)
        if get_pty:
            chan.get_pty()
        cmd = " ".join([shlex.quote(arg.format(tmp=self._tmp, **kws)) for arg in cmd])
        logger.debug("Executing {}".format(cmd))
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
