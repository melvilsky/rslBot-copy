
from pynput import mouse
import pyautogui
import threading
import time
import json
from pathlib import Path
from helpers.common import log

class Recorder:
    CROP_SIZE = 120
    RGB_SAMPLE_RADIUS = 2

    def __init__(self):
        self.is_recording = False
        self.events = []
        self._listener = None
        self.start_time = None
        self.recording_name = None
        self.recording_path = None
        self.assets_dir = None

    def start(self):
        if self.is_recording:
            return "Already recording"
        
        self.is_recording = True
        self.events = []
        self.start_time = time.time()
        self.recording_name = time.strftime("recording_%Y%m%d_%H%M%S")
        recordings_dir = Path("recorder") / "recordings"
        self.assets_dir = recordings_dir / f"{self.recording_name}_assets"
        self.recording_path = recordings_dir / f"{self.recording_name}.json"
        self.assets_dir.mkdir(parents=True, exist_ok=True)
        
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
        self._save_events()
        return self._format_events()

    def _on_click(self, x, y, button, pressed):
        if not self.is_recording:
            return False # Stop listener
            
        if pressed and button == mouse.Button.left:
            try:
                x = int(round(x))
                y = int(round(y))
                screenshot = pyautogui.screenshot()
                rgb = self._read_rgb(screenshot, x, y)
                crop_path, crop_region = self._save_click_crop(screenshot, x, y)
                avg_rgb_5x5 = self._avg_rgb(screenshot, x, y, radius=self.RGB_SAMPLE_RADIUS)
                
                event = {
                    'x': x,
                    'y': y,
                    'rgb': rgb,
                    'avg_rgb_5x5': avg_rgb_5x5,
                    'crop': crop_path,
                    'crop_region': crop_region,
                    # Kept for compatibility with existing output/users.
                    'color': tuple(rgb),
                    'time': time.time() - self.start_time,
                    'button': 'left'
                }
                self.events.append(event)
                log(f"Recorded click: {event}")
            except Exception as e:
                log(f"Error recording click at {x}, {y}: {e}")

    def _read_rgb(self, screenshot, x, y):
        width, height = screenshot.size
        if x < 0 or y < 0 or x >= width or y >= height:
            raise ValueError(f"Click is outside screenshot bounds: ({x}, {y}) not in {width}x{height}")
        pixel = screenshot.getpixel((x, y))
        return [int(pixel[0]), int(pixel[1]), int(pixel[2])]

    def _avg_rgb(self, screenshot, x, y, radius=2):
        width, height = screenshot.size
        left = max(0, x - radius)
        top = max(0, y - radius)
        right = min(width, x + radius + 1)
        bottom = min(height, y + radius + 1)

        total = [0, 0, 0]
        count = 0
        for px in range(left, right):
            for py in range(top, bottom):
                r, g, b = screenshot.getpixel((px, py))[:3]
                total[0] += r
                total[1] += g
                total[2] += b
                count += 1

        if not count:
            return None

        return [round(total[0] / count), round(total[1] / count), round(total[2] / count)]

    def _save_click_crop(self, screenshot, x, y):
        if self.assets_dir is None:
            return None, None

        width, height = screenshot.size
        half = self.CROP_SIZE // 2
        left = max(0, x - half)
        top = max(0, y - half)
        right = min(width, x + half)
        bottom = min(height, y + half)

        crop = screenshot.crop((left, top, right, bottom))
        file_name = f"click_{len(self.events) + 1:04d}_crop.png"
        crop_path = self.assets_dir / file_name
        crop.save(crop_path)

        crop_region = [left, top, right - left, bottom - top]
        return crop_path.as_posix(), crop_region

    def _save_events(self):
        if self.recording_path is None:
            return

        try:
            self.recording_path.parent.mkdir(parents=True, exist_ok=True)
            with self.recording_path.open("w", encoding="utf-8") as jsonfile:
                json.dump(self.events, jsonfile, ensure_ascii=False, indent=2)
            log(f"Recorder events saved: {self.recording_path}")
        except Exception as e:
            log(f"Error saving recorder events: {e}")

    def _format_events(self):
        if not self.events:
            return "No events recorded."
            
        result = "Recorded Events:\n"
        for i, event in enumerate(self.events):
            result += (
                f"{i+1}. Click at ({event['x']}, {event['y']})"
                f" - RGB: {event['rgb']}"
                f" - AVG 5x5: {event['avg_rgb_5x5']}"
                f" - Crop: {event['crop']}"
                f" - Time: {event['time']:.2f}s\n"
            )

        if self.recording_path is not None:
            result += f"\nSaved JSON: {self.recording_path.as_posix()}"
        
        return result
