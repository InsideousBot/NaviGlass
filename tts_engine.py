"""
Text-to-Speech Engine for NaviGlass
Wrapper around pyttsx3 for offline text-to-speech with queue management.
"""

import pyttsx3
import threading
import queue
import time
from typing import Optional


class TTSEngine:
    """Thread-safe text-to-speech engine with queue management."""
    
    def __init__(self, rate: int = 150, volume: float = 1.0):
        """
        Initialize TTS engine.
        
        Args:
            rate: Speech rate (words per minute), default 150
            volume: Volume level (0.0 to 1.0), default 1.0
        """
        self.engine = None
        self.rate = rate
        self.volume = volume
        self.speech_queue = queue.Queue()
        self.is_running = False
        self.worker_thread = None
        
        # Initialize engine
        self._init_engine()
        
    def _init_engine(self):
        """Initialize the pyttsx3 engine with settings."""
        try:
            self.engine = pyttsx3.init()
            self.engine.setProperty('rate', self.rate)
            self.engine.setProperty('volume', self.volume)
            
            # Try to set a better voice if available
            voices = self.engine.getProperty('voices')
            if voices:
                # Prefer English voices
                for voice in voices:
                    if 'english' in voice.name.lower():
                        self.engine.setProperty('voice', voice.id)
                        break
            
            print(f"TTS Engine initialized (rate={self.rate}, volume={self.volume})")
            
        except Exception as e:
            print(f"ERROR: Failed to initialize TTS engine: {e}")
            print("Make sure pyttsx3 and espeak are installed:")
            print("  sudo apt-get install espeak")
            print("  pip3 install pyttsx3")
            self.engine = None
    
    def start(self):
        """Start the TTS worker thread."""
        if self.is_running:
            print("TTS engine already running")
            return
        
        if not self.engine:
            print("ERROR: Cannot start TTS - engine not initialized")
            return
        
        self.is_running = True
        self.worker_thread = threading.Thread(target=self._worker, daemon=True)
        self.worker_thread.start()
        print("TTS worker thread started")
    
    def stop(self):
        """Stop the TTS worker thread."""
        if not self.is_running:
            return
        
        self.is_running = False
        # Add sentinel to wake up worker
        self.speech_queue.put(None)
        
        if self.worker_thread:
            self.worker_thread.join(timeout=2.0)
        
        print("TTS worker thread stopped")
    
    def _worker(self):
        """Worker thread that processes speech queue."""
        while self.is_running:
            try:
                # Get text from queue with timeout
                text = self.speech_queue.get(timeout=0.5)
                
                # Check for sentinel (stop signal)
                if text is None:
                    break
                
                # Speak the text
                try:
                    print(f"[TTS Speaking]: {text}")
                    self.engine.say(text)
                    self.engine.runAndWait()
                except Exception as e:
                    print(f"Error speaking text: {e}")
                
                self.speech_queue.task_done()
                
            except queue.Empty:
                # No text to speak, continue waiting
                continue
            except Exception as e:
                print(f"Error in TTS worker: {e}")
    
    def speak(self, text: str, interrupt: bool = False):
        """
        Add text to speech queue.
        
        Args:
            text: Text to speak
            interrupt: If True, clear queue and speak immediately
        """
        if not text or not text.strip():
            return
        
        if not self.engine:
            print(f"[TTS Disabled]: {text}")
            return
        
        if not self.is_running:
            print("WARNING: TTS engine not running. Call start() first.")
            print(f"[TTS Queued]: {text}")
            return
        
        # Clear queue if interrupting
        if interrupt:
            self.clear_queue()
        
        # Add to queue
        self.speech_queue.put(text)
    
    def speak_now(self, text: str):
        """
        Speak text immediately without queuing (blocking call).
        
        Args:
            text: Text to speak
        """
        if not text or not text.strip():
            return
        
        if not self.engine:
            print(f"[TTS Disabled]: {text}")
            return
        
        try:
            print(f"[TTS Speaking Now]: {text}")
            self.engine.say(text)
            self.engine.runAndWait()
        except Exception as e:
            print(f"Error speaking text: {e}")
    
    def clear_queue(self):
        """Clear all pending speech from queue."""
        while not self.speech_queue.empty():
            try:
                self.speech_queue.get_nowait()
                self.speech_queue.task_done()
            except queue.Empty:
                break
        print("TTS queue cleared")
    
    def is_speaking(self) -> bool:
        """Check if currently speaking or has queued speech."""
        return not self.speech_queue.empty()
    
    def set_rate(self, rate: int):
        """
        Set speech rate.
        
        Args:
            rate: Words per minute (typical range: 100-250)
        """
        self.rate = rate
        if self.engine:
            self.engine.setProperty('rate', rate)
            print(f"TTS rate set to {rate} WPM")
    
    def set_volume(self, volume: float):
        """
        Set volume level.
        
        Args:
            volume: Volume level (0.0 to 1.0)
        """
        self.volume = max(0.0, min(1.0, volume))
        if self.engine:
            self.engine.setProperty('volume', self.volume)
            print(f"TTS volume set to {self.volume}")
    
    def __del__(self):
        """Cleanup when object is destroyed."""
        self.stop()


# Test utility
if __name__ == "__main__":
    print("Testing TTS Engine...")
    
    tts = TTSEngine(rate=150)
    tts.start()
    
    # Test speech
    tts.speak("NaviGlass Text to Speech Engine initialized")
    tts.speak("Testing one, two, three")
    
    # Wait for speech to complete
    time.sleep(5)
    
    # Test immediate speech
    tts.speak_now("This is immediate speech")
    
    # Cleanup
    tts.stop()
    print("TTS test complete")
