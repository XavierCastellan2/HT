import asyncio
import queue
from bleak import BleakScanner, BleakClient
from typing import Optional, Dict, List

from pycycling.heart_rate_service import HeartRateService
from pycycling.cycling_speed_cadence_service import CyclingSpeedCadenceService
from pycycling.cycling_power_service import CyclingPowerService
from pycycling.fitness_machine_service import FitnessMachineService
from pycycling.tacx_trainer_control import TacxTrainerControl

class CyclingManager:
    """A manager for all BLE cycling device interactions using pycycling."""

    def __init__(self, ui_queue: queue.Queue):
        self.ui_queue = ui_queue
        self.clients: Dict[str, BleakClient] = {}
        self.services: Dict[str, object] = {}
        self.discovered_devices: List[BleakClient] = []

    async def scan(self, timeout=5.0):
        """Scans for BLE devices and informs the UI."""
        print(f"Scanning for devices for {timeout} seconds...")
        self.discovered_devices = await BleakScanner.discover(timeout=timeout)
        self.ui_queue.put({"type": "scan_complete", "devices": self.discovered_devices})

    async def connect_to_device(self, device_type: str, address: str):
        """Connects to a device, initializes the pycycling service, and enables notifications."""
        print(f"Attempting to connect to {address} as {device_type}...")
        status = "Failed"
        try:
            client = BleakClient(address)
            await client.connect()
            self.clients[device_type] = client

            service = self._initialize_service(device_type, client)
            if service:
                self.services[device_type] = service
                # For Tacx, the handler is set before enabling notifications
                if device_type == "tacx":
                     service.set_specific_trainer_data_page_handler(self._handle_tacx_update)
                await service.enable_notifications()

            status = "Connected"
            print(f"Successfully connected to {address} as {device_type}.")
        except Exception as e:
            print(f"Failed to connect to {address}: {e}")

        self.ui_queue.put({"type": "connection_status", "device_type": device_type, "status": status, "address": address})

    def _initialize_service(self, device_type, client):
        """Initializes and returns the correct pycycling service object."""
        if device_type == "hrm":
            service = HeartRateService(client)
            service.set_hr_measurement_handler(self._handle_hr_update)
            return service
        elif device_type == "csc":
            service = CyclingSpeedCadenceService(client)
            service.set_csc_measurement_handler(self._handle_csc_update)
            return service
        elif device_type == "power":
            service = CyclingPowerService(client)
            service.set_cycling_power_measurement_handler(self._handle_power_update)
            return service
        elif device_type == "ftms":
            return FitnessMachineService(client)
        elif device_type == "tacx": # For ANT+ FE-C over BLE
            return TacxTrainerControl(client)
        return None

    async def disconnect(self):
        """Disconnects all connected clients."""
        for client in self.clients.values():
            if client.is_connected:
                await client.disconnect()
        self.clients.clear()
        self.services.clear()
        print("All devices disconnected.")

    async def set_target_power(self, power: int):
        """Sets the target power on the connected trainer."""
        trainer_service = self.services.get("ftms") or self.services.get("tacx")
        if trainer_service:
            try:
                await trainer_service.set_target_power(power)
                print(f"Set target power to {power}W")
            except Exception as e:
                print(f"Failed to set target power: {e}")
        else:
            print("No trainer connected.")

    # --- Notification Handlers ---
    def _handle_hr_update(self, measurement):
        self.ui_queue.put({"type": "hr_update", "value": measurement.bpm})

    def _handle_csc_update(self, measurement):
        self.ui_queue.put({"type": "csc_update", "crank_rev": measurement.cumulative_crank_revolutions})

    def _handle_power_update(self, measurement):
        self.ui_queue.put({"type": "power_update", "value": measurement.instantaneous_power})

    def _handle_tacx_update(self, data):
        """Handles the combined data page from a Tacx trainer."""
        self.ui_queue.put({"type": "power_update", "value": data.instantaneous_power})
        self.ui_queue.put({"type": "csc_update", "crank_rev": data.instantaneous_cadence})
