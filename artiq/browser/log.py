import logging

from artiq.protocols.logging import SourceFilter


class LogWidgetHandler(logging.Handler):
    def __init__(self, *args, **kwargs):
        logging.Handler.__init__(self, *args, **kwargs)
        self.log_widget = None
        self.setFormatter(logging.Formatter("%(name)s:%(message)s"))

    def emit(self, record):
        if self.log_widget is not None:
            message = self.format(record)
            self.log_widget.append_message((record.levelno, record.source,
                                            record.created, message))


def init_log(args):
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.NOTSET)  # we use our custom filter only
    flt = SourceFilter(logging.WARNING + args.quiet*10 - args.verbose*10,
                       "browser")
    handlers = []
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(
        "%(levelname)s:%(source)s:%(name)s:%(message)s"))
    handlers.append(console_handler)

    widget_handler = LogWidgetHandler()
    handlers.append(widget_handler)

    for handler in handlers:
        handler.addFilter(flt)
        root_logger.addHandler(handler)

    return widget_handler
