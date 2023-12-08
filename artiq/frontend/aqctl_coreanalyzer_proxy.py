import argparse
import asyncio
import atexit
import logging

from sipyco.asyncio_tools import AsyncioServer, SignalHandler, atexit_register_coroutine
from sipyco.pc_rpc import Server
from sipyco import common_args

from artiq.coredevice.comm_analyzer import get_analyzer_dump


logger = logging.getLogger(__name__)


# simplified version of sipyco Broadcaster
class ProxyServer(AsyncioServer):
    def __init__(self, queue_limit=1024):
        AsyncioServer.__init__(self)
        self._recipients = set()
        self._queue_limit = queue_limit

    async def _handle_connection_cr(self, reader, writer):
        try:
            queue = asyncio.Queue(self._queue_limit)
            self._recipients.add(queue)
            try:
                while True:
                    dump = await queue.get()
                    writer.write(dump)
                    # raise exception on connection error
                    await writer.drain()
            finally:
                self._recipients.remove(queue)
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            # receivers disconnecting are a normal occurence
            pass
        finally:
            writer.close()

    def request_dump_cb(self, dump):
        for recipient in self._recipients:
            recipient.put_nowait(dump)


class ProxyControl:
    def __init__(self, request_dump_cb, core_addr, core_port=1382):
        self.request_dump_cb = request_dump_cb
        self.core_addr = core_addr
        self.core_port = core_port

    def ping(self):
        return True

    def request_dump(self):
        try:
            dump = get_analyzer_dump(self.core_addr, self.core_port)
            self.request_dump_cb(dump)
        except:
            logger.warning("Failed to get analyzer dump:", exc_info=1)
            return False
        else:
            return True


def get_argparser():
    parser = argparse.ArgumentParser(
        description="ARTIQ core analyzer proxy")
    common_args.verbosity_args(parser)
    common_args.simple_network_args(parser, [
        ("proxy", "proxying", 1385),
        ("control", "control", 1386)
    ])
    parser.add_argument("core_addr", metavar="CORE_ADDR",
                        help="hostname or IP address of the core device")
    return parser


def main():
    args = get_argparser().parse_args()
    common_args.init_logger_from_args(args)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    atexit.register(loop.close)

    signal_handler = SignalHandler()
    signal_handler.setup()
    atexit.register(signal_handler.teardown)

    bind_address = common_args.bind_address_from_args(args)

    proxy_server = ProxyServer()
    loop.run_until_complete(proxy_server.start(bind_address, args.port_proxy))
    atexit_register_coroutine(proxy_server.stop, loop=loop)

    controller = ProxyControl(proxy_server.request_dump_cb, args.core_addr)
    server = Server({"coreanalyzer_proxy_control": controller}, None, True)
    loop.run_until_complete(server.start(bind_address, args.port_control))
    atexit_register_coroutine(server.stop, loop=loop)

    _, pending = loop.run_until_complete(asyncio.wait(
        [loop.create_task(signal_handler.wait_terminate()),
         loop.create_task(server.wait_terminate())],
        return_when=asyncio.FIRST_COMPLETED))
    for task in pending:
        task.cancel()


if __name__ == "__main__":
    main()
