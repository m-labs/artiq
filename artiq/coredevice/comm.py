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
                   (1, after_idle * 1000, interval * 1000))
    else:
        logger.warning("TCP keepalive not supported on platform '%s', ignored",
                       sys.platform)


def initialize_connection(host, port):
    sock = socket.create_connection((host, port))
    set_keepalive(sock, 10, 10, 3)
    logger.debug("connected to %s:%d", host, port)
    return sock
