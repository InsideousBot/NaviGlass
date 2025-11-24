import time
import cv2
from picamera2 import Picamera2
from flask import Flask, Response, jsonify, request, render_template_string, send_file # Used for web streaming
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
                    # Store for web interface
                    set_latest_narration(sentence)
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



# Global variable to store latest narration for web interface
_latest_narration = ""
_narration_lock = threading.Lock()

def set_latest_narration(text):
    global _latest_narration
    with _narration_lock:
        _latest_narration = text

def get_latest_narration():
    with _narration_lock:
        return _latest_narration


# HTML Template for Web Interface
WEB_INTERFACE_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>NaviGlass Control Panel</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        h1 {
            color: white;
            text-align: center;
            margin-bottom: 30px;
            font-size: 2.5em;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }
        .card {
            background: white;
            border-radius: 15px;
            padding: 25px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }
        .card h2 {
            color: #667eea;
            margin-bottom: 15px;
            font-size: 1.5em;
        }
        .video-feed {
            width: 100%;
            border-radius: 10px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.2);
        }
        .btn {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 16px;
            font-weight: 600;
            transition: transform 0.2s, box-shadow 0.2s;
            width: 100%;
            margin-top: 10px;
        }
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
        }
        input[type="text"], input[type="file"] {
            width: 100%;
            padding: 10px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            font-size: 14px;
            margin-bottom: 10px;
        }
        input[type="text"]:focus, input[type="file"]:focus {
            outline: none;
            border-color: #667eea;
        }
        .status {
            padding: 15px;
            border-radius: 8px;
            margin-top: 10px;
            font-weight: 600;
        }
        .status.success { background: #d4edda; color: #155724; }
        .status.error { background: #f8d7da; color: #721c24; }
        .status.info { background: #d1ecf1; color: #0c5460; }
        .face-list {
            max-height: 300px;
            overflow-y: auto;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            padding: 10px;
            margin-top: 10px;
        }
        .face-item {
            padding: 10px;
            background: #f8f9fa;
            margin-bottom: 8px;
            border-radius: 6px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .face-item button {
            background: #dc3545;
            color: white;
            border: none;
            padding: 6px 12px;
            border-radius: 5px;
            cursor: pointer;
            font-size: 12px;
        }
        .narration-display {
            background: #f8f9fa;
            border: 2px solid #667eea;
            border-radius: 8px;
            padding: 20px;
            min-height: 100px;
            font-size: 18px;
            color: #333;
            text-align: center;
            margin-top: 15px;
        }
        @media (max-width: 768px) {
            h1 { font-size: 1.8em; }
            .grid { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🕶️ NaviGlass Control Panel</h1>
        
        <div class="grid">
            <!-- Live Feed -->
            <div class="card" style="grid-column: span 2;">
                <h2>📹 Live Camera Feed</h2>
                <img src="/video_feed" class="video-feed" alt="Live Feed">
                <div class="narration-display" id="narrationDisplay">
                    <em>Waiting for narration...</em>
                </div>
            </div>
            
            <!-- Face Enrollment -->
            <div class="card">
                <h2>👤 Enroll New Face</h2>
                <input type="text" id="faceName" placeholder="Enter person's name">
                <button class="btn" onclick="captureAndEnroll()">📸 Capture & Enroll</button>
                <div id="enrollStatus"></div>
            </div>
            
            <!-- Face Database -->
            <div class="card">
                <h2>📚 Face Database</h2>
                <button class="btn" onclick="loadFaces()">🔄 Refresh List</button>
                <div class="face-list" id="faceList">
                    <em>Click refresh to load faces</em>
                </div>
            </div>
            
            <!-- Audio Control -->
            <div class="card">
                <h2>🔊 Audio Control</h2>
                <button class="btn" onclick="testAudio()">🎵 Test TTS</button>
                <button class="btn" onclick="toggleNarration()">⏯️ Toggle Narration</button>
                <div id="audioStatus"></div>
            </div>
            
            <!-- System Status -->
            <div class="card">
                <h2>⚙️ System Status</h2>
                <button class="btn" onclick="getStatus()">🔍 Check Status</button>
                <div id="systemStatus"></div>
            </div>
        </div>
    </div>
    
    <script>
        // Poll for latest narration
        setInterval(async () => {
            try {
                const response = await fetch('/api/latest_narration');
                const data = await response.json();
                if (data.narration) {
                    document.getElementById('narrationDisplay').innerHTML = 
                        '<strong>' + data.narration + '</strong>';
                }
            } catch (error) {
                console.error('Error fetching narration:', error);
            }
        }, 1000);
        
        async function captureAndEnroll() {
            const name = document.getElementById('faceName').value.trim();
            if (!name) {
                showStatus('enrollStatus', 'Please enter a name', 'error');
                return;
            }
            
            showStatus('enrollStatus', 'Capturing face in 3 seconds...', 'info');
            
            try {
                const response = await fetch('/api/enroll_face', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({name: name})
                });
                
                const data = await response.json();
                if (data.success) {
                    showStatus('enrollStatus', '✅ ' + data.message, 'success');
                    document.getElementById('faceName').value = '';
                    loadFaces();
                } else {
                    showStatus('enrollStatus', '❌ ' + data.message, 'error');
                }
            } catch (error) {
                showStatus('enrollStatus', '❌ Error: ' + error, 'error');
            }
        }
        
        async function loadFaces() {
            try {
                const response = await fetch('/api/list_faces');
                const data = await response.json();
                
                const faceListDiv = document.getElementById('faceList');
                if (data.faces.length === 0) {
                    faceListDiv.innerHTML = '<em>No faces enrolled yet</em>';
                } else {
                    faceListDiv.innerHTML = data.faces.map(face => 
                        `<div class="face-item">
                            <span>${face.name}</span>
                            <button onclick="deleteFace('${face.name}')">🗑️ Delete</button>
                        </div>`
                    ).join('');
                }
            } catch (error) {
                console.error('Error loading faces:', error);
            }
        }
        
        async function deleteFace(name) {
            if (!confirm('Delete ' + name + '?')) return;
            
            try {
                const response = await fetch('/api/delete_face', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({name: name})
                });
                
                const data = await response.json();
                if (data.success) {
                    loadFaces();
                } else {
                    alert('Failed to delete: ' + data.message);
                }
            } catch (error) {
                alert('Error: ' + error);
            }
        }
        
        async function testAudio() {
            showStatus('audioStatus', 'Playing test audio...', 'info');
            try {
                const response = await fetch('/api/test_audio', {method: 'POST'});
                const data = await response.json();
                showStatus('audioStatus', '🔊 ' + data.message, 'success');
            } catch (error) {
                showStatus('audioStatus', '❌ Error: ' + error, 'error');
            }
        }
        
        async function toggleNarration() {
            try {
                const response = await fetch('/api/toggle_narration', {method: 'POST'});
                const data = await response.json();
                showStatus('audioStatus', data.message, 'info');
            } catch (error) {
                showStatus('audioStatus', '❌ Error: ' + error, 'error');
            }
        }
        
        async function getStatus() {
            try {
                const response = await fetch('/api/system_status');
                const data = await response.json();
                
                const statusHTML = `
                    <div class="status info">
                        <strong>📊 System Information</strong><br>
                        TTS: ${data.tts_running ? '✅ Running' : '❌ Stopped'}<br>
                        Bluetooth: ${data.bluetooth_connected ? '✅ Connected' : '❌ Disconnected'}<br>
                        Faces: ${data.faces_count} enrolled<br>
                        Face Recognition: ${data.face_recognition_enabled ? '✅ Enabled' : '❌ Disabled'}
                    </div>
                `;
                document.getElementById('systemStatus').innerHTML = statusHTML;
            } catch (error) {
                showStatus('systemStatus', '❌ Error: ' + error, 'error');
            }
        }
        
        function showStatus(elementId, message, type) {
            const statusDiv = document.getElementById(elementId);
            statusDiv.innerHTML = `<div class="status ${type}">${message}</div>`;
            setTimeout(() => {
                statusDiv.innerHTML = '';
            }, 5000);
        }
        
        // Load faces on page load
        window.onload = () => {
            loadFaces();
            getStatus();
        };
    </script>
</body>
</html>
'''


@app.route('/') # Serves the web interface
def index():
    return render_template_string(WEB_INTERFACE_HTML)


@app.route('/video_feed') # Generate the frames and feed it to the stream
def video_feed():
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/api/latest_narration') # Get latest narration
def api_latest_narration():
    return jsonify({'narration': get_latest_narration()})


@app.route('/api/enroll_face', methods=['POST']) # Enroll a new face
def api_enroll_face():
    try:
        data = request.get_json()
        name = data.get('name', '').strip()
        
        if not name:
            return jsonify({'success': False, 'message': 'Name is required'})
        
        # Check if name already exists
        if face_db.get_face_by_name(name):
            return jsonify({'success': False, 'message': f'Face with name "{name}" already exists'})
        
        # Capture current frame
        time.sleep(3)  # Give user time to position
        frame = picam.capture_array()
        
        # Add to database
        if face_db.add_face(name, image_array=frame):
            # Update global face recognition status
            global FACE_RECOGNITION_ENABLED
            FACE_RECOGNITION_ENABLED = face_db.count() > 0
            return jsonify({'success': True, 'message': f'Successfully enrolled {name}'})
        else:
            return jsonify({'success': False, 'message': 'No face detected in image'})
            
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/list_faces') # List all enrolled faces
def api_list_faces():
    faces = face_db.list_faces()
    face_list = []
    for name in faces:
        face = face_db.get_face_by_name(name)
        face_list.append({
            'name': name,
            'date_added': face.get('date_added', 'Unknown')
        })
    return jsonify({'faces': face_list})


@app.route('/api/delete_face', methods=['POST']) # Delete a face
def api_delete_face():
    try:
        data = request.get_json()
        name = data.get('name', '').strip()
        
        if face_db.remove_face(name):
            # Update global face recognition status
            global FACE_RECOGNITION_ENABLED
            FACE_RECOGNITION_ENABLED = face_db.count() > 0
            return jsonify({'success': True, 'message': f'Deleted {name}'})
        else:
            return jsonify({'success': False, 'message': f'Face "{name}" not found'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/test_audio', methods=['POST']) # Test TTS
def api_test_audio():
    tts_engine.speak("NaviGlass text to speech test. Audio is working correctly.")
    return jsonify({'success': True, 'message': 'Test audio played'})


_narration_enabled = True
@app.route('/api/toggle_narration', methods=['POST']) # Toggle narration
def api_toggle_narration():
    global _narration_enabled
    _narration_enabled = not _narration_enabled
    status = "enabled" if _narration_enabled else "disabled"
    return jsonify({'success': True, 'message': f'Narration {status}'})


@app.route('/api/system_status') # Get system status
def api_system_status():
    return jsonify({
        'tts_running': tts_engine.is_running,
        'bluetooth_connected': bluetooth_manager.is_connected(),
        'faces_count': face_db.count(),
        'face_recognition_enabled': FACE_RECOGNITION_ENABLED,
        'gemini_enabled': GEMINI_ENABLED
    })




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
