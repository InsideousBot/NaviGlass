"""
Face Enrollment Script for NaviGlass
Interactive tool to add new faces to the database.
"""

import cv2
import time
from picamera2 import Picamera2
from face_database import FaceDatabase
import sys


def enroll_face_interactive():
    """Interactive face enrollment using Picamera2."""
    
    print("=" * 60)
    print("NaviGlass Face Enrollment")
    print("=" * 60)
    
    # Initialize database
    db = FaceDatabase()
    print(f"\nCurrent database: {db.count()} face(s)")
    
    # Get name
    name = input("\nEnter person's name: ").strip()
    if not name:
        print("ERROR: Name cannot be empty")
        return False
    
    # Check if name exists
    if db.get_face_by_name(name):
        print(f"ERROR: A face with name '{name}' already exists")
        choice = input("Do you want to replace it? (yes/no): ").strip().lower()
        if choice != 'yes':
            print("Enrollment cancelled")
            return False
        else:
            db.remove_face(name)
    
    # Initialize camera
    print("\nInitializing camera...")
    try:
        picam = Picamera2()
        config = picam.create_preview_configuration(main={'size': (640, 480), 'format': 'RGB888'})
        picam.configure(config)
        picam.start()
        print("Camera started")
        time.sleep(2)  # Let camera warm up
    except Exception as e:
        print(f"ERROR: Failed to initialize camera: {e}")
        return False
    
    print("\n" + "=" * 60)
    print("INSTRUCTIONS:")
    print("1. Position your face in front of the camera")
    print("2. Make sure lighting is good")
    print("3. Look directly at the camera")
    print("4. Press ENTER when ready to capture")
    print("=" * 60)
    
    input("\nPress ENTER when ready...")
    
    # Capture frames and show preview
    print("\nCapturing in 3... 2... 1...")
    time.sleep(1)
    
    try:
        # Capture photo
        frame = picam.capture_array()
        print("Photo captured!")
        
        # Stop camera
        picam.stop()
        
        # Add to database
        print(f"\nProcessing face for '{name}'...")
        if db.add_face(name, image_array=frame):
            print("\n" + "=" * 60)
            print(f"✓ SUCCESS! Face enrolled for: {name}")
            print("=" * 60)
            print(f"\nTotal faces in database: {db.count()}")
            print("Known faces:", ", ".join(db.list_faces()))
            return True
        else:
            print("\n" + "=" * 60)
            print("✗ FAILED to enroll face")
            print("=" * 60)
            print("Possible reasons:")
            print("  - No face detected in image")
            print("  - Multiple faces detected")
            print("  - Poor image quality or lighting")
            return False
            
    except Exception as e:
        print(f"\nERROR during enrollment: {e}")
        picam.stop()
        return False


def enroll_from_file(name: str, image_path: str):
    """Enroll a face from an image file."""
    
    print(f"Enrolling '{name}' from {image_path}")
    
    db = FaceDatabase()
    
    # Check if name exists
    if db.get_face_by_name(name):
        print(f"ERROR: A face with name '{name}' already exists")
        return False
    
    # Add face
    if db.add_face(name, image_path=image_path):
        print(f"✓ Successfully enrolled: {name}")
        return True
    else:
        print(f"✗ Failed to enroll: {name}")
        return False


def list_faces():
    """List all enrolled faces."""
    
    db = FaceDatabase()
    faces = db.list_faces()
    
    print("\n" + "=" * 60)
    print(f"Face Database ({db.count()} face(s))")
    print("=" * 60)
    
    if len(faces) == 0:
        print("No faces enrolled yet")
    else:
        for name in faces:
            face = db.get_face_by_name(name)
            date_added = face.get('date_added', 'Unknown')
            print(f"  • {name} (added: {date_added})")
    
    print("=" * 60)


def remove_face_interactive():
    """Interactive face removal."""
    
    db = FaceDatabase()
    
    # List faces first
    list_faces()
    
    if db.count() == 0:
        return
    
    name = input("\nEnter name to remove: ").strip()
    if not name:
        print("Cancelled")
        return
    
    if db.remove_face(name):
        print(f"✓ Removed: {name}")
    else:
        print(f"✗ Not found: {name}")


if __name__ == "__main__":
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "list":
            # List all faces
            list_faces()
        
        elif command == "add" and len(sys.argv) >= 4:
            # Add from file
            name = sys.argv[2]
            image_path = sys.argv[3]
            enroll_from_file(name, image_path)
        
        elif command == "remove":
            # Remove face
            remove_face_interactive()
        
        elif command == "interactive" or command == "enroll":
            # Interactive enrollment
            enroll_face_interactive()
        
        else:
            print("Usage:")
            print("  python3 enroll_face.py interactive    # Interactive enrollment with camera")
            print("  python3 enroll_face.py add <name> <image_path>")
            print("  python3 enroll_face.py remove")
            print("  python3 enroll_face.py list")
    else:
        # Default to interactive
        enroll_face_interactive()
