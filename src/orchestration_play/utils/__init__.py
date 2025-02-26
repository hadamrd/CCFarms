import logging
from prefect import get_run_logger

class FlowLogger:
    """Dual-purpose logger that works in and out of Prefect flows"""
    def __init__(self, name: str):
        self.name = name
        self._fallback_logger = logging.getLogger(name)

    def __getattr__(self, name):
        # Try Prefect context first
        try:
            prefect_logger = get_run_logger()
            return getattr(prefect_logger, name)
        except RuntimeError:
            return getattr(self._fallback_logger, name)

def get_flow_aware_logger(name: str = __name__):
    return FlowLogger(name)
