# NaviGlass Raspberry Pi Deployment Guide

This guide will help you transfer your code to the Raspberry Pi and set it up for operation.

## Prerequisites

- Raspberry Pi (3B+, 4, or 5) with Raspberry Pi OS (Legacy/Buster or Bullseye recommended for camera compatibility)
- Internet connection on the Pi
- SSH enabled on the Pi

## Step 1: Transfer Files to Raspberry Pi

You can use `scp` (Secure Copy) to transfer the files from your Mac to the Pi.

Replace `pi@raspberrypi.local` with your Pi's username and hostname/IP.

```bash
# Open Terminal on your Mac and navigate to the project folder
cd /Users/smaran/Desktop/NaviGlass

# Transfer all files (excluding virtual env and cache)
scp -r objectDetection.py bluetooth_audio.py tts_engine.py face_database.py enroll_face.py requirements.txt .env faces_database.json yolo11n_ncnn_model pi@raspberrypi.local:~/NaviGlass
```

*Note: If `raspberrypi.local` doesn't work, use the Pi's IP address (e.g., `pi@192.168.1.15`).*

## Step 2: Install System Dependencies on Pi

SSH into your Raspberry Pi:

```bash
ssh pi@raspberrypi.local
```

Run the following commands on the Pi:

```bash
# Update system
sudo apt-get update
sudo apt-get upgrade -y

# Install required system libraries
sudo apt-get install -y \
    python3-pip \
    python3-dev \
    libatlas-base-dev \
    libjasper-dev \
    libqtgui4 \
    libqt4-test \
    espeak \
    bluez \
    pulseaudio-module-bluetooth \
    cmake \
    build-essential \
    libboost-all-dev \
    libopenblas-dev \
    liblapack-dev
```

## Step 3: Install Python Dependencies

Navigate to the folder and install Python packages:

```bash
cd ~/NaviGlass
pip3 install -r requirements.txt
```

*Warning: Installing `dlib` (dependency of `face_recognition`) can take 45+ minutes on a Raspberry Pi 3/4. Please be patient.*

## Step 4: Configure Hardware

### Enable Camera
```bash
sudo raspi-config
# Go to: 3 Interface Options -> I1 Legacy Camera -> Yes
# OR for Bullseye/Bookworm: 3 Interface Options -> I1 Camera -> Yes
```

### Enable I2C and GPIO (if needed)
```bash
# In raspi-config: 3 Interface Options -> I5 I2C -> Yes
# In raspi-config: 3 Interface Options -> I8 Remote GPIO -> Yes
```

### Reboot
```bash
sudo reboot
```

## Step 5: Setup Bluetooth Audio

1. **Start PulseAudio**:
   ```bash
   pulseaudio --start
   ```

2. **Scan and Pair** (using our helper script):
   ```bash
   python3 bluetooth_audio.py scan
   # Note the MAC address of your device (e.g., XX:XX:XX:XX:XX:XX)
   
   python3 bluetooth_audio.py connect XX:XX:XX:XX:XX:XX
   ```

3. **Update .env**:
   Edit the `.env` file to add your Bluetooth MAC address so it connects automatically next time.
   ```bash
   nano .env
   # Add: BLUETOOTH_DEVICE_MAC=XX:XX:XX:XX:XX:XX
   ```

## Step 6: Run NaviGlass

```bash
python3 objectDetection.py
```

## Troubleshooting

### "ModuleNotFoundError: No module named 'picamera2'"
If you are on an older OS (Buster), you might need `picamera` instead of `picamera2`.
- **Fix**: Upgrade to Bullseye/Bookworm OR modify code to use `picamera`.

### "Can't open camera"
- Check ribbon cable connection.
- Verify camera is enabled in `raspi-config`.
- Test with `libcamera-hello` (Bullseye/Bookworm) or `raspistill` (Legacy).

### "Audio not playing"
- Check volume: `alsamixer`
- Verify Bluetooth connection: `bluetoothctl info`

### "Memory Error" during dlib install
- Increase swap size:
  ```bash
  sudo nano /etc/dphys-swapfile
  # Change CONF_SWAPSIZE=100 to CONF_SWAPSIZE=1024
  sudo /etc/init.d/dphys-swapfile restart
  ```
  *Remember to change it back after installation to save SD card life.*
