from PyQt6.QtWidgets import (
    QWidget, QLabel, QPushButton, QVBoxLayout,
    QHBoxLayout, QSizeGrip, QPlainTextEdit
)
from PyQt6.QtCore import Qt


class FloatingPanel(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowOpacity(0.90)
        self.resize(230, 110)
        self.setMinimumSize(170, 75)

        self.drag_position = None
        self.setObjectName("panel")

        self.setStyleSheet("""
            QWidget#panel {
                background-color: rgba(25, 28, 36, 240);
                border: 1px solid rgba(255,255,255,45);
                border-radius: 12px;
                color: white;
            }
            QLabel {
                color: white;
                border: none;
            }
            QPushButton {
                background: transparent;
                color: white;
                border: none;
                padding: 2px 7px;
                font-size: 16px;
            }
            QPushButton:hover {
                background: rgba(255,255,255,35);
                border-radius: 5px;
            }
            QPlainTextEdit {
                background: transparent;
                color: white;
                border: none;
                font-size: 10px;
                selection-background-color: #4267a5;
            }
            QScrollBar:vertical {
                background: transparent;
                width: 5px;
                margin: 0;
            }
            QScrollBar::handle:vertical {
                background: rgba(255,255,255,100);
                border-radius: 2px;
                min-height: 15px;
            }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 5, 7, 5)
        layout.setSpacing(2)

        header = QHBoxLayout()
        title = QLabel("System Panel")
        close_button = QPushButton("×")
        close_button.clicked.connect(self.close)

        header.addWidget(title)
        header.addStretch()
        header.addWidget(close_button)

        self.answer = QPlainTextEdit()
        self.answer.setReadOnly(True)
        self.answer.setPlainText("Preparando consulta...")
        self.answer.setLineWrapMode(
            QPlainTextEdit.LineWrapMode.WidgetWidth
        )
        self.answer.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.answer.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        footer = QHBoxLayout()
        footer.addStretch()
        footer.addWidget(QSizeGrip(self))

        layout.addLayout(header)
        layout.addWidget(self.answer, 1)
        layout.addLayout(footer)

    def set_answer(self, text):
        self.answer.setPlainText(text)
        self.answer.verticalScrollBar().setValue(0)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = (
                event.globalPosition().toPoint()
                - self.frameGeometry().topLeft()
            )
            event.accept()

    def mouseMoveEvent(self, event):
        if (
            self.drag_position is not None
            and event.buttons() & Qt.MouseButton.LeftButton
        ):
            self.move(
                event.globalPosition().toPoint() - self.drag_position
            )
            event.accept()

    def mouseReleaseEvent(self, event):
        self.drag_position = None
