"""Configuração de logging."""

import logging
import os
from logging.handlers import RotatingFileHandler

from config.settings import (
    LOG_BACKUP_COUNT,
    LOG_LEVEL,
    LOG_MAX_BYTES,
    LOG_PATH,
    LOGS_DIR,
)


def configure_logging() -> None:
    """Grava o detalhe em arquivo e mantém o console limpo."""
    os.makedirs(LOGS_DIR, exist_ok=True)
    level = getattr(logging, LOG_LEVEL, logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)-24s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler = RotatingFileHandler(
        LOG_PATH,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    # O console recebe só mensagens simples dos scripts.
    # Detalhes de conexão, SSL e tentativas permanecem somente no arquivo de log.
    console_handler.setLevel(logging.CRITICAL)
    console_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    root.addHandler(file_handler)
    root.addHandler(console_handler)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
