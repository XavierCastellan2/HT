import sys
import time
import queue
import qasync
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QGroupBox, QLabel, QListWidget, QProgressBar, QFileDialog
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont

from src.cycling_manager import CyclingManager
from src.erg_parser import parse_erg
from src.workout_manager import WorkoutManager
from src.graph_widget import TrainingGraph

class MainWindow(QMainWindow):
    def __init__(self, loop):
        super().__init__()
        self.loop = loop

        self.setWindowTitle("Qt BLE Training App")
        self.setGeometry(100, 100, 800, 700)

        self.start_time = 0
        self.queue = queue.Queue()

        self.cycling_manager = CyclingManager(self.queue)
        self.workout_manager = WorkoutManager(self.cycling_manager, self.queue)
        self.device_lists = {}
        self.devices_by_role = {}

        self._create_ui()

        self.queue_timer = QTimer()
        self.queue_timer.timeout.connect(self.check_queue)
        self.queue_timer.start(100)

        self.graph_timer = QTimer()
        self.graph_timer.timeout.connect(self.update_graph)
        self.graph_timer.start(1000)

    def _create_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout()
        main_widget.setLayout(main_layout)

        controls_group = QGroupBox("Controls")
        controls_layout = QHBoxLayout()
        controls_group.setLayout(controls_layout)

        self.btn_load_erg = QPushButton("Load ERG")
        self.btn_scan = QPushButton("Scan")
        self.btn_connect = QPushButton("Connect")
        self.btn_start = QPushButton("Start Workout")
        self.btn_disconnect = QPushButton("Disconnect")

        self.btn_load_erg.clicked.connect(self.load_erg_file)
        self.btn_scan.clicked.connect(self.start_scan)
        self.btn_connect.clicked.connect(self.start_connect)
        self.btn_start.clicked.connect(self.start_workout)
        self.btn_disconnect.clicked.connect(self.disconnect_devices)

        controls_layout.addWidget(self.btn_load_erg)
        controls_layout.addWidget(self.btn_scan)
        controls_layout.addWidget(self.btn_connect)
        controls_layout.addWidget(self.btn_start)
        controls_layout.addWidget(self.btn_disconnect)
        controls_layout.addStretch()

        devices_group = QGroupBox("Devices")
        devices_layout = QGridLayout()
        devices_group.setLayout(devices_layout)

        roles = ["hrm", "csc", "power", "ftms", "tacx"]
        for i, role in enumerate(roles):
            devices_layout.addWidget(QLabel(f"{role.upper()}:"), 0, i)
            list_widget = QListWidget()
            self.device_lists[role] = list_widget
            devices_layout.addWidget(list_widget, 1, i)

        info_group = QGroupBox("Info & Status")
        info_layout = QGridLayout()
        info_group.setLayout(info_layout)

        # --- Create Fonts ---
        data_font = QFont()
        data_font.setPointSize(20)
        target_font = QFont()
        target_font.setPointSize(24)
        target_font.setBold(True)

        # Create labels for values
        self.lbl_hr = QLabel("--")
        self.lbl_cadence = QLabel("--")
        self.lbl_power = QLabel("--")
        self.lbl_target_power = QLabel("--")
        self.lbl_status = QLabel("Idle")
        self.progress = QProgressBar()

        # Apply fonts
        self.lbl_hr.setFont(data_font)
        self.lbl_cadence.setFont(data_font)
        self.lbl_power.setFont(data_font)
        self.lbl_target_power.setFont(target_font)

        # Add labels and widgets to grid
        info_layout.addWidget(QLabel("Target Power:"), 0, 0)
        info_layout.addWidget(self.lbl_target_power, 0, 1)
        info_layout.addWidget(QLabel("Power:"), 1, 0)
        info_layout.addWidget(self.lbl_power, 1, 1)
        info_layout.addWidget(QLabel("Heart Rate:"), 0, 2)
        info_layout.addWidget(self.lbl_hr, 0, 3)
        info_layout.addWidget(QLabel("Cadence:"), 1, 2)
        info_layout.addWidget(self.lbl_cadence, 1, 3)
        info_layout.addWidget(QLabel("Status:"), 0, 4)
        info_layout.addWidget(self.lbl_status, 0, 5)
        info_layout.addWidget(QLabel("Progress:"), 1, 4)
        info_layout.addWidget(self.progress, 1, 5)

        self.graph = TrainingGraph()

        main_layout.addWidget(controls_group)
        main_layout.addWidget(devices_group)
        main_layout.addWidget(info_group)
        main_layout.addWidget(self.graph, stretch=1)

    def start_scan(self):
        self.lbl_status.setText("Scanning...")
        for listbox in self.device_lists.values():
            listbox.clear()
        self.loop.create_task(self.cycling_manager.scan())

    def start_connect(self):
        devices_to_connect = []
        for role, listbox in self.device_lists.items():
            selected_items = listbox.selectedItems()
            if selected_items:
                device_text = selected_items[0].text()
                device_address = device_text.split('(')[-1].strip(')')
                devices_to_connect.append((role, device_address))
        if devices_to_connect:
            self.loop.create_task(self.cycling_manager.connect_all_devices(devices_to_connect))
        else:
            self.lbl_status.setText("No devices selected.")

    def disconnect_devices(self):
        self.lbl_status.setText("Disconnecting all devices...")
        self.workout_manager.stop_workout()
        self.loop.create_task(self.cycling_manager.disconnect())

    def load_erg_file(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Open ERG File", "", "ERG Files (*.erg);;All Files (*)")
        if not filepath: return
        workout_data = parse_erg(filepath)
        if workout_data:
            self.workout_manager.load_workout(workout_data)
            self.lbl_status.setText(f"Loaded {filepath}")
        else:
            self.lbl_status.setText(f"Failed to load {filepath}")

    def start_workout(self):
        if not self.workout_manager.workout:
            self.lbl_status.setText("Please load an ERG file first.")
            return
        self.start_time = time.time()
        self.graph.clear_plot()
        total_duration = self.workout_manager.workout[-1][0]
        self.graph.set_time_axis_range(total_duration)
        self.lbl_status.setText("Starting workout...")
        self.loop.create_task(self.workout_manager.run_workout())

    def check_queue(self):
        while not self.queue.empty():
            message = self.queue.get_nowait()
            msg_type = message.get("type")
            if msg_type == "scan_complete":
                self.handle_scan_complete(message.get("devices_by_role", {}))
            elif msg_type in ["hr_update", "power_update", "csc_update", "workout_update"]:
                self.handle_data_update(message)
            elif msg_type in ["connection_status", "status_update", "workout_finished"]:
                self.handle_status_update(message)

    def handle_data_update(self, message):
        msg_type = message.get("type")
        elapsed_time = time.time() - self.start_time if self.start_time else 0
        if msg_type == "hr_update":
            self.lbl_hr.setText(f"{message.get('value')} BPM")
            self.graph.add_data_point("hr", elapsed_time, message.get('value'))
        elif msg_type == "power_update":
            self.lbl_power.setText(f"{message.get('value')} W")
            self.graph.add_data_point("power", elapsed_time, message.get('value'))
        elif msg_type == "csc_update":
            self.lbl_cadence.setText(f"{message.get('crank_rev', 0)} RPM")
            self.graph.add_data_point("cadence", elapsed_time, message.get('crank_rev', 0))
        elif msg_type == "workout_update":
            self.lbl_target_power.setText(f"{message.get('target_power')} W")
            self.progress.setValue(int(message.get('progress', 0)))
            self.graph.add_data_point("target_power", elapsed_time, message.get('target_power'))

    def handle_status_update(self, message):
        msg_type = message.get("type")
        if msg_type == "connection_status":
            self.lbl_status.setText(f"{message.get('device_type').upper()} {message.get('status')}")
        elif msg_type == "workout_finished":
            self.lbl_status.setText(f"{message.get('message')}")
            self.progress.setValue(100)
        else:
            self.lbl_status.setText(message.get('message'))

    def handle_scan_complete(self, devices_by_role):
        self.devices_by_role = devices_by_role
        self.lbl_status.setText("Scan complete.")
        for role, listbox in self.device_lists.items():
            listbox.clear()
            for device in devices_by_role.get(role, []):
                listbox.addItem(f"{device.name or 'Unknown'} ({device.address})")

    def update_graph(self):
        if self.workout_manager._is_running:
            self.graph.draw_plot()

    @qasync.asyncClose
    async def closeEvent(self, event):
        print("Closing application...")
        self.workout_manager.stop_workout()
        await self.cycling_manager.disconnect()
        super().closeEvent(event)
