import sys
import asyncio
import qasync
from PySide6.QtWidgets import QApplication
from src.ui import MainWindow

def main():
    """
    Main entry point for the Qt application.

    This script initializes the Qt Application and the qasync event loop,
    which allows asyncio to work with Qt's event system.
    """
    app = QApplication(sys.argv)

    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    window = MainWindow(loop)
    window.show()

    with loop:
        loop.run_forever()

if __name__ == "__main__":
    main()
