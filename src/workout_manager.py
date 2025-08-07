import asyncio
import queue
from typing import List, Tuple, Optional
from src.trainer import Trainer

class WorkoutManager:
    """Manages the execution of a workout session."""

    def __init__(self, trainer: Optional[Trainer], ui_queue: queue.Queue):
        """
        Initializes the WorkoutManager.

        Args:
            trainer: An instance of the Trainer class to control the fitness machine.
            ui_queue: A queue to send updates to the UI thread.
        """
        self.trainer = trainer
        self.ui_queue = ui_queue
        self.workout: List[Tuple[int, int]] = []
        self._is_running = False
        self._workout_task: Optional[asyncio.Task] = None

    def load_workout(self, workout_data: List[Tuple[int, int]]):
        """Loads workout data into the manager."""
        self.workout = workout_data
        print(f"Workout loaded with {len(self.workout)} steps.")

    def start_workout(self):
        """Starts the workout execution in a new asyncio task."""
        if not self.workout:
            print("Cannot start: No workout loaded.")
            self.ui_queue.put({"type": "status_update", "message": "Error: No workout loaded."})
            return

        if self._is_running:
            print("Workout is already running.")
            return

        self._is_running = True
        self._workout_task = asyncio.create_task(self._run_workout_loop())
        self.ui_queue.put({"type": "status_update", "message": "Workout started."})

    async def _run_workout_loop(self):
        """The main async loop for the workout session."""
        print("Starting workout loop...")
        start_time = asyncio.get_event_loop().time()
        total_duration = self.workout[-1][0] if self.workout else 1

        for i, (time_offset, power) in enumerate(self.workout):
            if not self._is_running:
                print("Workout loop cancelled.")
                break

            # Wait until it's time for the next step
            current_time = asyncio.get_event_loop().time()
            time_to_wait = (start_time + time_offset) - current_time
            if time_to_wait > 0:
                await asyncio.sleep(time_to_wait)

            # Update UI and trainer
            progress = (time_offset / total_duration) * 100
            self.ui_queue.put({"type": "workout_update", "target_power": power, "progress": progress})

            if self.trainer:
                await self.trainer.set_target_power(power)
            else:
                print(f"Target Power: {power}W (Trainer not connected)")

        self._is_running = False
        self.ui_queue.put({"type": "workout_finished", "message": "Workout finished!"})
        print("Workout loop finished.")

    def stop_workout(self):
        """Stops the currently running workout."""
        if self._is_running and self._workout_task:
            self._is_running = False
            self._workout_task.cancel()
            print("Workout stop requested.")
            self.ui_queue.put({"type": "status_update", "message": "Workout stopped."})
