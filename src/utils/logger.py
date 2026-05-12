"""日志配置"""
import logging
import sys


def setup_logger(name: str = "code-review-agent") -> logging.Logger:
    """创建并配置 logger"""
    _logger = logging.getLogger(name)
    _logger.setLevel(logging.INFO)

    if not _logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%H:%M:%S",
        )
        handler.setFormatter(formatter)
        _logger.addHandler(handler)

    return _logger


logger = setup_logger()