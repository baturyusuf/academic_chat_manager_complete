"""Rate limiting for operating-system notifications, independent of Qt."""
from collections.abc import Callable


class DesktopNotificationThrottle:
    """Batch notifications within five seconds and let priorities interrupt."""

    def __init__(self, clock: Callable[[], float]):
        self._clock = clock
        self._last_desktop_at = float("-inf")
        self._last_priority_at = float("-inf")
        self._suppressed = {False: 0, True: 0}

    def record(self, *, priority: bool) -> int | None:
        """Return the number batched with this alert, or None while throttled."""
        now = self._clock()
        last = self._last_priority_at if priority else self._last_desktop_at
        if now - last < 5:
            self._suppressed[priority] += 1
            return None
        if priority:
            self._last_priority_at = now
        self._last_desktop_at = now
        suppressed = self._suppressed[priority]
        self._suppressed[priority] = 0
        return suppressed
