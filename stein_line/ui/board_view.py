import sqlite3
import re
from PySide6.QtWidgets import QGraphicsView, QGraphicsScene
from PySide6.QtCore import Qt, Slot, Signal, QPointF
from PySide6.QtGui import QPainter, QBrush, QColor
from .nodes import FactNode, TimelineLabel
from ..utils.coordinates import CoordinateEngine

class BoardView(QGraphicsView):
    # CRITICAL: Signal must be defined HERE at class level for .emit() to exist
    sig_node_selected = Signal(str)

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.coord_engine = CoordinateEngine(config)
        self.scene = QGraphicsScene()
        
        # PERFORMANCE: Use Binary Space Partitioning for 1.3M item speed
        self.scene.setItemIndexMethod(QGraphicsScene.BspTreeIndex)
        self.scene.setSceneRect(-100000.0, -100000.0, 200000.0, 200000.0)
        self.setScene(self.scene)
        
        # PERFORMANCE: Optimize viewport updates
        self.setViewportUpdateMode(QGraphicsView.MinimalViewportUpdate)
        self.setRenderHint(QPainter.Antialiasing, False) # Disable during high-load
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        
        self.setBackgroundBrush(QBrush(QColor("#0d1117")))
        self.day_stacks = {}

    def _safe_int(self, val):
        try:
            if val is None or str(val) == 'None': return 1
            match = re.search(r'\d+', str(val))
            return int(match.group()) if match else 1
        except: return 1

    def load_universe(self):
        if not self.config.intelligence_db_path: return
        # Disable indexing while loading large batches to prevent lag
        self.scene.setItemIndexMethod(QGraphicsScene.NoIndex)
        self.scene.clear()
        self.day_stacks = {}
        try:
            conn = sqlite3.connect(f"file:{self.config.intelligence_db_path}?mode=ro", uri=True)
            facts = conn.execute("SELECT * FROM intelligence ORDER BY associated_date DESC LIMIT 1000").fetchall()
            conn.close()
            self.stream_facts(facts)
        except Exception as e:
            self.sig_node_selected.emit(f"BOARD_LOAD_ERROR: {str(e)}")
        
        # Re-enable indexing after load
        self.scene.setItemIndexMethod(QGraphicsScene.BspTreeIndex)

    @Slot(list)
    def stream_facts(self, facts):
        for fact in facts:
            try:
                # fact indices: 0:fp, 3:date, 4:summary, 5:type, 7:severity
                fp = str(fact[0])
                date = str(fact[3])
                cat = str(fact[5])
                summary = str(fact[4])
                sev = self._safe_int(fact[7])
                
                cats = ['Financial', 'Legal', 'Communication', 'Travel', 'Operational Data', 'General Metadata', 'General']
                cat_idx = cats.index(cat) if cat in cats else 6
                
                stack_key = f"{date}-{cat_idx}"
                stack_idx = self.day_stacks.get(stack_key, 0)
                self.day_stacks[stack_key] = stack_idx + 1
                
                # Fetch coordinates and cast to float immediately
                x, y = self.coord_engine.get_pos(date, cat_idx, stack_idx)
                
                node = FactNode({'fingerprint': fp, 'date': date, 'label': summary, 'category': cat, 'severity': sev})
                node.setPos(float(x), float(y))
                # Connect node click back to our local handler
                node.clicked_signal.connect(self.on_node_clicked)
                self.scene.addItem(node)
            except: continue

    @Slot(str)
    def on_node_clicked(self, fingerprint):
        fp_str = str(fingerprint)
        # Emit to MainWindow Console
        self.sig_node_selected.emit(f"PULSE: {fp_str[:12]}...")
        
        # Fast update of highlights
        for item in self.scene.items():
            if isinstance(item, FactNode):
                item.isSelected = (item.data['fingerprint'] == fp_str)
                item.update()

    def wheelEvent(self, event):
        z = 1.25 if event.angleDelta().y() > 0 else 0.8
        self.scale(z, z)