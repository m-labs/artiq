import os
import asyncio
from asyncio.streams import FlowControlMixin


class _BaseIO:
    def write(self, data):
        self.writer.write(data)

    async def drain(self):
        await self.writer.drain()

    async def readline(self):
        return await self.reader.readline()

    async def read(self, n):
        return await self.reader.read(n)

    def close(self):
        self.writer.close()


if os.name != "nt":
    async def _fds_to_asyncio(rfd, wfd, loop):
        reader = asyncio.StreamReader(loop=loop)
        reader_protocol = asyncio.StreamReaderProtocol(reader, loop=loop)

        wf = open(wfd, "wb", 0)
        transport, protocol = await loop.connect_write_pipe(
            FlowControlMixin, wf)
        writer = asyncio.StreamWriter(transport, protocol,
                                      None, loop)

        rf = open(rfd, "rb", 0)
        await loop.connect_read_pipe(lambda: reader_protocol, rf)

        return reader, writer


    class AsyncioParentComm(_BaseIO):
        def __init__(self):
            self.c_rfd, self.p_wfd = os.pipe()
            self.p_rfd, self.c_wfd = os.pipe()

        def get_address(self):
            return "{},{}".format(self.c_rfd, self.c_wfd)

        async def create_subprocess(self, *args, **kwargs):
            loop = asyncio.get_event_loop()
            self.process = await asyncio.create_subprocess_exec(
                *args, pass_fds={self.c_rfd, self.c_wfd}, **kwargs)
            os.close(self.c_rfd)
            os.close(self.c_wfd)

            self.reader, self.writer = await _fds_to_asyncio(
                self.p_rfd, self.p_wfd, loop)


    class AsyncioChildComm(_BaseIO):
        def __init__(self, address):
            self.address = address

        async def connect(self):
            rfd, wfd = self.address.split(",", maxsplit=1)
            self.reader, self.writer = await _fds_to_asyncio(
                int(rfd), int(wfd), asyncio.get_event_loop())


    class ChildComm:
        def __init__(self, address):
            rfd, wfd = address.split(",", maxsplit=1)
            self.rf = open(int(rfd), "rb", 0)
            self.wf = open(int(wfd), "wb", 0)

        def read(self, n):
            return self.rf.read(n)

        def readline(self):
            return self.rf.readline()

        def write(self, data):
            return self.wf.write(data)

        def close(self):
            self.rf.close()
            self.wf.close()


else:  # windows
    class AsyncioParentComm(_BaseIO):
        pass

    class AsyncioChildComm(_BaseIO):
        """Requires ProactorEventLoop"""
        def __init__(self, address):
            self.address = address

        async def connect(self):
            loop = asyncio.get_event_loop()
            self.reader = asyncio.StreamReader(loop=loop)
            reader_protocol = asyncio.StreamReaderProtocol(
                self.reader, loop=loop)
            transport, protocol = await loop.create_pipe_connection(
                self.address, lambda: reader_protocol)
            self.writer = asyncio.StreamWriter(transport, protocol,
                                               self.reader, loop)

    class ChildComm:
        pass
