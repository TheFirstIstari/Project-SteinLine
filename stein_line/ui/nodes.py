import re
from PySide6.QtWidgets import QGraphicsObject
from PySide6.QtCore import Qt, QRectF, Signal, QPointF
from PySide6.QtGui import QColor, QPen, QBrush, QFont

class FactNode(QGraphicsObject):
    clicked_signal = Signal(str) # Defined at class level

    def __init__(self, data):
        super().__init__()
        
        # PRE-INITIALIZE ALL ATTRIBUTES (Prevents AttributeError)
        self.rect = QRectF(0.0, 0.0, 300.0, 100.0)
        self.isSelected = False
        self.setZValue(10.0)
        
        self.data = {
            'fingerprint': str(data.get('fingerprint', '')),
            'date': str(data.get('date', 'Unknown')),
            'label': str(data.get('label', '')),
            'severity': 1
        }
        
        try:
            match = re.search(r'\d+', str(data.get('severity', 1)))
            self.data['severity'] = int(match.group()) if match else 1
        except:
            self.data['severity'] = 1

        s = self.data['severity']
        if s >= 8: self.color = QColor("#f85149")
        elif s >= 5: self.color = QColor("#db6d28")
        else: self.color = QColor("#539bf5")

    def mousePressEvent(self, event):
        self.clicked_signal.emit(self.data['fingerprint'])
        event.accept()
        super().mousePressEvent(event)

    def boundingRect(self):
        return self.rect.adjusted(-5.0, -5.0, 5.0, 5.0)

    def paint(self, painter, option, widget):
        # LEVEL OF DETAIL (LOD) check
        lod = float(option.levelOfDetailFromTransform(painter.worldTransform()))
        
        if lod < 0.1:
            # Low LOD: Just a simple circle (Ultra fast)
            painter.setBrush(self.color)
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(0, 0, 80, 80)
            return

        # High LOD: Standard Forensic Card
        painter.setBrush(QColor(13, 17, 23))
        painter.setPen(QPen(self.color, 4.0 if self.isSelected else 1.5))
        painter.drawRoundedRect(self.rect, 4.0, 4.0)

        painter.setPen(Qt.white)
        painter.setFont(QFont("Consolas", 8, QFont.Bold))
        painter.drawText(10, 20, f"{self.data['date']} | ID:{self.data['fingerprint'][:6]}")
        
        if lod > 0.4:
            painter.setPen(QColor("#adbac7"))
            painter.setFont(QFont("Segoe UI", 8))
            painter.drawText(self.rect.adjusted(10, 30, -10, -10), Qt.TextWordWrap, self.data['label'])

class TimelineLabel(QGraphicsObject):
    def __init__(self, text):
        super().__init__()
        self.text = str(text)
        self.setZValue(0.0)

    def boundingRect(self):
        return QRectF(0.0, 0.0, 1000.0, 400.0)

    def paint(self, painter, option, widget):
        painter.setPen(QColor(255, 255, 255, 10)) 
        painter.setFont(QFont("Segoe UI", 120, QFont.Black))
        painter.drawText(0, 200, self.text)