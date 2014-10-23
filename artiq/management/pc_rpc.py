import socket
import json
import asyncio


class RemoteError(Exception):
    pass


class Client:
    def __init__(self, host, port):
        self.socket = socket.create_connection((host, port))

    def close(self):
        self.socket.close()

    def do_rpc(self, name, args, kwargs):
        obj = {"action": "call", "name": name, "args": args, "kwargs": kwargs}
        line = json.dumps(obj) + "\n"
        self.socket.sendall(line.encode())

        buf = self.socket.recv(4096).decode()
        while "\n" not in buf:
            more = self.socket.recv(4096)
            if not more:
                break
            buf += more.decode()
        obj = json.loads(buf)
        if obj["result"] == "ok":
            return obj["ret"]
        elif obj["result"] == "error":
            raise RemoteError(obj["message"])
        else:
            raise ValueError

    def __getattr__(self, name):
        def proxy(*args, **kwargs):
            return self.do_rpc(name, args, kwargs)
        return proxy


class Server:
    def __init__(self, target):
        self.target = target
        self.client_tasks = set()

    @asyncio.coroutine
    def start(self, host, port):
        self.server = yield from asyncio.start_server(self.handle_connection,
                                                      host, port)

    @asyncio.coroutine
    def stop(self):
        for task in self.client_tasks:
            task.cancel()
        self.server.close()
        yield from self.server.wait_closed()
        del self.server

    def client_done(self, task):
        self.client_tasks.remove(task)

    def handle_connection(self, reader, writer):
        task = asyncio.Task(self.handle_connection_task(reader, writer))
        self.client_tasks.add(task)
        task.add_done_callback(self.client_done)

    @asyncio.coroutine
    def handle_connection_task(self, reader, writer):
        try:
            while True:
                line = yield from reader.readline()
                if not line:
                    break
                obj = json.loads(line.decode())
                action = obj["action"]
                if action == "call":
                    method = getattr(self.target, obj["name"])
                    try:
                        ret = method(*obj["args"], **obj["kwargs"])
                        obj = {"result": "ok", "ret": ret}
                    except Exception as e:
                        obj = {"result": "error",
                               "message": type(e).__name__ + ": " + str(e)}
                    line = json.dumps(obj) + "\n"
                    writer.write(line.encode())
        finally:
            writer.close()
