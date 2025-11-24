# NaviGlass Raspberry Pi Deployment Guide

Complete setup guide for deploying NaviGlass on Raspberry Pi with camera, distance sensors, Bluetooth audio, and face recognition.

---

## Hardware Requirements

### Essential Components
- **Raspberry Pi 4** (or newer, 4GB RAM minimum)
- **Raspberry Pi Camera Module** (v2 or HQ Camera)
- **2x HC-SR04 Ultrasonic Distance Sensors**
- **Bluetooth Headphones/Speaker**
- **MicroSD Card** (32GB minimum, Class 10)
- **Power Supply** (5V 3A official Raspberry Pi adapter)

### Optional Components
- Case for Raspberry Pi
- Breadboard and jumper wires for prototyping
- External battery pack for portable use

---

## GPIO Wiring Diagram

Connect the ultrasonic sensors to the Raspberry Pi GPIO pins as follows:

| Component | GPIO Pin (BOARD) | Physical Pin |
|-----------|------------------|--------------|
| **Sensor 1 Trigger** | GPIO 13 | Pin 33 |
| **Sensor 1 Echo** | GPIO 11 | Pin 23 |
| **Sensor 2 Trigger** | GPIO 16 | Pin 36 |
| **Sensor 2 Echo** | GPIO 18 | Pin 12 |
| **VCC (Both Sensors)** | 5V | Pin 2 or 4 |
| **GND (Both Sensors)** | GND | Pin 6, 9, 14, etc. |

**Important**: The HC-SR04 sensor ECHO pin outputs 5V, which can damage the Raspberry Pi's 3.3V GPIO pins. Use a voltage divider (two resistors: 1kΩ and 2kΩ) on each ECHO pin to step down the voltage to 3.3V.

---

## Part 1: Raspberry Pi OS Installation

### 1.1 Flash Raspberry Pi OS

1. Download **Raspberry Pi Imager**: https://www.raspberrypi.com/software/
2. Insert your microSD card into your computer
3. Open Raspberry Pi Imager:
   - **OS**: Raspberry Pi OS (64-bit) Bullseye or Bookworm
   - **Storage**: Select your microSD card
   - Click ⚙️ (Advanced Options):
     - Set hostname: `naviglass.local`
     - Enable SSH
     - Set username/password
     - Configure WiFi (optional)
4. Click **Write** and wait for completion

### 1.2 Boot and Initial Setup

1. Insert microSD card into Raspberry Pi
2. Connect camera ribbon cable to CSI port
3. Power on the Raspberry Pi
4. Find IP address:
   ```bash
   # From your computer
   ping naviglass.local
   # OR check your router's DHCP table
   ```

5. SSH into Raspberry Pi:
   ```bash
   ssh pi@naviglass.local
   # Default password: raspberry (if not changed)
   ```

---

## Part 2: System Configuration

### 2.1 Enable Camera and Interfaces

```bash
sudo raspi-config
```

Navigate and enable:
- **3 Interface Options** → **I1 Camera** → **Yes**
- **3 Interface Options** → **I5 I2C** → **Yes** (optional)
- **3 Interface Options** → **I4 SPI** → **Yes** (optional)

Select **Finish** and **Reboot**: `sudo reboot`

### 2.2 Update System

```bash
sudo apt-get update
sudo apt-get upgrade -y
```

### 2.3 Install System Dependencies

```bash
# Install Python and development tools
sudo apt-get install -y \\
    python3-pip \\
    python3-dev \\
    python3-venv \\
    build-essential \\
    cmake \\
    pkg-config

# Install OpenCV dependencies
sudo apt-get install -y \\
    libopencv-dev \\
    libatlas-base-dev \\
    libjasper-dev \\
    libqtgui4 \\
    libqt4-test \\
    libhdf5-dev

# Install audio dependencies
sudo apt-get install -y \\
    espeak \\
    pulseaudio \\
    pulseaudio-module-bluetooth \\
    bluez \\
    bluez-tools

# Install face recognition dependencies (dlib requirements)
sudo apt-get install -y \\
    libboost-all-dev \\
    libopenblas-dev \\
    liblapack-dev
```

---

## Part 3: Transfer Project Files

### 3.1 From Your Computer

```bash
# Navigate to project folder on your Mac
cd /Users/smaran/Desktop/NaviGlass

# Transfer all files to Raspberry Pi
scp -r \\
  objectDetection.py \\
  bluetooth_audio.py \\
  tts_engine.py \\
  face_database.py \\
  enroll_face.py \\
  requirements.txt \\
  .env \\
  faces_database.json \\
  yolo11n_ncnn_model \\
  pi@naviglass.local:~/NaviGlass/

# OR use rsync for faster sync
rsync -av --progress \\
  --exclude '__pycache__' \\
  --exclude '.git' \\
  ./ pi@naviglass.local:~/NaviGlass/
```

---

## Part 4: Python Environment Setup

### 4.1 Create Virtual Environment

```bash
# SSH into Raspberry Pi
ssh pi@naviglass.local

# Navigate to project
cd ~/NaviGlass

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip setuptools wheel
```

### 4.2 Install Python Dependencies

**Important**: Installing `dlib` and `face_recognition` can take 60-90 minutes on Raspberry Pi due to compilation. Be patient!

```bash
# Install dependencies one by one for better error tracking
pip install python-dotenv
pip install numpy
pip install opencv-python
pip install flask
pip install google-generativeai
pip install picamera2
pip install ultralytics

# Install TTS (quick)
pip install pyttsx3

# Install dlib (SLOW - 45-60 minutes)
# Increase swap if needed (see troubleshooting)
pip install dlib

# Install face_recognition (requires dlib)
pip install face_recognition

# Install Bluetooth (if needed)
pip install pybluez pyaudio
```

**Alternative**: Install all at once (riskier if any fail):
```bash
pip install -r requirements.txt
```

---

## Part 5: Configuration

### 5.1 Configure Environment Variables

```bash
cd ~/NaviGlass

# Edit .env file
nano .env
```

Set your configuration:
```bash
# Gemini API Key (REQUIRED)
GEMINI_API_KEY=your_actual_api_key_here

# Bluetooth Device MAC (OPTIONAL - get from scanning)
BLUETOOTH_DEVICE_MAC=

# TTS Settings
TTS_RATE=150
TTS_VOLUME=1.0

# Face Recognition Settings
FACE_RECOGNITION_TOLERANCE=0.6
FACE_RECOGNITION_INTERVAL=5

# Web Server Port
PORT=5000
```

Save and exit (Ctrl+X, Y, Enter).

### 5.2 Setup Bluetooth Audio

#### Pair Bluetooth Device

```bash
# Start Bluetooth service
sudo systemctl start bluetooth
sudo systemctl enable bluetooth

# Start PulseAudio
pulseaudio --start

# Open Bluetooth control
bluetoothctl

# In bluetoothctl:
power on
agent on
default-agent
scan on
# Wait for your device to appear, note its MAC address (XX:XX:XX:XX:XX:XX)
scan off
pair XX:XX:XX:XX:XX:XX
trust XX:XX:XX:XX:XX:XX
connect XX:XX:XX:XX:XX:XX
exit
```

#### Or Use Python Helper Script

```bash
# Activate virtual environment
source ~/NaviGlass/venv/bin/activate

# Scan for devices
python3 bluetooth_audio.py scan

# Connect to device
python3 bluetooth_audio.py connect XX:XX:XX:XX:XX:XX
```

#### Update .env with MAC Address

```bash
nano .env
# Set: BLUETOOTH_DEVICE_MAC=XX:XX:XX:XX:XX:XX
```

---

## Part 6: Test Individual Components

### 6.1 Test Camera

```bash
# Using libcamera (Bullseye/Bookworm)
libcamera-hello

# OR using Python
python3 -c "from picamera2 import Picamera2; cam = Picamera2(); cam.start(); print('Camera OK'); cam.stop()"
```

### 6.2 Test Distance Sensors

Create test script:
```bash
nano test_sensors.py
```

```python
import RPi.GPIO as GPIO
import time

TRIG = 13
ECHO = 11

GPIO.setmode(GPIO.BOARD)
GPIO.setup(TRIG, GPIO.OUT)
GPIO.setup(ECHO, GPIO.IN)

GPIO.output(TRIG, False)
time.sleep(0.5)

GPIO.output(TRIG, True)
time.sleep(0.00001)
GPIO.output(TRIG, False)

while GPIO.input(ECHO) == 0:
    pulse_start = time.time()

while GPIO.input(ECHO) == 1:
    pulse_end = time.time()

pulse_duration = pulse_end - pulse_start
distance = pulse_duration * 17150
print(f"Distance: {distance:.1f} cm")

GPIO.cleanup()
```

Run test:
```bash
python3 test_sensors.py
```

### 6.3 Test Text-to-Speech

```bash
source ~/NaviGlass/venv/bin/activate
python3 tts_engine.py
# Should hear: "NaviGlass Text to Speech Engine initialized"
```

---

## Part 7: Run NaviGlass

### 7.1 Start the System

```bash
# Activate virtual environment
source ~/NaviGlass/venv/bin/activate

# Run NaviGlass
python3 objectDetection.py
```

Expected output:
```
Camera initialized.
YOLO11n loaded.
Gemini API key found, enabling Gemini narration.
TTS Engine initialized (rate=150, volume=1.0)
Loaded 0 face(s) from database
Face recognition disabled (no faces in database)
GPIO setup complete.
✓ TTS engine started
✓ NaviGlass system initialized
Started narration thread
 * Running on all addresses (0.0.0.0)
 * Running on http://127.0.0.1:5000
 * Running on http://192.168.1.X:5000
```

### 7.2 Access Web Interface

From any device on the same network, open browser:
```
http://naviglass.local:5000
# OR
http://<raspberry-pi-ip>:5000
```

You should see the **NaviGlass Control Panel** with:
- 📹 Live camera feed
- 👤 Face enrollment
- 📚 Face database
- 🔊 Audio control
- ⚙️ System status

---

## Part 8: Enroll Faces

### Method 1: Web Interface (Recommended)

1. Open `http://naviglass.local:5000`
2. Enter person's name in "Enroll New Face"
3. Click "📸 Capture & Enroll"
4. Position face in front of camera
5. Wait 3 seconds for capture
6. Check status message

### Method 2: Command Line

```bash
source ~/NaviGlass/venv/bin/activate
python3 enroll_face.py

# Follow prompts:
# Enter person's name: John Doe
# Press ENTER when ready...
```

---

## Part 9: Auto-Start on Boot (Optional)

### 9.1 Create Systemd Service

```bash
sudo nano /etc/systemd/system/naviglass.service
```

Paste:
```ini
[Unit]
Description=NaviGlass Assistive System
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/NaviGlass
ExecStart=/home/pi/NaviGlass/venv/bin/python3 /home/pi/NaviGlass/objectDetection.py
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
```

Enable service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable naviglass.service
sudo systemctl start naviglass.service
```

Check status:
```bash
sudo systemctl status naviglass.service
```

View logs:
```bash
sudo journalctl -u naviglass.service -f
```

---

## Troubleshooting

### Issue: "Memory Error" during dlib install

**Solution**: Increase swap space temporarily

```bash
# Check current swap
free -h

# Increase swap
sudo dphys-swapfile swapoff
sudo nano /etc/dphys-swapfile
# Change: CONF_SWAPSIZE=2048

sudo dphys-swapfile setup
sudo dphys-swapfile swapon

# After dlib installs, change back to 100 to preserve SD card
```

### Issue: Camera not found

```bash
# Check camera connection
vcgencmd get_camera

# Should show: supported=1 detected=1

# If not, check:
# 1. Ribbon cable firmly connected
# 2. Camera enabled in raspi-config
# 3. Reboot
```

### Issue: "Permission denied" for GPIO

```bash
# Add user to GPIO group
sudo usermod -a -G gpio pi
sudo usermod -a -G i2c pi

# Logout and login again
```

### Issue: Bluetooth audio not working

```bash
# Restart Bluetooth and PulseAudio
sudo systemctl restart bluetooth
pulseaudio -k
pulseaudio --start

# Check PulseAudio sinks
pactl list short sinks

# Set default sink to Bluetooth
pactl set-default-sink bluez_sink.XX_XX_XX_XX_XX_XX.a2dp_sink
```

### Issue: YOLO model not found

The YOLO model directory `yolo11n_ncnn_model` must be transferred to the Pi. If missing:

```bash
# On your Mac, make sure the model exists
ls -la yolo11n_ncnn_model/

# Transfer it
scp -r yolo11n_ncnn_model pi@naviglass.local:~/NaviGlass/
```

### Issue: Port 5000 already in use

```bash
# Find what's using port 5000
sudo lsof -i :5000

# Kill the process or change PORT in .env
nano .env
# Set: PORT=5001
```

---

## Performance Optimization

### Reduce Face Recognition Load

Edit `.env`:
```bash
# Check faces less frequently (every 10 seconds instead of 5)
FACE_RECOGNITION_INTERVAL=10

# Or disable until needed
# (Will auto-enable when faces are enrolled)
```

### Overclock Raspberry Pi (Optional)

```bash
sudo nano /boot/config.txt

# Add at the end:
over_voltage=2
arm_freq=1750

sudo reboot
```

**Warning**: Ensure proper cooling!

---

## System Maintenance

### Update NaviGlass Code

```bash
cd ~/NaviGlass
git pull  # If using git

# OR re-transfer files from Mac
```

### Backup Face Database

```bash
# Backup faces_database.json
cp faces_database.json faces_database_backup.json

# Transfer to Mac
scp pi@naviglass.local:~/NaviGlass/faces_database.json ~/Desktop/
```

### Update Python Packages

```bash
source ~/NaviGlass/venv/bin/activate
pip install --upgrade pip
pip list --outdated
pip install --upgrade <package_name>
```

---

## Usage Guide

### Starting the System

```bash
ssh pi@naviglass.local
cd ~/NaviGlass
source venv/bin/activate
python3 objectDetection.py
```

### Stopping the System

Press `Ctrl+C` in the terminal.

### Accessing Features

- **Web Interface**: `http://naviglass.local:5000`
- **Live Video**: Shows real-time camera feed with object detection
- **Enroll Faces**: Add new people to recognition database
- **System Status**: Check TTS, Bluetooth, and face recognition status
- **Test Audio**: Play test narration through Bluetooth

---

## Network Access

To access from outside your local network:
1. Set up port forwarding on your router (port 5000 → Raspberry Pi IP)
2. Use dynamic DNS service (e.g., No-IP, DuckDNS)
3. **Security**: Add authentication to Flask app or use VPN

---

## Support & Resources

- **Raspberry Pi Documentation**: https://www.raspberrypi.com/documentation/
- **Picamera2 Guide**: https://datasheets.raspberrypi.com/camera/picamera2-manual.pdf
- **YOLO Docs**: https://docs.ultralytics.com/
- **Google Gemini API**: https://ai.google.dev/

---

## Quick Reference Commands

```bash
# Start NaviGlass
cd ~/NaviGlass && source venv/bin/activate && python3 objectDetection.py

# Enroll face
python3 enroll_face.py

# Scan Bluetooth devices
python3 bluetooth_audio.py scan

# Check system journal
sudo journalctl -u naviglass.service -f

# Restart service
sudo systemctl restart naviglass.service
```

Happy NaviGlassing! 🕶️
