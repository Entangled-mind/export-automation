"""Daily send limit and throttling rate limiter for Phase 4 outreach.

Prevents exceeding mailbox daily sending quotas and tracks dispatch rates against
data/sent_log.csv.
"""

from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

import config
from logging_module.activity_logger import init_sent_log, read_sent_history


def get_today_sent_count(sent_log_path: Optional[Path] = None) -> int:
    """Calculate the number of emails sent today from sent_log.csv.

    Counts both real 'SUCCESS' dispatches and 'SIMULATED_SUCCESS' dry-runs.

    Args:
        sent_log_path: Optional custom path for sent_log.csv.

    Returns:
        Integer count of successful/simulated dispatches for the current calendar date.
    """
    path = init_sent_log(sent_log_path)
    if not path.exists():
        return 0

    today_str = datetime.now().strftime("%Y-%m-%d")
    history = read_sent_history(path)

    today_count = 0
    for entry in history:
        timestamp = entry.get("timestamp", "")
        status = entry.get("status", "")
        if timestamp.startswith(today_str) and status in ("SUCCESS", "SIMULATED_SUCCESS"):
            today_count += 1

    return today_count


def can_send_today(
    limit: Optional[int] = None, sent_log_path: Optional[Path] = None
) -> Tuple[bool, int, int]:
    """Check if the system has capacity to dispatch an email today.

    Args:
        limit: Optional daily send limit override. Defaults to config.DAILY_SEND_LIMIT.
        sent_log_path: Optional custom path for sent_log.csv.

    Returns:
        Tuple of (can_send: bool, current_sent: int, max_limit: int).
    """
    max_limit = limit if limit is not None else config.DAILY_SEND_LIMIT
    current_count = get_today_sent_count(sent_log_path)
    can_send = current_count < max_limit
    return can_send, current_count, max_limit
