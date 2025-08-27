from loguru import logger
import sys
from .config import get_settings

def setup_logging():
    logger.remove()
    settings = get_settings()
    logger.add(
        sys.stdout,
        level=settings.log_level.upper(),
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
               "<level>{level: <8}</level> | "
               "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
               "<level>{message}</level>",
        enqueue=True,
        backtrace=True,
        diagnose=False,
    )
    logger.debug("Logger initialized with level {}", settings.log_level)
    return logger
