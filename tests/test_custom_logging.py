"""test module."""
from itertools import product
from unittest import mock

import pytest


@pytest.mark.parametrize(
    'dev, debug',
    product([False, True], repeat=2)
)
def test_init_logging(dev, debug):
    """test func."""
    log_path = mock.Mock()
    debug_log_path = mock.Mock()
    with mock.patch('version.custom_logging.logging') as m_logging, \
            mock.patch('version.custom_logging.create_log_file') as m_create_lf, \
            mock.patch('version.custom_logging.os'), \
            mock.patch('version.custom_logging.app_constants') as m_ac:
        from version.custom_logging import init_logging
        # run
        init_logging(log_path, debug_log_path, dev=dev, debug=debug)
        # test
        handlers = []
        log_level = m_logging.INFO
        m_logging_calls = []
        if dev:
            m_logging_calls.append(mock.call.StreamHandler())
            handlers.append(m_logging.StreamHandler.return_value)
        if debug:
            m_create_lf.assert_called_once_with(debug_log_path)

            m_logging_calls.append(mock.call.FileHandler(debug_log_path, 'w', 'utf-8'))
            handlers.append(mock.call.FileHandler.return_value)
            log_level = m_logging.DEBUG
            assert m_ac.DEBUG
        else:
            m_logging_calls.append(mock.call.handlers.RotatingFileHandler(
                log_path, backupCount=2, encoding='utf-8', maxBytes=10000000))
            handlers.append(m_logging.handlers.RotatingFileHandler.return_value)
            m_create_lf.assert_called_once_with(log_path)

        m_logging_calls.append(
            mock.call.basicConfig(
                datefmt='%d-%m %H:%M',
                format='%(asctime)-8s %(levelname)-6s %(name)-6s %(message)s',
                handlers=tuple(handlers),
                level=log_level)
        )
        m_logging.assert_has_calls(m_logging_calls)
        # app_constants tested after m_logging calls


def test_create_log_file():
    """test func."""
    m_open = mock.mock_open()
    path = mock.Mock()
    with mock.patch('version.custom_logging.open', m_open, create=True):
        from version.custom_logging import create_log_file
        # run
        create_log_file(path=path)
        # test
        m_open.assert_has_calls([
            mock.call(path, 'x'),
            mock.call().__enter__(),
            mock.call().__exit__(None, None, None)
        ])
