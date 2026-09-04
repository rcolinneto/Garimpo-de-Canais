import logging

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def configure_logging(level: int = logging.INFO) -> None:
    """Log INFO para execução normal e ERROR para falhas (docs/07).

    Necessário porque o uvicorn configura só os loggers dele: sem isso, os logs
    dos jobs de coleta seriam descartados no container.
    """
    logging.basicConfig(level=level, format=LOG_FORMAT, force=True)
