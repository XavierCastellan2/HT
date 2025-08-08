import asyncio
from typing import List, Tuple, Optional
from src.cycling_manager import CyclingManager
from src.websocket_manager import WebSocketManager

class WorkoutManager:
    """Manages the execution of a workout session."""

    def __init__(self, cycling_manager: CyclingManager, ws_manager: WebSocketManager):
        """
        Initializes the WorkoutManager.

        Args:
            cycling_manager: An instance of the CyclingManager.
            ws_manager: An instance of the WebSocketManager to broadcast updates.
        """
        self.cycling_manager = cycling_manager
        self.ws_manager = ws_manager
        self.workout: List[Tuple[int, int]] = []
        self._is_running = False

    def load_workout(self, workout_data: List[Tuple[int, int]]):
        """Loads workout data into the manager."""
        self.workout = workout_data
        print(f"Workout loaded with {len(self.workout)} steps.")

    async def run_workout(self):
        """The main async coroutine for the workout session."""
        if not self.workout:
            print("Cannot start: No workout loaded.")
            await self.ws_manager.broadcast({"type": "status_update", "message": "Error: No workout loaded."})
            return

        if self._is_running:
            print("Workout is already running.")
            return

        self._is_running = True
        await self.ws_manager.broadcast({"type": "status_update", "message": "Workout started."})
        print("Starting workout loop...")
        start_time = asyncio.get_event_loop().time()
        total_duration = self.workout[-1][0] if self.workout else 1

        try:
            for i, (time_offset, power) in enumerate(self.workout):
                if not self._is_running:
                    print("Workout loop cancelled.")
                    break

                current_time = asyncio.get_event_loop().time()
                time_to_wait = (start_time + time_offset) - current_time
                if time_to_wait > 0:
                    await asyncio.sleep(time_to_wait)

                progress = (time_offset / total_duration) * 100
                await self.ws_manager.broadcast({"type": "workout_update", "target_power": power, "progress": progress})

                await self.cycling_manager.set_target_power(power)
        except asyncio.CancelledError:
            print("Workout run cancelled.")
        finally:
            self._is_running = False
            if asyncio.current_task() and not asyncio.current_task().cancelled():
                 await self.ws_manager.broadcast({"type": "workout_finished", "message": "Workout finished!"})
            print("Workout loop finished.")

    def stop_workout(self):
        """Requests the currently running workout to stop."""
        if self._is_running:
            self._is_running = False
            print("Workout stop requested.")
            asyncio.create_task(self.ws_manager.broadcast({"type": "status_update", "message": "Workout stopped."}))
