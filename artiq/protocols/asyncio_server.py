import asyncio
from copy import copy


class AsyncioServer:
    """Generic TCP server based on asyncio.

    Users of this class must derive from it and define the
    :meth:`~artiq.protocols.asyncio_server.AsyncioServer._handle_connection_cr`
    method/coroutine.
    """
    def __init__(self):
        self._client_tasks = set()

    async def start(self, host, port):
        """Starts the server.

        The user must call :meth:`stop`
        to free resources properly after this method completes successfully.

        This method is a *coroutine*.

        :param host: Bind address of the server (see ``asyncio.start_server``
            from the Python standard library).
        :param port: TCP port to bind to.
        """
        self.server = await asyncio.start_server(self._handle_connection,
                                                 host, port,
                                                 limit=4*1024*1024)

    async def stop(self):
        """Stops the server."""
        wait_for = copy(self._client_tasks)
        for task in self._client_tasks:
            task.cancel()
        for task in wait_for:
            try:
                await asyncio.wait_for(task, None)
            except asyncio.CancelledError:
                pass
        self.server.close()
        await self.server.wait_closed()
        del self.server

    def _client_done(self, task):
        self._client_tasks.remove(task)

    def _handle_connection(self, reader, writer):
        task = asyncio.ensure_future(self._handle_connection_cr(reader, writer))
        self._client_tasks.add(task)
        task.add_done_callback(self._client_done)

    async def _handle_connection_cr(self, reader, writer):
        raise NotImplementedError
