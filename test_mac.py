"""
Mac Testing Script for NaviGlass
Mocks Raspberry Pi hardware dependencies to run the application on Mac.
"""

import sys
import unittest.mock as mock
import numpy as np
import cv2
import time
import threading
import os

# ==========================================
# MOCK HARDWARE DEPENDENCIES
# ==========================================

# Mock RPi.GPIO
class MockGPIO:
    BOARD = 'BOARD'
    OUT = 'OUT'
    IN = 'IN'
    HIGH = 1
    LOW = 0
    
    @staticmethod
    def setmode(mode):
        print(f"[MockGPIO] Mode set to {mode}")
        
    @staticmethod
    def setup(pin, mode):
        print(f"[MockGPIO] Pin {pin} setup as {mode}")
        
    @staticmethod
    def output(pin, state):
        # print(f"[MockGPIO] Pin {pin} output {state}")
        pass
        
    @staticmethod
    def input(pin):
        # Simulate echo pulse for distance measurement
        # Return 0 then 1 then 0 to simulate a pulse
        return int((time.time() * 100) % 2 > 1)
        
    @staticmethod
    def cleanup():
        print("[MockGPIO] Cleanup")

# Mock Picamera2
class MockPicamera2:
    def __init__(self):
        print("[MockPicamera2] Initialized")
        
    def create_preview_configuration(self, main=None):
        return {}
        
    def configure(self, config):
        pass
        
    def start(self):
        print("[MockPicamera2] Camera started")
        
    def stop(self):
        print("[MockPicamera2] Camera stopped")
        
    def capture_array(self):
        # Return a black image with some noise or a test pattern
        # 640x480 RGB image
        img = np.zeros((480, 640, 3), dtype=np.uint8)
        # Add some text to simulate an object
        cv2.putText(img, "Mock Camera Feed", (50, 240), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        return img

# Mock Face Recognition (if not installed)
class MockFaceRecognition:
    @staticmethod
    def load_image_file(file):
        return np.zeros((100, 100, 3), dtype=np.uint8)
        
    @staticmethod
    def face_encodings(image):
        # Return a fake encoding (128-d vector)
        return [np.random.rand(128)]
        
    @staticmethod
    def face_distance(known_encodings, face_encoding):
        return [0.5] * len(known_encodings)

# Apply mocks to sys.modules
sys.modules['RPi'] = mock.MagicMock()
sys.modules['RPi.GPIO'] = MockGPIO
sys.modules['picamera2'] = mock.MagicMock()
sys.modules['picamera2'].Picamera2 = MockPicamera2

# Try to import face_recognition, if fails, mock it
try:
    import face_recognition
except ImportError:
    print("face_recognition not found, using mock")
    sys.modules['face_recognition'] = MockFaceRecognition
    sys.modules['dlib'] = mock.MagicMock()

# ==========================================
# RUN APPLICATION
# ==========================================

def run_test():
    print("=" * 60)
    print("NAVI GLASS - MAC TEST MODE")
    print("=" * 60)
    print("This script runs objectDetection.py with mocked hardware.")
    print("Press Ctrl+C to stop.")
    print("-" * 60)
    
    # Create a dummy .env if it doesn't exist
    if not os.path.exists('.env'):
        with open('.env', 'w') as f:
            f.write("GEMINI_API_KEY=test_key\n")
            f.write("TTS_RATE=150\n")
            f.write("TTS_VOLUME=1.0\n")
    
    # Import the main module
    # We need to patch the YOLO model to not actually load weights if they don't exist
    # or just let it fail if model missing? 
    # Let's mock YOLO too if model file missing
    
    if not os.path.exists("yolo11n_ncnn_model"):
        print("YOLO model not found, mocking YOLO...")
        
        class MockResult:
            def __init__(self):
                self.boxes = mock.MagicMock()
                self.boxes.cls = [mock.MagicMock()]
                self.boxes.cls[0].item.return_value = 0 # Person
                self.boxes.conf = [mock.MagicMock()]
                self.boxes.conf[0].item.return_value = 0.85
                self.names = {0: 'person', 1: 'bicycle'}
                
            def plot(self):
                return np.zeros((480, 640, 3), dtype=np.uint8)
        
        class MockYOLO:
            def __init__(self, model_path):
                print(f"[MockYOLO] Loaded model: {model_path}")
                
            def __call__(self, source, **kwargs):
                return [MockResult()]
                
        sys.modules['ultralytics'] = mock.MagicMock()
        sys.modules['ultralytics'].YOLO = MockYOLO
    
    # Now import main
    import objectDetection
    
    # Run main
    try:
        objectDetection.app.run(host='0.0.0.0', port=5000)
    except KeyboardInterrupt:
        print("\nTest stopped by user")
    except Exception as e:
        print(f"\nError running test: {e}")

if __name__ == "__main__":
    run_test()
