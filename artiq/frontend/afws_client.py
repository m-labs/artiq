#!/usr/bin/env python3

import sys
import argparse
import os
import socket
import ssl
import io
import zipfile
from getpass import getpass


def get_artiq_cert():
    try:
        import artiq
    except ImportError:
        return None
    filename = os.path.join(os.path.dirname(artiq.__file__), "afws.pem")
    if not os.path.isfile(filename):
        return None
    return filename


def get_artiq_rev():
    try:
        import artiq
    except ImportError:
        return None
    return artiq._version.get_rev()


def zip_unarchive(data, directory):
    buf = io.BytesIO(data)
    with zipfile.ZipFile(buf) as archive:
        archive.extractall(directory)


class Client:
    def __init__(self, server, port, cafile):
        self.ssl_context = ssl.create_default_context(cafile=cafile)
        self.raw_socket = socket.create_connection((server, port))
        try:
            self.socket = self.ssl_context.wrap_socket(self.raw_socket, server_hostname=server)
        except:
            self.raw_socket.close()
            raise
        self.fsocket = self.socket.makefile("rwb")

    def close(self):
        self.socket.close()
        self.raw_socket.close()

    def send_command(self, *command):
        self.fsocket.write((" ".join(command) + "\n").encode())
        self.fsocket.flush()

    def read_reply(self):
        return self.fsocket.readline().decode("ascii").split()

    def login(self, username, password):
        self.send_command("LOGIN", username, password)
        return self.read_reply() == ["HELLO"]

    def build(self, rev, variant):
        self.send_command("BUILD", rev, variant)
        reply = self.read_reply()[0]
        if reply != "BUILDING":
            return reply, None
        print("Build in progress. This may take 10-15 minutes.")
        reply, status = self.read_reply()
        if reply != "DONE":
            raise ValueError("Unexpected server reply: expected 'DONE', got '{}'".format(reply))
        if status != "done":
            return status, None
        print("Build completed. Downloading...")
        reply, length = self.read_reply()
        if reply != "PRODUCT":
            raise ValueError("Unexpected server reply: expected 'PRODUCT', got '{}'".format(reply))
        contents = self.fsocket.read(int(length))
        print("Download completed.")
        return "OK", contents

    def passwd(self, password):
        self.send_command("PASSWD", password)
        return self.read_reply() == ["OK"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", default="nixbld.m-labs.hk", help="server to connect to (default: %(default)s)")
    parser.add_argument("--port", default=7402, type=int, help="port to connect to (default: %(default)d)")
    parser.add_argument("--cert", default=None, help="SSL certificate file used to authenticate server (default: afws.pem in ARTIQ)")
    parser.add_argument("username", help="user name for logging into AFWS")
    action = parser.add_subparsers(dest="action")
    action.required = True
    act_build = action.add_parser("build", help="build and download firmware")
    act_build.add_argument("--rev", default=None, help="revision to build (default: currently installed ARTIQ revision)")
    act_build.add_argument("variant", help="variant to build")
    act_build.add_argument("directory", help="output directory")
    act_passwd = action.add_parser("passwd", help="change password")
    args = parser.parse_args()

    cert = args.cert
    if cert is None:
        cert = get_artiq_cert()
    if cert is None:
        print("SSL certificate not found in ARTIQ. Specify manually using --cert.")
        sys.exit(1)

    if args.action == "passwd":
        password = getpass("Current password: ")
    else:
        password = getpass()

    client = Client(args.server, args.port, cert)
    try:
        if not client.login(args.username, password):
            print("Login failed")
            sys.exit(1)
        print("Logged in successfully.")
        if args.action == "passwd":
            print("Password must made of alphanumeric characters (a-z, A-Z, 0-9) and be at least 8 characters long.")
            password = getpass("New password: ")
            password_confirm = getpass("New password (again): ")
            while password != password_confirm:
                print("Passwords do not match")
                password = getpass("New password: ")
                password_confirm = getpass("New password (again): ")
            if not client.passwd(password):
                print("Failed to change password")
                sys.exit(1)
        elif args.action == "build":
            try:
                os.mkdir(args.directory)
            except FileExistsError:
                try:
                    if any(os.scandir(args.directory)):
                        print("Output directory already exists and is not empty. Please remove it and try again.")
                        sys.exit(1)
                except NotADirectoryError:
                    print("A file with the same name as the output directory already exists. Please remove it and try again.")
                    sys.exit(1)
            rev = args.rev
            if rev is None:
                rev = get_artiq_rev()
            if rev is None:
                print("Unable to determine currently installed ARTIQ revision. Specify manually using --rev.")
                sys.exit(1)
            result, contents = client.build(rev, args.variant)
            if result != "OK":
                if result == "UNAUTHORIZED":
                    print("You are not authorized to build this variant. Your firmware subscription may have expired. Contact helpdesk\x40m-labs.hk.")
                else:
                    print("Build failed: {}".format(result))
                sys.exit(1)
            zip_unarchive(contents, args.directory)
        else:
            raise ValueError
    finally:
        client.close()


if __name__ == "__main__":
    main()
