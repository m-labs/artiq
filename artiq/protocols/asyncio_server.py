import asyncio
from copy import copy


class AsyncioServer:
    """Generic TCP server based on asyncio.

    Users of this class must derive from it and define the
    ``_handle_connection_cr`` method and coroutine.

    """
    def __init__(self):
        self._client_tasks = set()

    @asyncio.coroutine
    def start(self, host, port):
        """Starts the server.

        The user must call ``stop`` to free resources properly after this
        method completes successfully.

        This method is a `coroutine`.

        :param host: Bind address of the server (see ``asyncio.start_server``
            from the Python standard library).
        :param port: TCP port to bind to.

        """
        self.server = yield from asyncio.start_server(self._handle_connection,
                                                      host, port)

    @asyncio.coroutine
    def stop(self):
        """Stops the server.

        """
        wait_for = copy(self._client_tasks)
        for task in self._client_tasks:
            task.cancel()
        for task in wait_for:
            try:
                yield from asyncio.wait_for(task, None)
            except asyncio.CancelledError:
                pass
        self.server.close()
        yield from self.server.wait_closed()
        del self.server

    def _client_done(self, task):
        self._client_tasks.remove(task)

    def _handle_connection(self, reader, writer):
        task = asyncio.Task(self._handle_connection_cr(reader, writer))
        self._client_tasks.add(task)
        task.add_done_callback(self._client_done)
