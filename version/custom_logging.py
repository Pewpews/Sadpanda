"""module for logging."""
import os
import logging

try:
    import app_constants
except ImportError:
    from . import app_constants


def create_log_file(path):
    """create log file.

    Args:
        path: Path of the log file.
    """
    try:
        with open(path, 'x'):
            pass
    except FileExistsError:  # NOQA
        pass


def init_logging(log_path, debug_log_path, dev=None, debug=None):
    """init logging.

    Args:
        log_path: Path for log file for normal logging.
        debug_log_path: Path for log file for debug logging.
        dev (bool): Set logging for dev mode.
        debug (bool: Set logging for debug mode.)
    """
    log_handlers = []
    log_level = logging.INFO
    if dev:
        log_handlers.append(logging.StreamHandler())
    if debug:
        print("happypanda_debug.log created at {}".format(os.path.dirname(debug_log_path)))
        # create log
        create_log_file(debug_log_path)

        log_handlers.append(logging.FileHandler(debug_log_path, 'w', 'utf-8'))
        log_level = logging.DEBUG
        app_constants.DEBUG = True
    else:
        create_log_file(log_path)

        log_handlers.append(logging.handlers.RotatingFileHandler(
            log_path, maxBytes=1000000*10, encoding='utf-8', backupCount=2))

    logging.basicConfig(
        level=log_level,
        format='%(asctime)-8s %(levelname)-6s %(name)-6s %(message)s',
        datefmt='%d-%m %H:%M',
        handlers=tuple(log_handlers)
    )
