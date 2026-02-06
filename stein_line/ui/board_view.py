import sqlite3
from PySide6.QtWidgets import QGraphicsView, QGraphicsScene
from PySide6.QtCore import Qt, Slot, QPointF
from PySide6.QtGui import QPainter, QBrush, QColor
from .nodes import FactNode, TimelineLabel
from ..utils.coordinates import CoordinateEngine

class BoardView(QGraphicsView):
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.coord_engine = CoordinateEngine(config)
        self.scene = QGraphicsScene()
        self.setScene(self.scene)
        
        self.setRenderHint(QPainter.Antialiasing)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setBackgroundBrush(QBrush(QColor("#0d1117")))
        
        # Track stacking to prevent node overlap
        self.day_stacks = {} 

    @Slot(list)
    def stream_facts(self, facts):
        """Real-time drop of cards onto the canvas."""
        for fact in facts:
            # fact = [fp, fn, source, date, summary, type, crime, severity]
            clean_date = fact[3].replace("-XX", "-01")
            
            # Simple Category index mapping
            cats = ['Financial', 'Legal', 'Communication', 'Travel', 'Operational Data', 'General Metadata', 'General']
            cat_idx = cats.index(fact[5]) if fact[5] in cats else 6
            
            # Manage stacking for this specific day
            stack_key = f"{clean_date}-{cat_idx}"
            self.day_stacks[stack_key] = self.day_stacks.get(stack_key, 0) + 1
            
            x, y = self.coord_engine.get_pos(fact[3], cat_idx, self.day_stacks[stack_key])
            
            node_data = {
                'fingerprint': fact[0], 'fileName': fact[1], 'label': fact[4],
                'date': fact[3], 'category': fact[5], 'severity': fact[7]
            }
            
            node = FactNode(node_data)
            node.setPos(x, y)
            node.clicked_signal.connect(self.highlight_spiderweb)
            self.scene.addItem(node)

    def highlight_spiderweb(self, fingerprint):
        """Light up all instances of a specific file."""
        self.config.is_ready = False # Internal block to prevent concurrent logic errors
        for item in self.scene.items():
            if isinstance(item, FactNode):
                item.isSelected = (item.data['fingerprint'] == fingerprint)
                item.update()
        self.config.is_ready = True

    def wheelEvent(self, event):
        zoom = 1.25 if event.angleDelta().y() > 0 else 0.8
        self.scale(zoom, zoom)