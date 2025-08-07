import struct
from bleak import BleakClient
from typing import Optional

# From the FTMS specification, the Fitness Machine Control Point UUID
FTMS_CONTROL_POINT_CHAR_UUID = "00002ad9-0000-1000-8000-00805f9b34fb"
# The op-code for setting target power
SET_TARGET_POWER_OP_CODE = 0x05

class Trainer:
    """A class to control a fitness machine that supports FTMS."""

    def __init__(self, client: BleakClient):
        """
        Initializes the Trainer controller.

        Args:
            client: A connected BleakClient for the FTMS device.
        """
        self.client = client

    async def set_target_power(self, power: int):
        """
        Sets the target power on the fitness machine.

        This sends a 'Set Target Power' command to the FTMS control point.

        Assumption: The trainer correctly implements the standard FTMS service
        and will respond to the 'Set Target Power' op-code.

        Args:
            power: The target power in watts.
        """
        if not self.client or not self.client.is_connected:
            print("Error: Trainer is not connected.")
            return

        try:
            # The payload for setting target power is the op-code followed by
            # the power value as a 2-byte unsigned integer (little-endian).
            payload = bytearray([SET_TARGET_POWER_OP_CODE]) + struct.pack("<H", int(power))

            print(f"Sending 'Set Target Power' command: {power}W")
            await self.client.write_gatt_char(FTMS_CONTROL_POINT_CHAR_UUID, payload)
            print("Command sent successfully.")

        except Exception as e:
            print(f"Failed to set target power: {e}")
