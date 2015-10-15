#!/usr/bin/env python3

import asyncio
import argparse
import atexit
import os

from artiq.protocols.pc_rpc import Server as RPCServer
from artiq.protocols.sync_struct import Publisher
from artiq.protocols.logging import Server as LoggingServer
from artiq.master.log import log_args, init_log, log_worker
from artiq.master.databases import DeviceDB, DatasetDB
from artiq.master.scheduler import Scheduler
from artiq.master.worker_db import get_last_rid
from artiq.master.repository import FilesystemBackend, GitBackend, Repository


def get_argparser():
    parser = argparse.ArgumentParser(description="ARTIQ master")

    group = parser.add_argument_group("network")
    group.add_argument(
        "--bind", default="::1",
        help="hostname or IP address to bind to")
    group.add_argument(
        "--port-notify", default=3250, type=int,
        help="TCP port to listen to for notifications (default: %(default)d)")
    group.add_argument(
        "--port-control", default=3251, type=int,
        help="TCP port to listen to for control (default: %(default)d)")
    group.add_argument(
        "--port-logging", default=1066, type=int,
        help="TCP port to listen to for remote logging (default: %(default)d)")

    group = parser.add_argument_group("databases")
    group.add_argument("--device-db", default="device_db.pyon",
                       help="device database file (default: '%(default)s')")
    group.add_argument("--dataset-db", default="dataset_db.pyon",
                       help="dataset file (default: '%(default)s')")

    group = parser.add_argument_group("repository")
    group.add_argument(
        "-g", "--git", default=False, action="store_true",
        help="use the Git repository backend")
    group.add_argument(
        "-r", "--repository", default="repository",
        help="path to the repository (default: '%(default)s')")

    log_args(parser)

    return parser


def main():
    args = get_argparser().parse_args()
    log_buffer = init_log(args)
    if os.name == "nt":
        loop = asyncio.ProactorEventLoop()
        asyncio.set_event_loop(loop)
    else:
        loop = asyncio.get_event_loop()
    atexit.register(lambda: loop.close())

    device_db = DeviceDB(args.device_db)
    dataset_db = DatasetDB(args.dataset_db)
    dataset_db.start()
    atexit.register(lambda: loop.run_until_complete(dataset_db.stop()))

    if args.git:
        repo_backend = GitBackend(args.repository)
    else:
        repo_backend = FilesystemBackend(args.repository)
    repository = Repository(repo_backend, device_db.get_device_db,
                            log_worker)
    atexit.register(repository.close)
    repository.scan_async()

    worker_handlers = {
        "get_device_db": device_db.get_device_db,
        "get_device": device_db.get,
        "get_dataset": dataset_db.get,
        "update_dataset": dataset_db.update,
        "log": log_worker
    }
    scheduler = Scheduler(get_last_rid() + 1, worker_handlers, repo_backend)
    worker_handlers["scheduler_submit"] = scheduler.submit
    scheduler.start()
    atexit.register(lambda: loop.run_until_complete(scheduler.stop()))

    server_control = RPCServer({
        "master_device_db": device_db,
        "master_dataset_db": dataset_db,
        "master_schedule": scheduler,
        "master_repository": repository
    })
    loop.run_until_complete(server_control.start(
        args.bind, args.port_control))
    atexit.register(lambda: loop.run_until_complete(server_control.stop()))

    server_notify = Publisher({
        "schedule": scheduler.notifier,
        "devices": device_db.data,
        "datasets": dataset_db.data,
        "explist": repository.explist,
        "log": log_buffer.data
    })
    loop.run_until_complete(server_notify.start(
        args.bind, args.port_notify))
    atexit.register(lambda: loop.run_until_complete(server_notify.stop()))

    server_logging = LoggingServer()
    loop.run_until_complete(server_logging.start(
        args.bind, args.port_logging))
    atexit.register(lambda: loop.run_until_complete(server_logging.stop()))

    loop.run_forever()

if __name__ == "__main__":
    main()
