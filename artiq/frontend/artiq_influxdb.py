#!/usr/bin/env python3

import argparse
import logging
import asyncio
import atexit
import fnmatch
from functools import partial
import time

import numpy as np
import aiohttp

from artiq.tools import *
from artiq.protocols.sync_struct import Subscriber
from artiq.protocols.pc_rpc import Server
from artiq.protocols import pyon


logger = logging.getLogger(__name__)


def get_argparser():
    parser = argparse.ArgumentParser(
        description="ARTIQ data to InfluxDB bridge",
        epilog="Pattern matching works as follows. "
               "The default action on a key (dataset name) is to log it. "
               "Then the patterns are traversed in order and glob-matched "
               "with the key. "
               "Optional + and - pattern prefixes specify whether to ignore or "
               "log keys matching the rest of the pattern. "
               "Default (in the absence of prefix) is to ignore. Last matched "
               "pattern takes precedence.")
    group = parser.add_argument_group("master")
    group.add_argument(
        "--server-master", default="::1",
        help="hostname or IP of the master to connect to")
    group.add_argument(
        "--port-master", default=3250, type=int,
        help="TCP port to use to connect to the master")
    group.add_argument(
        "--retry-master", default=5.0, type=float,
        help="retry timer for reconnecting to master")
    group = parser.add_argument_group("database")
    group.add_argument(
        "--baseurl-db", default="http://localhost:8086",
        help="base URL to access InfluxDB (default: %(default)s)")
    group.add_argument(
        "--user-db", default="", help="InfluxDB username")
    group.add_argument(
        "--password-db", default="", help="InfluxDB password")
    group.add_argument(
        "--database", default="db", help="database name to use")
    group.add_argument(
        "--table", default="lab", help="table name to use")
    group = parser.add_argument_group("filter")
    group.add_argument(
        "--pattern-file", default="influxdb_patterns.cfg",
        help="file to load the patterns from (default: %(default)s). "
             "If the file is not found, no patterns are loaded "
             "(everything is logged).")
    simple_network_args(parser, [("control", "control", 3248)])
    verbosity_args(parser)
    return parser


def format_influxdb(v):
    if np.issubdtype(type(v), np.bool_):
        return "bool={}".format(v)
    if np.issubdtype(type(v), np.integer):
        return "int={}i".format(v)
    if np.issubdtype(type(v), np.floating):
        return "float={}".format(v)
    if np.issubdtype(type(v), np.str_):
        return "str=\"{}\"".format(v.replace('"', '\\"'))
    return "pyon=\"{}\"".format(pyon.encode(v).replace('"', '\\"'))


class DBWriter(TaskObject):
    def __init__(self, base_url, user, password, database, table):
        self.base_url = base_url
        self.user = user
        self.password = password
        self.database = database
        self.table = table

        self._queue = asyncio.Queue(100)

    def update(self, k, v):
        try:
            self._queue.put_nowait((k, v, time.time()))
        except asyncio.QueueFull:
            logger.warning("failed to update dataset '%s': "
                           "too many pending updates", k)

    async def _do(self):
        while True:
            k, v, t = await self._queue.get()
            url = self.base_url + "/write"
            params = {"u": self.user, "p": self.password, "db": self.database,
                      "precision": "ms"}
            data = "{},dataset={} {} {}".format(
                self.table, k, format_influxdb(v), round(t*1e3))
            try:
                response = await aiohttp.request(
                    "POST", url, params=params, data=data)
            except:
                logger.warning("got exception trying to update '%s'",
                               k, exc_info=True)
            else:
                if response.status not in (200, 204):
                    content = (await response.content.read()).decode().strip()
                    logger.warning("got HTTP status %d "
                                   "trying to update '%s': %s",
                                   response.status, k, content)
                response.close()


class _Mock:
    def __setitem__(self, k, v):
        pass

    def __getitem__(self, k):
        return self

    def __delitem__(self, k):
        pass


class Datasets:
    def __init__(self, filter_function, writer, init):
        self.filter_function = filter_function
        self.writer = writer

    def __setitem__(self, k, v):
        if self.filter_function(k):
            self.writer.update(k, v[1])

    # ignore mutations
    def __getitem__(self, k):
        return _Mock()

    # ignore deletions
    def __delitem__(self, k):
        pass


class MasterReader(TaskObject):
    def __init__(self, server, port, retry, filter_function, writer):
        self.server = server
        self.port = port
        self.retry = retry

        self.filter_function = filter_function
        self.writer = writer

    async def _do(self):
        subscriber = Subscriber(
            "datasets",
            partial(Datasets, self.filter_function, self.writer))
        while True:
            try:
                await subscriber.connect(self.server, self.port)
                try:
                    await asyncio.wait_for(subscriber.receive_task, None)
                finally:
                    await subscriber.close()
            except (ConnectionAbortedError, ConnectionError,
                    ConnectionRefusedError, ConnectionResetError) as e:
                logger.warning("Connection to master failed (%s: %s)",
                    e.__class__.__name__, str(e))
            else:
                logger.warning("Connection to master lost")
            logger.warning("Retrying in %.1f seconds", self.retry)
            await asyncio.sleep(self.retry)


class Filter:
    def __init__(self, pattern_file):
        self.pattern_file = pattern_file
        self.scan_patterns()

    def scan_patterns(self):
        """(Re)load the patterns file."""
        try:
            with open(self.pattern_file, "r") as f:
                self.patterns = []
                for line in f:
                    line = line.rstrip()
                    if line:
                        self.patterns.append(line)
        except FileNotFoundError:
            logger.info("no pattern file found, logging everything")
            self.patterns = []

    # Privatize so that it is not shown in artiq_rpctool list-methods.
    def _filter(self, k):
        take = "+"
        for pattern in self.patterns:
            sign = "-"
            if pattern[0] in "+-":
                sign, pattern = pattern[0], pattern[1:]
            if fnmatch.fnmatchcase(k, pattern):
                take = sign
        return take == "+"

    def get_patterns(self):
        """Show existing patterns."""
        return self.patterns


def main():
    args = get_argparser().parse_args()
    init_logger(args)

    loop = asyncio.get_event_loop()
    atexit.register(loop.close)

    writer = DBWriter(args.baseurl_db,
                      args.user_db, args.password_db,
                      args.database, args.table)
    writer.start()
    atexit_register_coroutine(writer.stop)

    filter = Filter(args.pattern_file)
    rpc_server = Server({"influxdb_filter": filter}, builtin_terminate=True)
    loop.run_until_complete(rpc_server.start(bind_address_from_args(args),
                                             args.port_control))
    atexit_register_coroutine(rpc_server.stop)

    reader = MasterReader(args.server_master, args.port_master,
                          args.retry_master, filter._filter, writer)
    reader.start()
    atexit_register_coroutine(reader.stop)

    loop.run_until_complete(rpc_server.wait_terminate())


if __name__ == "__main__":
    main()
