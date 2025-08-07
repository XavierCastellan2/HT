import tkinter as tk
from tkinter import ttk, filedialog
import asyncio
import threading
import queue
import time
from src.cycling_manager import CyclingManager
from src.erg_parser import parse_erg
from src.workout_manager import WorkoutManager
from src.graph_widget import TrainingGraph

class App(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("BLE Training App")
        self.geometry("800x700")

        # --- Data Stores for Graphing ---
        self.start_time = 0
        self.power_data = []
        self.target_power_data = []
        self.hr_data = []
        self.cadence_data = []

        # --- Asyncio and Threading Setup ---
        self.queue = queue.Queue()
        self.loop = asyncio.new_event_loop()
        self.asyncio_thread = threading.Thread(target=self.start_asyncio_loop, daemon=True)
        self.asyncio_thread.start()
        self.workout_task = None

        # --- Business Logic ---
        self.cycling_manager = CyclingManager(self.queue)
        self.workout_manager = WorkoutManager(self.cycling_manager, self.queue)
        self.device_lists = {}

        # --- UI Initialization ---
        self.create_ui()
        self.after(100, self.check_queue)
        self.after(1000, self.update_graph) # Schedule graph updates
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def create_ui(self):
        # ... (Same controls and device frames as before)
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        controls_frame = ttk.LabelFrame(main_frame, text="Controls")
        controls_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        # ... buttons ...
        self.btn_load_erg = ttk.Button(controls_frame, text="Load ERG File", command=self.load_erg_file)
        self.btn_load_erg.pack(side=tk.LEFT, padx=5, pady=5)
        self.btn_scan = ttk.Button(controls_frame, text="Scan for Devices", command=self.start_scan)
        self.btn_scan.pack(side=tk.LEFT, padx=5, pady=5)
        self.btn_connect = ttk.Button(controls_frame, text="Connect", command=self.start_connect)
        self.btn_connect.pack(side=tk.LEFT, padx=5, pady=5)
        self.btn_start = ttk.Button(controls_frame, text="Start Workout", command=self.start_workout)
        self.btn_start.pack(side=tk.LEFT, padx=5, pady=5)

        devices_frame = ttk.LabelFrame(main_frame, text="Devices")
        devices_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        roles = ["hrm", "csc", "power", "ftms", "tacx"]
        for i, role in enumerate(roles):
            ttk.Label(devices_frame, text=f"{role.upper()}:").grid(row=0, column=i, padx=10, pady=2, sticky=tk.W)
            listbox = tk.Listbox(devices_frame, exportselection=False, height=5)
            listbox.grid(row=1, column=i, padx=10, pady=5, sticky=tk.EW)
            self.device_lists[role] = listbox
        devices_frame.grid_columnconfigure(list(range(len(roles))), weight=1)

        # --- Graph Frame ---
        graph_frame = ttk.LabelFrame(main_frame, text="Training Graph")
        graph_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.graph = TrainingGraph(graph_frame)
        self.graph.pack(fill=tk.BOTH, expand=True)

        # --- Live Data & Status Frame ---
        bottom_frame = ttk.Frame(main_frame)
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=5)

        data_frame = ttk.LabelFrame(bottom_frame, text="Live Data")
        data_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.lbl_hr = ttk.Label(data_frame, text="HR: -- BPM", font=("Helvetica", 12))
        self.lbl_hr.pack(anchor=tk.W, padx=10, pady=2)
        self.lbl_cadence = ttk.Label(data_frame, text="Cadence: -- RPM", font=("Helvetica", 12))
        self.lbl_cadence.pack(anchor=tk.W, padx=10, pady=2)
        self.lbl_power = ttk.Label(data_frame, text="Power: -- W", font=("Helvetica", 12))
        self.lbl_power.pack(anchor=tk.W, padx=10, pady=2)
        self.lbl_target_power = ttk.Label(data_frame, text="Target Power: -- W", font=("Helvetica", 12, "bold"))
        self.lbl_target_power.pack(anchor=tk.W, padx=10, pady=2)

        status_frame = ttk.LabelFrame(bottom_frame, text="Status")
        status_frame.pack(side=tk.RIGHT, fill=tk.X, expand=True)
        self.lbl_status = ttk.Label(status_frame, text="Status: Idle", font=("Helvetica", 10))
        self.lbl_status.pack(anchor=tk.W, padx=10, pady=5)
        self.progress = ttk.Progressbar(status_frame, orient=tk.HORIZONTAL, length=100, mode='determinate')
        self.progress.pack(fill=tk.X, expand=True, padx=10, pady=5)

    def start_workout(self):
        # Reset data stores
        self.start_time = time.time()
        self.power_data = []
        self.target_power_data = []
        self.hr_data = []
        self.cadence_data = []
        self.graph.clear_plot()

        self.lbl_status.config(text="Status: Starting workout...")
        self.workout_task = asyncio.run_coroutine_threadsafe(self.workout_manager.run_workout(), self.loop)

    def check_queue(self):
        while not self.queue.empty():
            message = self.queue.get_nowait()
            msg_type = message.get("type")
            elapsed_time = time.time() - self.start_time if self.start_time else 0

            if msg_type == "hr_update":
                val = message.get('value')
                self.lbl_hr.config(text=f"HR: {val} BPM")
                self.graph.add_data_point("hr", elapsed_time, val)
            elif msg_type == "power_update":
                val = message.get('value')
                self.lbl_power.config(text=f"Power: {val} W")
                self.graph.add_data_point("power", elapsed_time, val)
            elif msg_type == "csc_update":
                val = message.get('crank_rev', 0) # simplified
                self.lbl_cadence.config(text=f"Cadence: {val} RPM")
                self.graph.add_data_point("cadence", elapsed_time, val)
            elif msg_type == "workout_update":
                val = message.get('target_power')
                self.lbl_target_power.config(text=f"Target Power: {val} W")
                self.progress['value'] = message.get('progress', 0)
                self.graph.add_data_point("target_power", elapsed_time, val)
            # ... other handlers ...
            elif msg_type == "scan_complete":
                self.handle_scan_complete(message.get("devices", []))
            elif msg_type == "connection_status":
                self.handle_connection_status(message)
            elif msg_type == "status_update":
                self.lbl_status.config(text=f"Status: {message.get('message')}")
            elif msg_type == "workout_finished":
                self.lbl_status.config(text=f"Status: {message.get('message')}")
                self.progress['value'] = 100

        self.after(100, self.check_queue)

    def update_graph(self):
        """Periodically redraws the graph."""
        if self.workout_manager._is_running:
            self.graph.draw_plot()
        self.after(1000, self.update_graph)

    # ... (rest of the methods are the same)
    def start_asyncio_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def load_erg_file(self):
        filepath = filedialog.askopenfilename(filetypes=[("ERG Files", "*.erg"), ("All files", "*.*")])
        if not filepath: return
        workout_data = parse_erg(filepath)
        if workout_data:
            self.workout_manager.load_workout(workout_data)
            self.lbl_status.config(text=f"Status: Loaded workout from {filepath}")
        else:
            self.lbl_status.config(text=f"Status: Failed to load workout from {filepath}")

    def start_scan(self):
        self.lbl_status.config(text="Status: Scanning...")
        for listbox in self.device_lists.values(): listbox.delete(0, tk.END)
        asyncio.run_coroutine_threadsafe(self.cycling_manager.scan(), self.loop)

    def start_connect(self):
        devices_to_connect = []
        for role, listbox in self.device_lists.items():
            selection_indices = listbox.curselection()
            if selection_indices:
                device_address = listbox.get(selection_indices[0]).split('(')[-1].strip(')')
                devices_to_connect.append((role, device_address))
        if devices_to_connect:
            asyncio.run_coroutine_threadsafe(self.cycling_manager.connect_all_devices(devices_to_connect), self.loop)
        else:
            self.lbl_status.config(text="Status: No devices selected to connect.")

    def handle_scan_complete(self, devices):
        self.lbl_status.config(text=f"Status: Scan complete. Found {len(devices)} devices.")
        for listbox in self.device_lists.values(): listbox.delete(0, tk.END)
        for device in devices:
            display_name = f"{device.name or 'Unknown'} ({device.address})"
            for listbox in self.device_lists.values(): listbox.insert(tk.END, display_name)

    def handle_connection_status(self, message):
        role = message.get("device_type")
        status = message.get("status")
        self.lbl_status.config(text=f"Status: {role.upper()} {status}")

    def on_closing(self):
        print("Closing application...")
        if self.loop.is_running():
            self.workout_manager.stop_workout()
            if self.workout_task: self.workout_task.cancel()
            asyncio.run_coroutine_threadsafe(self.cycling_manager.disconnect(), self.loop)
            self.loop.call_soon_threadsafe(self.loop.stop)
        self.destroy()

if __name__ == '__main__':
    app = App()
    app.mainloop()
