#!/usr/bin/env python3

import asyncio
import argparse
import atexit
import os
import logging

from sipyco.pc_rpc import Server as RPCServer
from sipyco.sync_struct import Publisher
from sipyco.logging_tools import Server as LoggingServer
from sipyco.broadcast import Broadcaster
from sipyco import common_args
from sipyco.asyncio_tools import atexit_register_coroutine

from artiq import __version__ as artiq_version
from artiq.master.log import log_args, init_log
from artiq.master.databases import DeviceDB, DatasetDB
from artiq.master.scheduler import Scheduler
from artiq.master.rid_counter import RIDCounter
from artiq.master.experiments import (FilesystemBackend, GitBackend,
                                      ExperimentDB)

logger = logging.getLogger(__name__)


def get_argparser():
    parser = argparse.ArgumentParser(description="ARTIQ master")
    parser.add_argument("--version", action="version",
                        version="ARTIQ v{}".format(artiq_version),
                        help="print the ARTIQ version number")

    common_args.simple_network_args(parser, [
        ("notify", "notifications", 3250),
        ("control", "control", 3251),
        ("logging", "remote logging", 1066),
        ("broadcast", "broadcasts", 1067)
    ])

    group = parser.add_argument_group("databases")
    group.add_argument("--device-db", default="device_db.py",
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

    parser.add_argument("--name",
        help="friendly name, displayed in dashboards "
             "to identify master instead of server address")

    return parser


class MasterConfig:
    def __init__(self, name):
        self.name = name

    def get_name(self):
        return self.name


def main():
    args = get_argparser().parse_args()
    log_forwarder = init_log(args)
    if os.name == "nt":
        loop = asyncio.ProactorEventLoop()
        asyncio.set_event_loop(loop)
    else:
        loop = asyncio.get_event_loop()
    atexit.register(loop.close)
    bind = common_args.bind_address_from_args(args)

    server_broadcast = Broadcaster()
    loop.run_until_complete(server_broadcast.start(
        bind, args.port_broadcast))
    atexit_register_coroutine(server_broadcast.stop)

    log_forwarder.callback = (lambda msg:
        server_broadcast.broadcast("log", msg))
    def ccb_issue(service, *args, **kwargs):
        msg = {
            "service": service,
            "args": args,
            "kwargs": kwargs
        }
        server_broadcast.broadcast("ccb", msg)

    device_db = DeviceDB(args.device_db)
    dataset_db = DatasetDB(args.dataset_db)
    dataset_db.start()
    atexit_register_coroutine(dataset_db.stop)
    worker_handlers = dict()

    if args.git:
        repo_backend = GitBackend(args.repository)
    else:
        repo_backend = FilesystemBackend(args.repository)
    experiment_db = ExperimentDB(repo_backend, worker_handlers)
    atexit.register(experiment_db.close)

    scheduler = Scheduler(RIDCounter(), worker_handlers, experiment_db)
    scheduler.start()
    atexit_register_coroutine(scheduler.stop)

    config = MasterConfig(args.name)

    worker_handlers.update({
        "get_device_db": device_db.get_device_db,
        "get_device": device_db.get,
        "get_dataset": dataset_db.get,
        "update_dataset": dataset_db.update,
        "scheduler_submit": scheduler.submit,
        "scheduler_delete": scheduler.delete,
        "scheduler_request_termination": scheduler.request_termination,
        "scheduler_get_status": scheduler.get_status,
        "scheduler_check_pause": scheduler.check_pause,
        "ccb_issue": ccb_issue,
    })
    experiment_db.scan_repository_async()

    server_control = RPCServer({
        "master_config": config,
        "master_device_db": device_db,
        "master_dataset_db": dataset_db,
        "master_schedule": scheduler,
        "master_experiment_db": experiment_db
    }, allow_parallel=True)
    loop.run_until_complete(server_control.start(
        bind, args.port_control))
    atexit_register_coroutine(server_control.stop)

    server_notify = Publisher({
        "schedule": scheduler.notifier,
        "devices": device_db.data,
        "datasets": dataset_db.data,
        "explist": experiment_db.explist,
        "explist_status": experiment_db.status
    })
    loop.run_until_complete(server_notify.start(
        bind, args.port_notify))
    atexit_register_coroutine(server_notify.stop)

    server_logging = LoggingServer()
    loop.run_until_complete(server_logging.start(
        bind, args.port_logging))
    atexit_register_coroutine(server_logging.stop)

    print("ARTIQ master is now ready.")
    loop.run_forever()

if __name__ == "__main__":
    main()
