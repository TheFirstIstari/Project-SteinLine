from datetime import datetime
from pathlib import Path

class CoordinateEngine:
    """Calculates deterministic X/Y positions for the forensic board.

    Uses a datetime-based anchor (1945-01-01) and computes X as weeks since
    the anchor and Y as category lane + stacking offset.
    """

    X_SCALE = 1200  # Pixels per ordinal week
    Y_LANE_HEIGHT = 1500  # Pixels between categories
    FACT_OFFSET = 300  # Vertical gap between facts in the same week

    def __init__(self, config):
        self.config = config
        self.anchor = datetime(1945, 1, 1)

    def _parse_date(self, date_str: str):
        clean = str(date_str).replace("-XX", "-01").strip()
        # Try ISO first, then a few common formats
        fmts = ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S")
        for fmt in fmts:
            try:
                return datetime.strptime(clean, fmt)
            except Exception:
                continue
        try:
            # Fallback to fromisoformat for other ISO variants
            return datetime.fromisoformat(clean)
        except Exception:
            return None

    def get_pos(self, date_str, category_index, stack_index):
        """Returns a (float, float) tuple representing board coordinates."""
        try:
            m_date = self._parse_date(date_str)
            if m_date is None:
                raise ValueError("invalid date")

            days_diff = float((m_date - self.anchor).days)

            # Calculate X (Time axis) in weeks
            x = (days_diff / 7.0) * self.X_SCALE

            # Calculate Y (Category stack)
            y = (float(category_index) * self.Y_LANE_HEIGHT) + (float(stack_index) * self.FACT_OFFSET)

            return float(x), float(y)
        except Exception:
            # Fallback to origin to prevent C++ crash
            return 0.0, 0.0