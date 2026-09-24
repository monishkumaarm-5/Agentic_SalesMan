import logging


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, str(level).upper(), logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )
    # Third-party libraries are chatty at INFO.
    for noisy in ("httpx", "chromadb", "sentence_transformers", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
