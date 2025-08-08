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
        self.role_uuids = {
            "hrm": "0000180d-0000-1000-8000-00805f9b34fb",
            "csc": "00001816-0000-1000-8000-00805f9b34fb",
            "power": "00001818-0000-1000-8000-00805f9b34fb",
            "ftms": "00001826-0000-1000-8000-00805f9b34fb",
            "tacx": "6e40fec1-b5a3-f393-e0a9-e50e24dcca9e", # Tacx FE-C over BLE
        }

    async def scan(self, timeout=5.0):
        """Scans for BLE devices and informs the UI with a filtered list."""
        print(f"Scanning for devices for {timeout} seconds...")

        devices_found = {}
        def detection_callback(device, advertisement_data):
            # Store all unique devices found
            if device.address not in devices_found:
                devices_found[device.address] = (device, advertisement_data)

        scanner = BleakScanner(detection_callback=detection_callback)
        await scanner.start()
        await asyncio.sleep(timeout)
        await scanner.stop()

        # Filter devices by role
        devices_by_role = {role: [] for role in self.role_uuids.keys()}
        all_devices = []

        for device, ad_data in devices_found.values():
            all_devices.append(device)
            for role, uuid in self.role_uuids.items():
                if uuid.lower() in [s.lower() for s in ad_data.service_uuids]:
                    devices_by_role[role].append(device)

        self.discovered_devices = all_devices
        self.ui_queue.put({"type": "scan_complete", "devices_by_role": devices_by_role})

    async def connect_all_devices(self, devices_to_connect: List[tuple]):
        """Connects to a list of devices sequentially."""
        self.ui_queue.put({"type": "status_update", "message": "Connecting to devices..."})
        for device_type, address in devices_to_connect:
            await self.connect_to_device(device_type, address)
        self.ui_queue.put({"type": "status_update", "message": "Device connection process complete."})

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
                await self._enable_service_notifications(device_type, service)

            status = "Connected"
            print(f"Successfully connected to {address} as {device_type}.")
        except Exception as e:
            print(f"Failed to connect to {address}: {e}")
            if device_type in self.clients:
                del self.clients[device_type]

        self.ui_queue.put({"type": "connection_status", "device_type": device_type, "status": status, "address": address})

    def _initialize_service(self, device_type, client):
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
            service = FitnessMachineService(client)
            service.set_indoor_bike_data_handler(self._handle_ftms_update)
            return service
        elif device_type == "tacx":
            service = TacxTrainerControl(client)
            service.set_specific_trainer_data_page_handler(self._handle_tacx_update)
            return service
        return None

    async def _enable_service_notifications(self, device_type, service):
        print(f"Enabling notifications for {device_type}...")
        if device_type == "hrm": await service.enable_hr_measurement_notifications()
        elif device_type == "csc": await service.enable_csc_measurement_notifications()
        elif device_type == "power": await service.enable_cycling_power_measurement_notifications()
        elif device_type == "ftms": await service.enable_indoor_bike_data_notify()
        elif device_type == "tacx": await service.enable_fec_notifications()

    async def disconnect(self):
        for client in self.clients.values():
            if client.is_connected: await client.disconnect()
        self.clients.clear()
        self.services.clear()
        print("All devices disconnected.")

    async def set_target_power(self, power: int):
        trainer_service = self.services.get("ftms") or self.services.get("tacx")
        if trainer_service:
            try:
                if isinstance(trainer_service, FitnessMachineService):
                    await trainer_service.request_control()
                await trainer_service.set_target_power(power)
                print(f"Set target power to {power}W")
            except Exception as e:
                print(f"Failed to set target power: {e}")
        else:
            print("No trainer connected.")

    def _handle_hr_update(self, m): self.ui_queue.put({"type": "hr_update", "value": m.bpm})
    def _handle_csc_update(self, m): self.ui_queue.put({"type": "csc_update", "crank_rev": m.cumulative_crank_revolutions})
    def _handle_power_update(self, m): self.ui_queue.put({"type": "power_update", "value": m.instantaneous_power})
    def _handle_ftms_update(self, d):
        self.ui_queue.put({"type": "power_update", "value": d.instantaneous_power})
        self.ui_queue.put({"type": "csc_update", "crank_rev": d.instantaneous_cadence})
    def _handle_tacx_update(self, d):
        self.ui_queue.put({"type": "power_update", "value": d.instantaneous_power})
        self.ui_queue.put({"type": "csc_update", "crank_rev": d.instantaneous_cadence})
