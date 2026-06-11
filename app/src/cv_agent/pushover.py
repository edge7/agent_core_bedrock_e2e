import logging

import httpx

from cv_agent.settings import settings

PUSHOVER_API = "https://api.pushover.net/1/messages.json"

logger = logging.getLogger(__name__)


def send_pushover(message: str, title: str = "CV Agent — recruiter lead") -> bool:
    """Send a Pushover notification. Returns False (without raising) if not configured or failed."""
    user_key, api_token = settings.resolve_pushover()
    if not user_key or not api_token:
        logger.warning("pushover: credentials not resolved, skipping notification")
        return False
    try:
        resp = httpx.post(
            PUSHOVER_API,
            data={
                "token": api_token,
                "user": user_key,
                "title": title,
                "message": message[:1024],
            },
            timeout=10,
        )
        if resp.status_code != 200:
            logger.error("pushover: HTTP %s — %s", resp.status_code, resp.text[:300])
            return False
        logger.info("pushover: notification sent")
        return True
    except httpx.HTTPError as exc:
        logger.error("pushover: request failed — %r", exc)
        return False
