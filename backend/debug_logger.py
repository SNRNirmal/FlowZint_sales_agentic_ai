import logging
from typing import Optional, List, Any

logger = logging.getLogger("threshold.debug")

class dl:
    @staticmethod
    def log_step(
        step_id: float,
        message: str,
        node: Optional[str] = None,
        output_keys: Optional[List[str]] = None,
        **kwargs
    ) -> None:
        """Log a step in the pipeline execution."""
        node_str = f"[{node}] " if node else ""
        keys_str = f" (outputs: {output_keys})" if output_keys else ""
        kwargs_str = f" | {kwargs}" if kwargs else ""
        logger.info(f"{node_str}Step {step_id}: {message}{keys_str}{kwargs_str}")
