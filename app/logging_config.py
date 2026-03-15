"""Uvicorn logging configuration with timestamps."""

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s - %(levelname)s - %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "access": {
            "()": "uvicorn.logging.AccessFormatter",
            "fmt": (
                "%(asctime)s - %(levelname)s - %(client_addr)s"
                ' - "%(request_line)s" %(status_code)s'
            ),
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "default": {
            "formatter": "default",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
        },
        "access": {
            "formatter": "access",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
        },
    },
    "loggers": {
        "uvicorn": {
            "handlers": ["default"],
            "level": "INFO",
            "propagate": False,
        },
        "uvicorn.error": {
            "handlers": ["default"],
            "level": "INFO",
            "propagate": False,
        },
        "uvicorn.access": {
            "handlers": ["access"],
            "level": "INFO",
            "propagate": False,
        },
        "azure": {
            "handlers": ["default"],
            "level": "WARNING",
            "propagate": False,
        },
        "azure.identity": {
            "handlers": ["default"],
            "level": "WARNING",
            "propagate": False,
        },
        "azure.core.pipeline": {
            "handlers": ["default"],
            "level": "WARNING",
            "propagate": False,
        },
        "": {  # Root logger
            "handlers": ["default"],
            "level": "INFO",
        },
    },
}
