# NaviGlass - Assistive Glasses for the Blind

NaviGlass is an assistive device powered by a Raspberry Pi that helps blind users navigate their environment using:
- **YOLO11n Object Detection** - Real-time detection of people, vehicles, and objects
- **Ultrasonic Distance Sensors** - Measures distances to detected objects  
- **AI-Powered Narration** - Natural language descriptions using Google Gemini
- **Text-to-Speech** - Audio feedback through Bluetooth or speakers
- **Face Recognition** - Recognizes specific individuals by name
- **Web Control Panel** - Browser-based interface for system management

## Features

### 🎯 Object Detection
- Detects common objects: people, cars, bicycles, traffic signs, etc.
- 70% confidence threshold for reliable detection
- Real-time processing with FPS monitoring

### 📏 Distance Measurement
- Dual ultrasonic sensors (HC-SR04)
- Range: 2-400 cm
- Average of 5 measurements for accuracy

### 🗣️ Text-to-Speech
- Offline TTS using pyttsx3
- Queue-based speech for smooth narration
- Bluetooth audio support

### 📡 Bluetooth Audio
- Connect to Bluetooth headphones/speakers
- Automatic audio routing via PulseAudio
- Configurable device MAC address

### 👤 Face Recognition
- Database of known faces
- Personalized greetings ("Hello, John!")
- Easy enrollment with camera
- Runs every 5 seconds to preserve performance

### 🌐 Web Control Panel
- Live camera feed with object detection overlays
- Real-time narration display
- Face enrollment through browser
- Database management (add/remove faces)
- System status monitoring
- Audio testing and control

## Hardware Requirements

- **Raspberry Pi** (3B+, 4, or 5 recommended)
- **Raspberry Pi Camera Module**
- **2x HC-SR04 Ultrasonic Sensors**
- **Bluetooth Adapter** (built-in on Pi 3B+ and newer)
- **Bluetooth Audio Device** (headphones or speaker)

### GPIO Wiring

| Component | GPIO Pin (BOARD) |
|-----------|------------------|
| Sensor 1 Trigger | 13 |
| Sensor 1 Echo | 11 |
| Sensor 2 Trigger | 16 |
| Sensor 2 Echo | 18 |

## Installation

### 1. System Dependencies

```bash
# Update system
sudo apt-get update && sudo apt-get upgrade -y

# Install system packages
sudo apt-get install -y \\
    python3-pip \\
    python3-dev \\
    libatlas-base-dev \\
    libjasper-dev \\
    libqtgui4 \\
    libqt4-test \\
    espeak \\
    bluez \\
    pulseaudio-module-bluetooth

# For face recognition (dlib dependencies)
sudo apt-get install -y \\
    build-essential \\
    cmake \\
    libboost-all-dev \\
    libopenblas-dev \\
    liblapack-dev
```

### 2. Python Dependencies

```bash
# Install Python packages
pip3 install -r requirements.txt
```

**Note**: Installing `dlib` and `face_recognition` can take 30-60 minutes on Raspberry Pi due to compilation.

### 3. Configuration

```bash
# Copy environment template
cp .env.example .env

# Edit configuration
nano .env
```

Set your configuration:
```
GEMINI_API_KEY=your_gemini_api_key_here
BLUETOOTH_DEVICE_MAC=XX:XX:XX:XX:XX:XX  # Optional
TTS_RATE=150
TTS_VOLUME=1.0
FACE_RECOGNITION_TOLERANCE=0.6
FACE_RECOGNITION_INTERVAL=5
```

### 4. Bluetooth Setup (Optional)

Find your Bluetooth audio device:
```bash
python3 bluetooth_audio.py scan
```

Connect to device:
```bash
python3 bluetooth_audio.py connect XX:XX:XX:XX:XX:XX
```

Or set `BLUETOOTH_DEVICE_MAC` in `.env` for automatic connection.

## Usage

### Running NaviGlass

```bash
python3 objectDetection.py
```

The system will:
1. Initialize camera and sensors
2. Connect to Bluetooth audio (if configured)
3. Start TTS engine
4. Begin object detection and narration
5. Start web server on port 5000

**Access Web Interface**:
Open browser and navigate to:
- `http://naviglass.local:5000` (if hostname configured)
- `http://<raspberry-pi-ip>:5000` (using IP address)

Press `Ctrl+C` to shutdown gracefully.

### Face Enrollment

**Method 1: Web Interface (Recommended)**

1. Open web control panel: `http://<raspberry-pi-ip>:5000`
2. Navigate to "👤 Enroll New Face" section
3. Enter person's name
4. Click "📸 Capture & Enroll"
5. Position face in front of camera (3 second delay)
6. Check status message for confirmation

**Method 2: Command Line**

Add faces to the recognition database:

```bash
# Interactive enrollment with camera
python3 enroll_face.py

# Add from image file
python3 enroll.py add "John Doe" /path/to/photo.jpg

# List enrolled faces
python3 enroll.py list

# Remove a face
python3 enroll.py remove
```

### Face Database Management

```bash
# List faces in database
python3 lib/face_database.py list

# Add face from image
python3 lib/face_database.py add "Jane Smith" photo.jpg

# Remove face
python3 lib/face_database.py remove "Jane Smith"

# Clear database
python3 lib/face_database.py clear
```

### Web Interface Features

Access the control panel at `http://<raspberry-pi-ip>:5000`:

**📹 Live Feed**
- Real-time camera view with object detection boxes
- Live narration display

**👤 Face Enrollment**
- Add new faces directly from browser
- No command line needed

**📚 Face Database**
- View all enrolled faces
- Delete faces with one click
- See enrollment dates

**🔊 Audio Control**
- Test TTS functionality
- Toggle narration on/off

**⚙️ System Status**
- Check TTS engine status
- View Bluetooth connection
- Monitor face recognition

## File Structure

```
NaviGlass/
├── objectDetection.py      # Main application (YOLO + Flask server)
├── bluetooth_audio.py      # Bluetooth audio manager
├── tts_engine.py           # Text-to-speech engine
├── face_database.py        # Face recognition database
├── enroll_face.py          # Face enrollment tool
├── requirements.txt        # Python dependencies
├── .env                    # Environment configuration (your API keys)
├── .env.example            # Environment template
├── faces_database.json     # Face encodings (created automatically)
├── yolo11n_ncnn_model/     # YOLO model files
├── README.md               # This file
└── DEPLOYMENT.md           # Full deployment guide
```

## Troubleshooting

### No Audio Output

1. Check if TTS engine initialized:
   ```
   pulseaudio --start
   speaker-test -t wav -c 2
   ```

2. Test TTS directly:
   ```bash
   python3 tts_engine.py
   ```

### Bluetooth Connection Failed

1. Ensure device is paired:
   ```bash
   bluetoothctl
   > scan on
   > pair XX:XX:XX:XX:XX:XX
   > trust XX:XX:XX:XX:XX:XX
   > connect XX:XX:XX:XX:XX:XX
   ```

2. Check PulseAudio Bluetooth module:
   ```bash
   pactl load-module module-bluetooth-discover
   ```

### Camera Not Found

1. Enable camera:
   ```bash
   sudo raspi-config
   # Interface Options > Camera > Enable
   ```

2. Reboot:
   ```bash
   sudo reboot
   ```

### Face Recognition Slow

- Reduce `FACE_RECOGNITION_INTERVAL` in `.env` (e.g., 10 seconds)
- Consider using fewer enrolled faces
- Use a more powerful Raspberry Pi (Pi 4 or 5)

### GPIO Errors

- Ensure you're running as root or in `gpio` group:
  ```bash
  sudo usermod -a -G gpio $USER
  ```

## API Keys

### Google Gemini API Key

1. Go to [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Create a new API key
3. Add to `.env` file: `GEMINI_API_KEY=your_key_here`

## Performance

Typical performance on Raspberry Pi 4:
- **Object Detection**: 10-15 FPS
- **Face Recognition**: Every 5 seconds (configurable)
- **Narration**: Every 5 seconds when object detected
- **Distance Measurement**: ~100ms per reading

## Contributing

Contributions are welcome! Areas for improvement:
- Multiple language support for TTS
- Mobile app for remote monitoring
- Haptic feedback for closer objects
- Voice commands for system control
- Offline object detection model optimization

## License

This project is open source and available for educational and personal use.

## Credits

- **YOLO** - Ultralytics YOLO11n
- **Face Recognition** - face_recognition library by Adam Geitgey
- **Google Gemini** - AI-powered narration
- **pyttsx3** - Text-to-speech engine

## Safety Notice

⚠️ **Important**: NaviGlass is an assistive tool and should NOT be used as the sole means of navigation. Always use with caution and in conjunction with other mobility aids (cane, guide dog, etc.).
