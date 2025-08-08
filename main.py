import asyncio
import threading
import uvicorn
import webview
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.cycling_manager import CyclingManager
from src.erg_parser import parse_erg
from src.workout_manager import WorkoutManager
from src.websocket_manager import WebSocketManager

# --- Global Objects ---
app = FastAPI()
ws_manager = WebSocketManager()
# Note: The asyncio loop will be running in the uvicorn thread.
# We need to be careful about how we interact with it from other threads.
# For now, our managers are created and used within the same async context.
cycling_manager = CyclingManager(ws_manager)
workout_manager = WorkoutManager(cycling_manager, ws_manager)

# --- FastAPI App Setup ---
app.mount("/web", StaticFiles(directory="web"), name="web")

@app.get("/")
async def get_root():
    return FileResponse('web/index.html')

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            command = data.get("command")

            if command == "scan":
                asyncio.create_task(cycling_manager.scan())
            elif command == "connect":
                devices = data.get("devices", [])
                asyncio.create_task(cycling_manager.connect_all_devices(devices))
            elif command == "load_erg":
                workout_data = parse_erg(data.get("filepath"))
                if workout_data:
                    workout_manager.load_workout(workout_data)
                    await ws_manager.broadcast({"type": "status_update", "message": f"Loaded workout: {data.get('filepath')}"})
            elif command == "start_workout":
                 asyncio.create_task(workout_manager.run_workout())
            elif command == "disconnect":
                asyncio.create_task(cycling_manager.disconnect())

    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
        print("Client disconnected from WebSocket.")

# --- pywebview and Server Threading ---
def run_server():
    """Runs the Uvicorn server."""
    uvicorn.run(app, host="127.0.0.1", port=8000)

if __name__ == "__main__":
    # Run the FastAPI server in a separate thread
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    # Create and start the pywebview window
    webview.create_window(
        "BLE Training App",
        "http://127.0.0.1:8000",
        width=1200,
        height=800,
        resizable=True
    )
    webview.start()

    print("Main window closed. Application shutting down.")
