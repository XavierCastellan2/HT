import asyncio
import queue
from typing import List, Tuple, Optional
from src.cycling_manager import CyclingManager

class WorkoutManager:
    """Manages the execution of a workout session."""

    def __init__(self, cycling_manager: CyclingManager, ui_queue: queue.Queue):
        """
        Initializes the WorkoutManager.

        Args:
            cycling_manager: An instance of the CyclingManager.
            ui_queue: A queue to send updates to the UI thread.
        """
        self.cycling_manager = cycling_manager
        self.ui_queue = ui_queue
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
            self.ui_queue.put({"type": "status_update", "message": "Error: No workout loaded."})
            return

        if self._is_running:
            print("Workout is already running.")
            return

        self._is_running = True
        self.ui_queue.put({"type": "status_update", "message": "Workout started."})
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
                self.ui_queue.put({"type": "workout_update", "target_power": power, "progress": progress})

                await self.cycling_manager.set_target_power(power)
        except asyncio.CancelledError:
            print("Workout run cancelled.")
        finally:
            self._is_running = False
            if asyncio.current_task() and not asyncio.current_task().cancelled():
                 self.ui_queue.put({"type": "workout_finished", "message": "Workout finished!"})
            print("Workout loop finished.")

    def stop_workout(self):
        """Requests the currently running workout to stop."""
        if self._is_running:
            self._is_running = False
            print("Workout stop requested.")
            self.ui_queue.put({"type": "status_update", "message": "Workout stopped."})
