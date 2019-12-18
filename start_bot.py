"""Start Bot"""
import logging

from butler_G.core import start_bot
from butler_G.constants import DEV_MODE


if __name__ == "__main__":
    logger = logging.getLogger()
    shndlr, *_ = logger.handlers
    shndlr.setLevel(logging.INFO)
    shndlr.setFormatter(
        logging.Formatter(
            "[{}] %(asctime)s - %(levelname)s : %(message)s".format(
                "DEV" if DEV_MODE else "PRD"
            )
        )
    )

    start_bot()
