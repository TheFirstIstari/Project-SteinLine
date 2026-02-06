import re
from PySide6.QtWidgets import QGraphicsObject
from PySide6.QtCore import Qt, QRectF, Signal
from PySide6.QtGui import QColor, QPen, QBrush, QFont

class FactNode(QGraphicsObject):
    # Signal emitted when user clicks a fact to find related documents
    clicked_signal = Signal(str) # Passes the fingerprint

    def __init__(self, data):
        super().__init__()
        self.data = data 
        
        try:
            raw_sev = str(self.data.get('severity', 1))
            match = re.search(r'\d+', raw_sev)
            self.severity = int(match.group()) if match else 1
        except Exception:
            self.severity = 1

        self.rect = QRectF(0, 0, 300, 100)
        self.color = self._get_severity_color()
        self.isSelected = False
        self.setZValue(10)

    def _get_severity_color(self):
        if self.severity >= 8: return QColor("#f85149") 
        if self.severity >= 5: return QColor("#db6d28") 
        return QColor("#539bf5")

    def mousePressEvent(self, event):
        """Trigger the Neural Pulse on click."""
        self.clicked_signal.emit(self.data.get('fingerprint', ''))
        super().mousePressEvent(event)

    def boundingRect(self):
        return self.rect.adjusted(-20, -20, 20, 20)

    def paint(self, painter, option, widget):
        lod = option.levelOfDetailFromTransform(painter.worldTransform())
        
        # Highlighting logic
        pen_width = 3 if self.isSelected else 1.5
        
        if lod < 0.15:
            painter.setBrush(self.color)
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(0, 0, 80, 80)
        else:
            painter.setBrush(QColor(13, 17, 23, 240))
            painter.setPen(QPen(self.color, pen_width))
            painter.drawRoundedRect(self.rect, 4, 4)

            painter.setPen(Qt.white)
            painter.setFont(QFont("Consolas", 8, QFont.Bold))
            date_str = str(self.data.get('date', 'Unknown'))
            fp_str = str(self.data.get('fingerprint', '000000'))[:6]
            painter.drawText(10, 20, f"{date_str} | ID:{fp_str}")
            
            if lod > 0.4:
                painter.setPen(QColor("#adbac7"))
                painter.setFont(QFont("Segoe UI", 8))
                painter.drawText(self.rect.adjusted(10, 30, -10, -10), 
                                 Qt.TextWordWrap, str(self.data.get('label', '')))

class TimelineLabel(QGraphicsObject):
    def __init__(self, text):
        super().__init__()
        self.text = text
        self.setZValue(0)

    def boundingRect(self):
        return QRectF(0, 0, 1000, 400)

    def paint(self, painter, option, widget):
        painter.setPen(QColor(255, 255, 255, 10)) 
        painter.setFont(QFont("Segoe UI", 150, QFont.Black))
        painter.drawText(0, 200, self.text)