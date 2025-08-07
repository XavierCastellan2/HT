import asyncio
import struct
from bleak import BleakScanner, BleakClient
from typing import Optional, Dict, Callable
import queue

# Service UUIDs
HR_SERVICE_UUID = "0000180d-0000-1000-8000-00805f9b34fb"
CSC_SERVICE_UUID = "00001816-0000-1000-8000-00805f9b34fb"
POWER_SERVICE_UUID = "00001818-0000-1000-8000-00805f9b34fb"
FTMS_SERVICE_UUID = "00001826-0000-1000-8000-00805f9b34fb"

# Characteristic UUIDs
HR_MEASUREMENT_CHAR_UUID = "00002a37-0000-1000-8000-00805f9b34fb"
CSC_MEASUREMENT_CHAR_UUID = "00002a5b-0000-1000-8000-00805f9b34fb"
POWER_MEASUREMENT_CHAR_UUID = "00002a63-0000-1000-8000-00805f9b34fb"
FTMS_CONTROL_POINT_CHAR_UUID = "00002ad9-0000-1000-8000-00805f9b34fb"


class DeviceManager:
    def __init__(self, ui_queue: queue.Queue):
        self.ui_queue = ui_queue
        self.clients: Dict[str, Optional[BleakClient]] = {
            "hrm": None,
            "csc": None,
            "power": None,
            "ftms": None,
        }
        self.discovered_devices = []

    async def scan(self, timeout=5.0):
        """Scans for BLE devices and puts the results in the UI queue."""
        print(f"Scanning for devices for {timeout} seconds...")

        devices_found = {}

        def detection_callback(device, advertisement_data):
            if device.address not in devices_found:
                devices_found[device.address] = device

        scanner = BleakScanner(detection_callback=detection_callback)
        await scanner.start()
        await asyncio.sleep(timeout)
        await scanner.stop()

        self.discovered_devices = list(devices_found.values())
        self.ui_queue.put({"type": "scan_complete", "devices": self.discovered_devices})

    async def connect_to_device(self, device_type: str, address: str):
        """Connects to a device and reports the status to the UI queue."""
        if device_type not in self.clients:
            print(f"Error: Invalid device type '{device_type}'")
            return

        print(f"Attempting to connect to {address} as {device_type}...")
        client = None
        try:
            client = BleakClient(address)
            await client.connect()
            self.clients[device_type] = client
            status = "Connected"
            print(f"Successfully connected to {address} as {device_type}.")
        except Exception as e:
            print(f"Failed to connect to {address}: {e}")
            self.clients[device_type] = None
            status = "Failed"

        self.ui_queue.put({"type": "connection_status", "device_type": device_type, "status": status, "address": address})


    async def disconnect(self):
        """Disconnects all connected clients."""
        for device_type, client in self.clients.items():
            if client and client.is_connected:
                print(f"Disconnecting from {device_type} device...")
                await client.disconnect()
        print("All devices disconnected.")

    def get_client(self, device_type: str) -> Optional[BleakClient]:
        """Returns the client for a given device type."""
        return self.clients.get(device_type)

    # --- Notification Handlers ---
    def _handle_hr_notification(self, sender: int, data: bytearray):
        flags = data[0]
        hr_format = (flags >> 0) & 1
        hr_value = struct.unpack_from("<H" if hr_format == 1 else "<B", data, 1)[0]
        self.ui_queue.put({"type": "hr_update", "value": hr_value})

    def _handle_csc_notification(self, sender: int, data: bytearray):
        flags = data[0]
        offset = 1
        update_data = {"type": "csc_update"}
        if (flags >> 0) & 1: # Wheel Revolution Data Present
            wheel_revolutions = struct.unpack_from("<L", data, offset)[0]
            last_wheel_event_time = struct.unpack_from("<H", data, offset + 4)[0]
            update_data.update({"wheel_rev": wheel_revolutions, "wheel_time": last_wheel_event_time})
            offset += 6
        if (flags >> 1) & 1: # Crank Revolution Data Present
            crank_revolutions = struct.unpack_from("<H", data, offset)[0]
            last_crank_event_time = struct.unpack_from("<H", data, offset + 2)[0]
            update_data.update({"crank_rev": crank_revolutions, "crank_time": last_crank_event_time})
        self.ui_queue.put(update_data)

    def _handle_power_notification(self, sender: int, data: bytearray):
        power_value = struct.unpack_from("<h", data, 2)[0]
        self.ui_queue.put({"type": "power_update", "value": power_value})

    # --- Methods to start notifications ---
    async def start_notifications(self, device_type: str):
        client = self.get_client(device_type)
        if not (client and client.is_connected):
            print(f"{device_type.upper()} device not connected.")
            return

        char_uuid, handler = None, None
        if device_type == "hrm":
            char_uuid, handler = HR_MEASUREMENT_CHAR_UUID, self._handle_hr_notification
        elif device_type == "csc":
            char_uuid, handler = CSC_MEASUREMENT_CHAR_UUID, self._handle_csc_notification
        elif device_type == "power":
            char_uuid, handler = POWER_MEASUREMENT_CHAR_UUID, self._handle_power_notification

        if char_uuid and handler:
            print(f"Starting {device_type.upper()} notifications...")
            try:
                await client.start_notify(char_uuid, handler)
            except Exception as e:
                print(f"Failed to start {device_type.upper()} notifications: {e}")
