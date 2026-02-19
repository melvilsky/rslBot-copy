
from pynput import mouse
import pyautogui
import threading
import time
from helpers.common import log

class Recorder:
    def __init__(self):
        self.is_recording = False
        self.events = []
        self._listener = None
        self.start_time = None

    def start(self):
        if self.is_recording:
            return "Already recording"
        
        self.is_recording = True
        self.events = []
        self.start_time = time.time()
        
        # Start listener in a non-blocking way
        self._listener = mouse.Listener(on_click=self._on_click)
        self._listener.start()
        
        log("Recorder started")
        return "Recording started. Click around! Send /record_off to stop."

    def stop(self):
        if not self.is_recording:
            return "Not recording"
            
        self.is_recording = False
        if self._listener:
            self._listener.stop()
            self._listener = None
            
        log(f"Recorder stopped. Captured {len(self.events)} events.")
        return self._format_events()

    def _on_click(self, x, y, button, pressed):
        if not self.is_recording:
            return False # Stop listener
            
        if pressed and button == mouse.Button.left:
            try:
                # Get pixel color
                # Note: pyautogui.pixel might be slow, so we do it cautiously
                r, g, b = pyautogui.pixel(x, y)
                color = (r, g, b)
                
                event = {
                    'x': x,
                    'y': y,
                    'color': color,
                    'time': time.time() - self.start_time,
                    'button': 'left'
                }
                self.events.append(event)
                log(f"Recorded click: {event}")
            except Exception as e:
                log(f"Error recording click at {x}, {y}: {e}")

    def _format_events(self):
        if not self.events:
            return "No events recorded."
            
        result = "Recorded Events:\n"
        for i, event in enumerate(self.events):
            result += f"{i+1}. Click at ({event['x']}, {event['y']}) - Color: {event['color']} - Time: {event['time']:.2f}s\n"
        
        return result
