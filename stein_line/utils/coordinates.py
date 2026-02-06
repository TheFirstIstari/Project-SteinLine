import moment
from pathlib import Path

class CoordinateEngine:
    """Calculates deterministic X/Y positions for the forensic board."""
    
    X_SCALE = 1000 # Pixels per ordinal week
    Y_LANE_HEIGHT = 1500 # Pixels between categories
    FACT_OFFSET = 300 # Vertical gap between facts in the same week

    def __init__(self, config):
        self.config = config
        self.anchor = moment.date("1945-01-01") # Global starting point

    def get_pos(self, date_str, category_index, stack_index):
        """Converts forensic metadata into a QPointF-compatible tuple."""
        try:
            # Handle the "XX" dates from our deconstructor
            clean_date = date_str.replace("-XX", "-01")
            m_date = moment.date(clean_date)
            
            # X = Chronological displacement
            # Note: For compressed view, we use the week-index, 
            # but for this logic we use total days for stability.
            days = m_date.diff(self.anchor, "days")
            x = (days / 7) * self.X_SCALE 
            
            # Y = Category Lane + Stack displacement
            y = (category_index * self.Y_LANE_HEIGHT) + (stack_index * self.FACT_OFFSET)
            
            return x, y
        except:
            return 0, 0