import time
import cv2
from picamera2 import Picamera2
from flask import Flask, Response, jsonify # Used for web streaming
from ultralytics import YOLO
import threading
import google.generativeai as genai
import RPi.GPIO as GPIO
import os
import signal
import sys
from dotenv import load_dotenv
import face_recognition
import numpy as np

# Import our custom modules
from bluetooth_audio import BluetoothAudioManager
from tts_engine import TTSEngine
from face_database import FaceDatabase



_latest_distances = []
_distance_lock = threading.Lock()
_latest_recognized_faces = []
_recognized_faces_lock = threading.Lock()
_last_face_check_time = 0
SENSOR_TRIG_PIN1 = 13
SENSOR_ECHO_PIN1 = 11
SENSOR_TRIG_PIN2 = 16
SENSOR_ECHO_PIN2 = 18


app = Flask(__name__)  # Initialize Flask app


picam = Picamera2()  # Initialize the camera
print("Camera initialized.")
config = picam.create_preview_configuration(main={'size': (640, 480), 'format': 'RGB888'})
picam.configure(config)
picam.start()  # Start the camera

model = YOLO("yolo11n_ncnn_model")  # Load the model
print("YOLO11n loaded.")
_latest_labels = []
_latest_labels_lock = threading.Lock()


# Load environment variables from .env file
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    GEMINI_ENABLED = True
    print("Gemini API key found, enabling Gemini narration.")
else:
    GEMINI_ENABLED = False
    print("GEMINI_API_KEY not set. Narration will be basic.")

# Initialize TTS Engine
tts_engine = TTSEngine(rate=int(os.getenv("TTS_RATE", "150")), 
                       volume=float(os.getenv("TTS_VOLUME", "1.0")))

# Initialize Bluetooth Audio Manager
bluetooth_mac = os.getenv("BLUETOOTH_DEVICE_MAC")
bluetooth_manager = BluetoothAudioManager(device_mac=bluetooth_mac)

# Initialize Face Recognition Database
face_db = FaceDatabase()
FACE_RECOGNITION_ENABLED = face_db.count() > 0
FACE_RECOGNITION_TOLERANCE = float(os.getenv("FACE_RECOGNITION_TOLERANCE", "0.6"))
FACE_RECOGNITION_INTERVAL = int(os.getenv("FACE_RECOGNITION_INTERVAL", "5"))
if FACE_RECOGNITION_ENABLED:
    print(f"Face recognition enabled with {face_db.count()} known face(s)")
else:
    print("Face recognition disabled (no faces in database)")




def setup_sensor(): # Pin set up
    GPIO.setmode(GPIO.BOARD)
    GPIO.setup(SENSOR_TRIG_PIN1, GPIO.OUT)
    GPIO.output(SENSOR_TRIG_PIN1, GPIO.LOW)
    GPIO.setup(SENSOR_ECHO_PIN1, GPIO.IN)
    GPIO.setup(SENSOR_TRIG_PIN2, GPIO.OUT)
    GPIO.output(SENSOR_TRIG_PIN2, GPIO.LOW)
    GPIO.setup(SENSOR_ECHO_PIN2, GPIO.IN)
    print("GPIO setup complete.")


def measure_distance(TRIG, ECHO):
    GPIO.output(TRIG, GPIO.HIGH) # Send a 10us pulse to trigger the sensor
    time.sleep(0.00001)
    GPIO.output(TRIG, GPIO.LOW)

    MAX_TIMEOUT = 0.1 # 100 ms timeout
    t_timeout = time.time()

    pulse_start = time.time()  # Initialize before loop
    while GPIO.input(ECHO) == 0: # Wait for the echo start
        if time.time() - t_timeout > MAX_TIMEOUT:
            return 999  # Timeout, return out of range
        pulse_start = time.time()

    pulse_end = time.time()  # Initialize before loop
    t_timeout = time.time()
    while GPIO.input(ECHO) == 1:
        if time.time() - t_timeout > MAX_TIMEOUT:
            return 999  # Timeout, return out of range
        pulse_end = time.time()

    pulse_duration = pulse_end - pulse_start # Calculate pulse duration and distance
    distance_cm = pulse_duration * 17150

    if distance_cm < 2 or distance_cm > 400:
        return 999  # Out of range
    
    return distance_cm


def set__latest_distances(distances): # Safely set the distances
    global _latest_distances
    with _distance_lock:
        _latest_distances = list(distances) if distances is not None else []


def get__latest_distances(): # Safely get the distances
    with _distance_lock:
        return list(_latest_distances)


def set_latest_recognized_faces(faces): # Safely set recognized faces
    global _latest_recognized_faces
    with _recognized_faces_lock:
        _latest_recognized_faces = list(faces) if faces is not None else []


def get_latest_recognized_faces(): # Safely get recognized faces
    with _recognized_faces_lock:
        return list(_latest_recognized_faces)


def generate_distance(TRIG, ECHO): # Make 5 distance measurements
    t=0
    distances = []
    while t<5:
        distance_cm = measure_distance(TRIG, ECHO)
        distances.append(distance_cm)
        t+=1
        time.sleep(0.02)
    set__latest_distances(distances)
    avg_distance = sum(distances)/len(distances) # Return the average of the 5 measurements
    print("Distance measured: " + str(avg_distance)) # Print distance for debugging
    return avg_distance



def set_latest_labels(labels): # Safely set the labels
    global _latest_labels
    with _latest_labels_lock:
        _latest_labels = list(labels) if labels is not None else []


def get_latest_labels(): # Safely get the labels
    with _latest_labels_lock:
        return list(_latest_labels)
    

def labels_from_result(result, conf_min: float = 0.70):
    out = []
    if getattr(result, "boxes", None) is None or len(result.boxes) == 0:
        return out
    names = result.names
    for cls_tensor, conf_tensor in zip(result.boxes.cls, result.boxes.conf):
        conf = float(conf_tensor.item())
        if conf >= conf_min:
            cls_id = int(cls_tensor.item())
            label = names.get(cls_id, str(cls_id))
            out.append({"label": label, "confidence": conf})
    return out


def generate_frames():
    global _last_face_check_time
    
    while True:
        frame = picam.capture_array() # Capture frame from Picamera2
        t0 = time.perf_counter() # Start time for fps measurement

        results = model(frame, verbose=False, classes=[0, 1, 2, 3, 5, 7, 9, 10, 11, 13]) # Run the YOLO model on a certain amount of classes
        r = results[0] # Extract the Results object from the list
        labels = labels_from_result(r, conf_min=0.70) # Get labels from the Results object with confidence filtering
        set_latest_labels(labels) # Set the thread-safe variable
        
        # Face recognition (run every FACE_RECOGNITION_INTERVAL seconds)
        current_time = time.time()
        if FACE_RECOGNITION_ENABLED and (current_time - _last_face_check_time) >= FACE_RECOGNITION_INTERVAL:
            _last_face_check_time = current_time
            try:
                # Convert BGR to RGB for face_recognition
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                recognized = face_db.recognize_faces(rgb_frame, tolerance=FACE_RECOGNITION_TOLERANCE)
                set_latest_recognized_faces(recognized)
                if recognized:
                    names = [name for name, _ in recognized]
                    print(f"Recognized faces: {', '.join(names)}")
            except Exception as e:
                print(f"Error in face recognition: {e}")

        t1 = time.perf_counter() # End time for fps measurement
        elpased_ms = (t1 - t0) * 1000
        fps = 1000 / elpased_ms
        print(f"Inference time: {elpased_ms:.2f} ms, FPS: {fps:.2f}") # Print time for observation

        annotated_frame = r.plot() # Draw bounding boxes
        ret, buffer = cv2.imencode('.jpg', annotated_frame) # Turn the frame into JPEG and send to stream through Flask
        if not ret:
            continue
        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        time.sleep(0.01) # Rest the CPU


def select_highest_confidence_label(labels): # Select the label with the highest confidence
    if not labels:
        return None, "No objects detected"
    best = max(labels, key=lambda x: x.get("confidence", 0.0))
    prompt_str = f"Detected {best['label'].upper()} ({best['confidence']:.2f} confidence)"
    return best, prompt_str



def narrate_sentences_periodically(sentence_from_llm_func, interval_seconds: float = 5.0): # Narrate sentences with Gemini LLM call
    
    if not callable(sentence_from_llm_func): # Make sure that sentence_from_llm_func is a function
        raise ValueError("sentence_from_llm_func must be callable")

    def _narrate_loop(): # Narration loop
        nonlocal sentence_from_llm_func  # Uses the variable define in the outer function
        
        if GEMINI_ENABLED: # If Gemini is reachable, override the sentence producer function

            gemini_model = genai.GenerativeModel('gemini-2.5-flash')

            def _gemini_sentence_from_latest():
                # Check for recognized faces first
                recognized_faces = get_latest_recognized_faces()
                if recognized_faces:
                    names = [name for name, _ in recognized_faces]
                    if len(names) == 1:
                        return f"Hello {names[0]}"
                    else:
                        return f"Hello {', '.join(names[:-1])} and {names[-1]}"
                
                # Otherwise, do object detection narration
                best, _ = select_highest_confidence_label(get_latest_labels())
                
                if best and best.get('confidence') >= 0.70:
                    distance_cm1 = generate_distance(SENSOR_TRIG_PIN1, SENSOR_ECHO_PIN1) 
                    distance_cm2 = generate_distance(SENSOR_TRIG_PIN2, SENSOR_ECHO_PIN2)
                    distance_cm = min(distance_cm1, distance_cm2)
                    # Activate the distance sensor if an object is detected with >=.70 confidence
        
                    distance_str = f"The distance sensor measures {distance_cm:.1f} cm." if distance_cm != 999 else "The distance sensor reading is out of range. "

                    user_prompt = (
                         f"Object: {best['label']}. {distance_str} "
                         f"Narrate in present tense. Max 10 words."
                        )

                    t0 = time.perf_counter() # Start timer for API call duration measurement

                    try:
                        resp = gemini_model.generate_content(user_prompt)
                        t1 = time.perf_counter() # End timer for API call
                        api_latency = (t1 - t0)
                        print("API latency: " + str(api_latency))

                        text = resp.text.strip()
                        return text if text else f"Detected {best['label'].upper()} ({best['confidence']:.2f} confidence)"
                    
                    except Exception as e:
                        print(f"Gemini API call failed: {e}")
                        return f"Detected {best['label'].upper()} ({best['confidence']:.2f} confidence)"
                    
                return None # Do nothing if the confidence is too low
        
            sentence_from_llm_func = _gemini_sentence_from_latest # Override the default function with the Gemini one

        try: # Main loop
            while True: # Continualy try narrating by searching for confidence >= 0.70
                sentence = None
                try:
                    sentence = sentence_from_llm_func()
                except Exception as e:
                    print(f"Error calling sentence_from_llm_func: {e}")

                if sentence:
                    print(f"[Narration]: {sentence}")
                    # Speak using TTS engine
                    tts_engine.speak(sentence)

                    time.sleep(interval_seconds) # Wait before next narration

        except KeyboardInterrupt:
            print("Narration loop interrupted by user,")

    return _narrate_loop


def sentence_from_llm_default(): # Default sentence producer (fallback if Gemini fails or is disabled)
    labels = get_latest_labels()
    best, prompt = select_highest_confidence_label(labels)
    if best:
        return prompt
    return None



@app.route('/') # Serves the webpage
def index():
    return """<html><body>
                <h1>YOLO11n Live Stream</h1>
                <img src='/video_feed'>
              </body></html>"""


@app.route('/video_feed') # Generate the frames and feed it to the stream
def video_feed():
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')




def cleanup_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    print("\n\nShutdown signal received, cleaning up...")
    
    # Stop TTS engine
    if tts_engine:
        tts_engine.stop()
    
    # Disconnect Bluetooth
    if bluetooth_manager and bluetooth_manager.is_connected():
        bluetooth_manager.disconnect()
    
    # Cleanup GPIO
    GPIO.cleanup()
    print("Cleanup complete")
    sys.exit(0)


if __name__ == '__main__': # Main function
    # Setup signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, cleanup_handler)
    signal.signal(signal.SIGTERM, cleanup_handler)
    
    try:
        setup_sensor()
    except Exception as e:
        print(f"Failed to setup sensor: {e}")
    
    # Connect to Bluetooth audio device
    if bluetooth_mac:
        print(f"Attempting to connect to Bluetooth device: {bluetooth_mac}")
        if bluetooth_manager.connect_audio():
            print("✓ Bluetooth audio connected")
        else:
            print("✗ Failed to connect to Bluetooth, audio will use default output")
    else:
        print("No Bluetooth MAC address configured, using default audio output")
    
    # Start TTS engine
    tts_engine.start()
    print("✓ TTS engine started")
    
    # Announce startup
    tts_engine.speak("NaviGlass system initialized")

    try: # Start narration runner
        runner = narrate_sentences_periodically(sentence_from_llm_default, interval_seconds=5.0)
        t = threading.Thread(target=runner, daemon=True)
        t.start()
        print("Started narration thread")
    except Exception as e:
        print(f"Failed to start narration thread: {e}")

    try:
        app.run(host='0.0.0.0', port=5000) # Start the web server

    finally:
        cleanup_handler(None, None)
