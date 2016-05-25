import logging

from artiq.protocols.logging import SourceFilter


class LogBufferHandler(logging.Handler):
    def __init__(self, log, *args, **kwargs):
        logging.Handler.__init__(self, *args, **kwargs)
        self.log = log
        self.setFormatter(logging.Formatter("%(name)s:%(message)s"))

    def emit(self, record):
        if self.log.model is not None:
            self.log.model.append((record.levelno, record.source,
                                   record.created, self.format(record)))


def init_log(args, log):
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.NOTSET)  # we use our custom filter only
    flt = SourceFilter(logging.WARNING + args.quiet*10 - args.verbose*10,
                       "browser")
    handlers = []
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(
        "%(levelname)s:%(source)s:%(name)s:%(message)s"))
    handlers.append(console_handler)

    buffer_handler = LogBufferHandler(log)
    handlers.append(buffer_handler)

    for handler in handlers:
        handler.addFilter(flt)
        root_logger.addHandler(handler)
