import logging
import logging.handlers

from sipyco.logging_tools import SourceFilter


class LogForwarder(logging.Handler):
    def __init__(self, *args, **kwargs):
        logging.Handler.__init__(self, *args, **kwargs)
        self.callback = None
        self.setFormatter(logging.Formatter("%(name)s:%(message)s"))

    def emit(self, record):
        if self.callback is not None:
            message = self.format(record)
            self.callback((record.levelno, record.source, record.created,
                           message))


def log_args(parser):
    group = parser.add_argument_group("logging")
    group.add_argument("-v", "--verbose", default=0, action="count",
                       help="increase logging level of the master process")
    group.add_argument("-q", "--quiet", default=0, action="count",
                       help="decrease logging level of the master process")
    group.add_argument("--log-file", default="",
                       help="store logs in rotated files; set the "
                            "base filename")
    group.add_argument("--log-backup-count", type=int, default=0,
                       help="number of old log files to keep, or 0 to keep "
                            "all log files. '.<yyyy>-<mm>-<dd>' is added "
                            "to the base filename (default: %(default)d)")


def init_log(args):
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.NOTSET)  # we use our custom filter only
    flt = SourceFilter(logging.WARNING + args.quiet*10 - args.verbose*10,
                       "master")
    handlers = []
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(
        "%(levelname)s:%(source)s:%(name)s:%(message)s"))
    handlers.append(console_handler)

    if args.log_file:
        file_handler = logging.handlers.TimedRotatingFileHandler(
            args.log_file,
            when="midnight",
            backupCount=args.log_backup_count)
        file_handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s:%(source)s:%(name)s:%(message)s"))
        handlers.append(file_handler)
    
    log_forwarder = LogForwarder()
    handlers.append(log_forwarder)

    for handler in handlers:
        handler.addFilter(flt)
        root_logger.addHandler(handler)

    return log_forwarder
