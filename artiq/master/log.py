import logging
import logging.handlers

from artiq.protocols.sync_struct import Notifier
from artiq.protocols.logging import parse_log_message, log_with_name, SourceFilter


class LogBuffer:
    def __init__(self, depth):
        self.depth = depth
        self.data = Notifier([])

    def log(self, level, source, time, message):
        if len(self.data.read) >= self.depth:
            del self.data[0]
        self.data.append((level, source, time, message))


class LogBufferHandler(logging.Handler):
    def __init__(self, log_buffer, *args, **kwargs):
        logging.Handler.__init__(self, *args, **kwargs)
        self.log_buffer = log_buffer
        self.setFormatter(logging.Formatter("%(name)s:%(message)s"))

    def emit(self, record):
        message = self.format(record)
        for part in message.split("\n"):
            self.log_buffer.log(record.levelno, record.source, record.created,
                                part)


def log_worker(rid, message):
    level, name, message = parse_log_message(message)
    log_with_name(name, level, message,
                  extra={"source": "worker({})".format(rid)})
log_worker.worker_pass_rid = True


def log_args(parser):
    group = parser.add_argument_group("logging")
    group.add_argument("-v", "--verbose", default=0, action="count",
                       help="increase logging level of the master process")
    group.add_argument("-q", "--quiet", default=0, action="count",
                       help="decrease logging level of the master process")
    group.add_argument("--log-file", default="",
                       help="store logs in rotated files; set the "
                            "base filename")
    group.add_argument("--log-max-size", type=int, default=1024,
                       help="maximum size of each log file in KiB "
                            "(default: %(default)d)")
    group.add_argument("--log-backup-count", type=int, default=6,
                       help="number of old log files to keep (.<n> is added "
                            "to the base filename (default: %(default)d)")


def init_log(args):
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.NOTSET)  # we use our custom filter only
    flt = SourceFilter(logging.WARNING + args.quiet*10 - args.verbose*10,
                       "master")
    full_fmt = logging.Formatter(
        "%(levelname)s:%(source)s:%(name)s:%(message)s")

    handlers = []
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(full_fmt)
    handlers.append(console_handler)

    if args.log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            args.log_file,
            maxBytes=args.log_max_size*1024,
            backupCount=args.log_backup_count)
        file_handler.setFormatter(full_fmt)
        handlers.append(file_handler)
    
    log_buffer = LogBuffer(1000)
    buffer_handler = LogBufferHandler(log_buffer)
    handlers.append(buffer_handler)

    for handler in handlers:
        handler.addFilter(flt)
        root_logger.addHandler(handler)

    return log_buffer
