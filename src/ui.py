import tkinter as tk
from tkinter import ttk, filedialog
import asyncio
import threading
import queue
from src.cycling_manager import CyclingManager
from src.erg_parser import parse_erg
from src.workout_manager import WorkoutManager

class App(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("BLE Training App")
        self.geometry("800x600")

        # --- Asyncio and Threading Setup ---
        self.queue = queue.Queue()
        self.loop = asyncio.new_event_loop()
        self.asyncio_thread = threading.Thread(target=self.start_asyncio_loop, daemon=True)
        self.asyncio_thread.start()

        # --- Business Logic ---
        self.cycling_manager = CyclingManager(self.queue)
        self.workout_manager = WorkoutManager(self.cycling_manager, self.queue)
        self.device_lists = {}

        # --- UI Initialization ---
        self.create_ui()
        self.after(100, self.check_queue)
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def create_ui(self):
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Controls Frame
        controls_frame = ttk.LabelFrame(main_frame, text="Controls")
        controls_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        self.btn_load_erg = ttk.Button(controls_frame, text="Load ERG File", command=self.load_erg_file)
        self.btn_load_erg.pack(side=tk.LEFT, padx=5, pady=5)
        self.btn_scan = ttk.Button(controls_frame, text="Scan for Devices", command=self.start_scan)
        self.btn_scan.pack(side=tk.LEFT, padx=5, pady=5)
        self.btn_connect = ttk.Button(controls_frame, text="Connect", command=self.start_connect)
        self.btn_connect.pack(side=tk.LEFT, padx=5, pady=5)
        self.btn_start = ttk.Button(controls_frame, text="Start Workout", command=self.start_workout)
        self.btn_start.pack(side=tk.LEFT, padx=5, pady=5)

        # Devices Frame
        devices_frame = ttk.LabelFrame(main_frame, text="Devices")
        devices_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        roles = ["hrm", "csc", "power", "ftms", "tacx"]
        for i, role in enumerate(roles):
            ttk.Label(devices_frame, text=f"{role.upper()}:").grid(row=0, column=i, padx=10, pady=2, sticky=tk.W)
            listbox = tk.Listbox(devices_frame, exportselection=False, height=5)
            listbox.grid(row=1, column=i, padx=10, pady=5, sticky=tk.EW)
            self.device_lists[role] = listbox
        devices_frame.grid_columnconfigure(list(range(len(roles))), weight=1)

        # Data Frame
        data_frame = ttk.LabelFrame(main_frame, text="Live Data")
        data_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.lbl_hr = ttk.Label(data_frame, text="HR: -- BPM", font=("Helvetica", 14))
        self.lbl_hr.pack(anchor=tk.W, padx=10, pady=5)
        self.lbl_cadence = ttk.Label(data_frame, text="Cadence: -- RPM", font=("Helvetica", 14))
        self.lbl_cadence.pack(anchor=tk.W, padx=10, pady=5)
        self.lbl_power = ttk.Label(data_frame, text="Power: -- W", font=("Helvetica", 14))
        self.lbl_power.pack(anchor=tk.W, padx=10, pady=5)
        self.lbl_target_power = ttk.Label(data_frame, text="Target Power: -- W", font=("Helvetica", 14, "bold"))
        self.lbl_target_power.pack(anchor=tk.W, padx=10, pady=10)
        self.lbl_status = ttk.Label(data_frame, text="Status: Idle", font=("Helvetica", 10))
        self.lbl_status.pack(anchor=tk.W, padx=10, pady=10)

        # Status/Progress Bar
        status_frame = ttk.Frame(main_frame)
        status_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=5)
        self.progress = ttk.Progressbar(status_frame, orient=tk.HORIZONTAL, length=100, mode='determinate')
        self.progress.pack(fill=tk.X, expand=True)

    def start_asyncio_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def load_erg_file(self):
        filepath = filedialog.askopenfilename(filetypes=[("ERG Files", "*.erg"), ("All files", "*.*")])
        if not filepath:
            return

        workout_data = parse_erg(filepath)
        if workout_data:
            self.workout_manager.load_workout(workout_data)
            self.lbl_status.config(text=f"Status: Loaded workout from {filepath}")
        else:
            self.lbl_status.config(text=f"Status: Failed to load workout from {filepath}")

    def start_scan(self):
        self.lbl_status.config(text="Status: Scanning...")
        for listbox in self.device_lists.values():
            listbox.delete(0, tk.END)
        asyncio.run_coroutine_threadsafe(self.cycling_manager.scan(), self.loop)

    def start_connect(self):
        self.lbl_status.config(text="Status: Connecting...")
        for role, listbox in self.device_lists.items():
            selection_indices = listbox.curselection()
            if selection_indices:
                selection_index = listbox.curselection()[0]
                device_address = listbox.get(selection_index).split('(')[-1].strip(')')
                asyncio.run_coroutine_threadsafe(
                    self.cycling_manager.connect_to_device(role, device_address),
                    self.loop
                )

    def start_workout(self):
        self.lbl_status.config(text="Status: Starting workout...")
        self.workout_manager.start_workout()

    def check_queue(self):
        while not self.queue.empty():
            message = self.queue.get_nowait()
            msg_type = message.get("type")

            if msg_type == "scan_complete":
                self.handle_scan_complete(message.get("devices", []))
            elif msg_type == "connection_status":
                self.handle_connection_status(message)
            elif msg_type == "status_update":
                self.lbl_status.config(text=f"Status: {message.get('message')}")
            elif msg_type == "hr_update":
                self.lbl_hr.config(text=f"HR: {message.get('value')} BPM")
            elif msg_type == "power_update":
                self.lbl_power.config(text=f"Power: {message.get('value')} W")
            elif msg_type == "csc_update":
                cadence = message.get('crank_rev', '--')
                self.lbl_cadence.config(text=f"Cadence: {cadence} RPM")
            elif msg_type == "workout_update":
                self.lbl_target_power.config(text=f"Target Power: {message.get('target_power')} W")
                self.progress['value'] = message.get('progress', 0)
            elif msg_type == "workout_finished":
                self.lbl_status.config(text=f"Status: {message.get('message')}")
                self.progress['value'] = 100

        self.after(100, self.check_queue)

    def handle_scan_complete(self, devices):
        self.lbl_status.config(text=f"Status: Scan complete. Found {len(devices)} devices.")
        for listbox in self.device_lists.values():
            listbox.delete(0, tk.END)
        for device in devices:
            display_name = f"{device.name or 'Unknown'} ({device.address})"
            for listbox in self.device_lists.values():
                listbox.insert(tk.END, display_name)

    def handle_connection_status(self, message):
        role = message.get("device_type")
        status = message.get("status")
        self.lbl_status.config(text=f"Status: {role.upper()} {status}")

    def on_closing(self):
        print("Closing application...")
        if self.loop.is_running():
            self.workout_manager.stop_workout()
            asyncio.run_coroutine_threadsafe(self.cycling_manager.disconnect(), self.loop)
            self.loop.call_soon_threadsafe(self.loop.stop)
        self.destroy()

if __name__ == '__main__':
    app = App()
    app.mainloop()
