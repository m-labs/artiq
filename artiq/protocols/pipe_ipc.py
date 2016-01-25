import os
import asyncio


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

            pipe = open(self.p_rfd, "rb", 0)
            self.reader = asyncio.StreamReader(loop=loop)
            def factory():
                return asyncio.StreamReaderProtocol(self.reader, loop=loop)
            await loop.connect_read_pipe(factory, pipe)

            pipe = open(self.p_wfd, "wb", 0)
            transport, protocol = await loop.connect_write_pipe(
                asyncio.Protocol, pipe)
            self.writer = asyncio.StreamWriter(transport, protocol,
                                               None, loop)

    class AsyncioChildComm(_BaseIO):
        pass

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
            def factory():
                return asyncio.StreamReaderProtocol(self.reader)
            transport, protocol = await loop.create_pipe_connection(self.address,
                                                                    factory)
            self.writer = asyncio.StreamWriter(transport, protocol,
                                               self.reader, loop)

    class ChildComm:
        pass
