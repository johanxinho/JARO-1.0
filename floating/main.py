import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QThread, pyqtSignal, QTimer

from capture import capture_screen
from ai_client import ask_gemini
from overlay import FloatingPanel


TRIGGER = Path.home() / ".cache" / "johanai" / "trigger"


class AIWorker(QThread):
    result = pyqtSignal(str)
    status = pyqtSignal(str)

    def run(self):
        try:
            screen_text = capture_screen()

            self.status.emit(
                f"Detectados {len(screen_text)} caracteres. "
                "Consultando Gemini..."
            )

            answer = ask_gemini(screen_text)
            self.result.emit(answer)

        except Exception as error:
            self.result.emit(f"Error: {error}")


class JohanAI:
    def __init__(self, app):
        self.app = app
        self.panel = FloatingPanel()
        self.panel.set_answer(
            "Panel del sistema listo.\n\n"
            "Pulsa Ctrl + 1 para analizar la pantalla."
        )
        self.panel.show()

        self.worker = None

        self.timer = QTimer()
        self.timer.timeout.connect(self.check_trigger)
        self.timer.start(150)

    def check_trigger(self):
        if not TRIGGER.exists():
            return

        TRIGGER.unlink(missing_ok=True)
        self.start_analysis()

    def start_analysis(self):
        if self.worker and self.worker.isRunning():
            self.panel.set_answer(
                "Ya hay una consulta en proceso. Espera un momento."
            )
            self.panel.show()
            self.panel.raise_()
            return

        self.panel.hide()

        # Oculta el panel antes de capturar para evitar leerlo.
        QTimer.singleShot(350, self.launch_worker)

    def launch_worker(self):
        self.worker = AIWorker()

        self.worker.status.connect(self.show_status)
        self.worker.result.connect(self.show_result)

        self.worker.start()

    def show_status(self, message):
        self.panel.set_answer(message)
        self.panel.show()
        self.panel.raise_()

    def show_result(self, answer):
        self.panel.set_answer(answer)
        self.panel.show()
        self.panel.raise_()


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)

    assistant = JohanAI(app)

    # Mantener vivo el controlador durante toda la aplicación.
    app.johanai = assistant

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
