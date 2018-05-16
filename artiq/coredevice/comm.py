import sys
import socket
import logging


logger = logging.getLogger(__name__)


def set_keepalive(sock, after_idle, interval, max_fails):
    if sys.platform.startswith("linux"):
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, after_idle)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, interval)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, max_fails)
    elif sys.platform.startswith("win") or sys.platform.startswith("cygwin"):
        # setting max_fails is not supported, typically ends up being 5 or 10
        # depending on Windows version
        sock.ioctl(socket.SIO_KEEPALIVE_VALS,
                   (1, after_idle*1000, interval*1000))
    else:
        logger.warning("TCP keepalive not supported on platform '%s', ignored",
                       sys.platform)


def initialize_connection(host, port, ssh_transport=None):
    if ssh_transport is None:
        sock = socket.create_connection((host, port), 5.0)
        sock.settimeout(None)
        set_keepalive(sock, 3, 2, 3)
        logger.debug("connected to %s:%d", host, port)
    else:
        sock = ssh_transport.open_channel("direct-tcpip", (host, port),
                                          ("localhost", 9999), timeout=5.0)
        ssh_transport.set_keepalive(2)
        logger.debug("connected to %s:%d via SSH transport to %s:%d",
                     host, port, *ssh_transport.getpeername())
    return sock
