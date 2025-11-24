"""
Bluetooth Audio Manager for NaviGlass
Handles Bluetooth device discovery, pairing, and audio output routing.
"""

import subprocess
import os
import time
from typing import Optional, List, Dict


class BluetoothAudioManager:
    """Manages Bluetooth audio device connections for NaviGlass."""
    
    def __init__(self, device_mac: Optional[str] = None):
        """
        Initialize Bluetooth Audio Manager.
        
        Args:
            device_mac: MAC address of the Bluetooth device to connect to.
                       If None, will need to be set later.
        """
        self.device_mac = device_mac
        self.connected = False
        
    def scan_devices(self, duration: int = 10) -> List[Dict[str, str]]:
        """
        Scan for available Bluetooth devices.
        
        Args:
            duration: Scan duration in seconds
            
        Returns:
            List of dictionaries with 'mac' and 'name' keys
        """
        print(f"Scanning for Bluetooth devices for {duration} seconds...")
        devices = []
        
        try:
            # Start Bluetooth scan using bluetoothctl
            result = subprocess.run(
                ["bluetoothctl", "devices"],
                capture_output=True,
                text=True,
                timeout=duration + 5
            )
            
            if result.returncode == 0:
                # Parse output: "Device XX:XX:XX:XX:XX:XX Device Name"
                for line in result.stdout.strip().split('\n'):
                    if line.startswith("Device"):
                        parts = line.split(maxsplit=2)
                        if len(parts) >= 3:
                            devices.append({
                                'mac': parts[1],
                                'name': parts[2] if len(parts) > 2 else 'Unknown'
                            })
            
            print(f"Found {len(devices)} Bluetooth device(s)")
            for dev in devices:
                print(f"  - {dev['name']} ({dev['mac']})")
                
        except subprocess.TimeoutExpired:
            print("Bluetooth scan timed out")
        except FileNotFoundError:
            print("ERROR: bluetoothctl not found. Please install bluez-utils.")
        except Exception as e:
            print(f"Error scanning Bluetooth devices: {e}")
            
        return devices
    
    def pair_device(self, mac_address: str) -> bool:
        """
        Pair with a Bluetooth device.
        
        Args:
            mac_address: MAC address of the device
            
        Returns:
            True if pairing successful, False otherwise
        """
        print(f"Pairing with {mac_address}...")
        
        try:
            # Trust the device first
            subprocess.run(
                ["bluetoothctl", "trust", mac_address],
                capture_output=True,
                timeout=10
            )
            
            # Pair with the device
            result = subprocess.run(
                ["bluetoothctl", "pair", mac_address],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if "Pairing successful" in result.stdout or "AlreadyExists" in result.stderr:
                print(f"Successfully paired with {mac_address}")
                return True
            else:
                print(f"Failed to pair with {mac_address}")
                print(f"Output: {result.stdout}")
                print(f"Error: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            print("Pairing timed out")
            return False
        except Exception as e:
            print(f"Error pairing device: {e}")
            return False
    
    def connect_audio(self, mac_address: Optional[str] = None) -> bool:
        """
        Connect to a Bluetooth audio device.
        
        Args:
            mac_address: MAC address to connect to. Uses self.device_mac if None.
            
        Returns:
            True if connection successful, False otherwise
        """
        target_mac = mac_address or self.device_mac
        
        if not target_mac:
            print("ERROR: No MAC address provided for Bluetooth connection")
            return False
        
        print(f"Connecting to Bluetooth audio device: {target_mac}")
        
        try:
            # Connect to the device
            result = subprocess.run(
                ["bluetoothctl", "connect", target_mac],
                capture_output=True,
                text=True,
                timeout=20
            )
            
            if "Connection successful" in result.stdout or "AlreadyConnected" in result.stderr:
                print(f"Successfully connected to {target_mac}")
                self.connected = True
                self.device_mac = target_mac
                
                # Set as default audio sink
                time.sleep(2)  # Wait for device to be recognized
                self._set_default_audio_sink()
                
                return True
            else:
                print(f"Failed to connect to {target_mac}")
                print(f"Output: {result.stdout}")
                print(f"Error: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            print("Connection timed out")
            return False
        except Exception as e:
            print(f"Error connecting to device: {e}")
            return False
    
    def _set_default_audio_sink(self):
        """Set the Bluetooth device as the default audio sink using PulseAudio."""
        try:
            # Get list of sinks
            result = subprocess.run(
                ["pactl", "list", "short", "sinks"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            # Find the Bluetooth sink (usually contains "bluez")
            for line in result.stdout.split('\n'):
                if 'bluez' in line.lower():
                    sink_name = line.split()[1]
                    # Set as default
                    subprocess.run(
                        ["pactl", "set-default-sink", sink_name],
                        timeout=5
                    )
                    print(f"Set default audio sink to: {sink_name}")
                    return
                    
        except Exception as e:
            print(f"Warning: Could not set default audio sink: {e}")
            print("Audio may still work through default routing")
    
    def disconnect(self) -> bool:
        """
        Disconnect from the current Bluetooth device.
        
        Returns:
            True if disconnection successful, False otherwise
        """
        if not self.device_mac:
            print("No device to disconnect from")
            return True
        
        print(f"Disconnecting from {self.device_mac}")
        
        try:
            result = subprocess.run(
                ["bluetoothctl", "disconnect", self.device_mac],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                print(f"Disconnected from {self.device_mac}")
                self.connected = False
                return True
            else:
                print(f"Failed to disconnect: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"Error disconnecting device: {e}")
            return False
    
    def is_connected(self) -> bool:
        """Check if currently connected to a Bluetooth device."""
        return self.connected


# Command-line utility for testing
if __name__ == "__main__":
    import sys
    
    manager = BluetoothAudioManager()
    
    if len(sys.argv) > 1 and sys.argv[1] == "scan":
        # Scan for devices
        devices = manager.scan_devices(duration=10)
        
    elif len(sys.argv) > 1 and sys.argv[1] == "connect":
        # Connect to device
        if len(sys.argv) < 3:
            print("Usage: python3 bluetooth_audio.py connect XX:XX:XX:XX:XX:XX")
            sys.exit(1)
        
        mac = sys.argv[2]
        manager.pair_device(mac)
        manager.connect_audio(mac)
        
    else:
        print("Usage:")
        print("  python3 bluetooth_audio.py scan")
        print("  python3 bluetooth_audio.py connect XX:XX:XX:XX:XX:XX")
