#!/usr/bin/env python3

import argparse
import logging
import asyncio
import atexit
import time

import aiohttp
import numpy as np

from artiq.protocols.sync_struct import Subscriber
from artiq.tools import (add_common_args, simple_network_args, TaskObject,
                         init_logger, atexit_register_coroutine,
                         bind_address_from_args)
from artiq.protocols.pc_rpc import Server
from artiq.protocols import pyon


logger = logging.getLogger(__name__)


def get_argparser():
    parser = argparse.ArgumentParser(
        description="ARTIQ schedule InfluxDB logger bridge",
        epilog="Listens to schedule updates on the master experiment schedule "
               "and submits schedule additions and removals to the InfluxDB "
               "database. Other schedule changes, such as transitions between "
               "pipeline states (prepare, prepare_done, running, etc.) are "
               "ignored. Typical high cardinality metadata is logged as "
               "fields while low cardinality data is logged as tags. "
               "The initially obtained complete state is logged as a 'clear' "
               "entry followed by the addition of all entries.")
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
        "--table", default="schedule", help="table name to use")
    simple_network_args(parser, [("control", "control", 3275)])
    add_common_args(parser)
    return parser


def format_influxdb(v, tag=True):
    if np.issubdtype(type(v), np.bool_):
        return "{}".format(v)
    if np.issubdtype(type(v), np.integer):
        return "{}i".format(v)
    if np.issubdtype(type(v), np.floating):
        return "{}".format(v)
    if not np.issubdtype(type(v), np.str_):
        v = pyon.encode(v)
    if tag:
        for i in ",= ":
            v = v.replace(i, "\\" + i)
        return v
    else:
        return "\"{}\"".format(v.replace('"', '\\"'))


class DBWriter(TaskObject):
    def __init__(self, base_url, user, password, database, table):
        self.base_url = base_url
        self.user = user
        self.password = password
        self.database = database
        self.table = table

        self._queue = asyncio.Queue(100)

    def update(self, fields, tags):
        try:
            self._queue.put_nowait((fields, tags, time.time()))
        except asyncio.QueueFull:
            logger.warning("failed to update schedule: "
                           "too many pending updates")

    async def _do(self):
        async with aiohttp.ClientSession() as session:
            while True:
                fields, tags, timestamp = await self._queue.get()
                url = self.base_url + "/write"
                params = {"u": self.user, "p": self.password,
                          "db": self.database, "precision": "ms"}
                tags = ",".join("{}={}".format(
                    k, format_influxdb(v, tag=True))
                                for (k, v) in tags.items())
                fields = ",".join("{}={}".format(
                    k, format_influxdb(v, tag=False))
                                  for (k, v) in fields.items())
                data = "{},{} {} {}".format(
                    self.table, tags, fields, round(timestamp*1e3))
                try:
                    response = await session.post(
                        url, params=params, data=data)
                except:
                    logger.warning("got exception trying to update schedule",
                                   exc_info=True)
                else:
                    if response.status not in (200, 204):
                        content = (
                            await response.content.read()).decode().strip()
                        logger.warning("got HTTP status %d "
                                       "trying to update schedule: %s",
                                       response.status, content)
                    response.close()


class Log(dict):
    def __init__(self, writer):
        self.writer = writer

    def init(self, x):
        self.clear()
        self.update(x)
        self.writer.update({"rid": -1}, {"status": "clear"})
        for k, v in self.items():
            self.notify_cb(dict(action="setitem", key=k, value=v))
        return self

    def notify_cb(self, mod):
        if not mod.get("path"):
            if mod["action"] == "setitem":
                rid = mod["key"]
                v = mod["value"]
                logger.debug("added: %s: %s", rid, v)
                self.writer.update(
                    fields={
                        "rid": rid,
                        "log_level": v["expid"]["log_level"],
                        "priority": v["priority"],
                        "due_date": v["due_date"] or -1.,
                        "arguments": v["expid"].get("arguments", {}),
                        "repo_rev": v["expid"]["repo_rev"],
                        "flush": v["flush"],
                    },
                    tags={
                        "status": "add",
                        "class_name": v["expid"]["class_name"],
                        "file": v["expid"]["file"],
                        "pipeline": v["pipeline"],
                    })
            elif mod["action"] == "delitem":
                rid = mod["key"]
                logger.debug("removed: %s", rid)
                self.writer.update({"rid": rid}, {"status": "remove"})
        elif (mod["action"] == "setitem" and mod["key"] == "status"
              and mod["value"] == "running"):
            rid = mod["path"][0]
            logger.debug("run: %s", rid)

    def disconnect_cb(self):
        logger.warn("disconnect")


class MasterReader(TaskObject):
    def __init__(self, server, port, retry, writer):
        self.server = server
        self.port = port
        self.retry = retry

        self.writer = writer

    async def _do(self):
        subscriber = Subscriber(
            "schedule",
            target_builder=self.writer.init,
            notify_cb=self.writer.notify_cb,
            disconnect_cb=self.writer.disconnect_cb)
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
            except Exception as e:
                logger.exception(e)
            else:
                logger.warning("Connection to master lost")
            logger.warning("Retrying in %.1f seconds", self.retry)
            await asyncio.sleep(self.retry)


class Logger:
    def ping(self):
        return True


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

    log = Log(writer)

    server = Logger()
    rpc_server = Server({"schedule_logger": server}, builtin_terminate=True)
    loop.run_until_complete(rpc_server.start(
        bind_address_from_args(args), args.port_control))
    atexit_register_coroutine(rpc_server.stop)

    reader = MasterReader(args.server_master, args.port_master,
                          args.retry_master, log)
    reader.start()
    atexit_register_coroutine(reader.stop)

    loop.run_until_complete(rpc_server.wait_terminate())


if __name__ == "__main__":
    main()
