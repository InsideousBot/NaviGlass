"""
Face Recognition Database for NaviGlass
Manages known faces with encodings stored in JSON format.
"""

import json
import os
import numpy as np
from typing import Optional, List, Dict, Tuple
from datetime import datetime
import face_recognition


class FaceDatabase:
    """Manages a database of known faces for recognition."""
    
    def __init__(self, db_path: str = "faces_database.json"):
        """
        Initialize face database.
        
        Args:
            db_path: Path to JSON database file
        """
        self.db_path = db_path
        self.faces = []  # List of {name, encoding, date_added}
        self.load()
    
    def load(self) -> bool:
        """
        Load face database from JSON file.
        
        Returns:
            True if loaded successfully, False otherwise
        """
        if not os.path.exists(self.db_path):
            print(f"Database file not found: {self.db_path}")
            print("Creating new database...")
            self.faces = []
            self.save()
            return True
        
        try:
            with open(self.db_path, 'r') as f:
                data = json.load(f)
            
            # Convert encoding lists back to numpy arrays
            self.faces = []
            for face in data.get('faces', []):
                self.faces.append({
                    'name': face['name'],
                    'encoding': np.array(face['encoding']),
                    'date_added': face.get('date_added', 'Unknown')
                })
            
            print(f"Loaded {len(self.faces)} face(s) from database")
            return True
            
        except Exception as e:
            print(f"Error loading database: {e}")
            self.faces = []
            return False
    
    def save(self) -> bool:
        """
        Save face database to JSON file.
        
        Returns:
            True if saved successfully, False otherwise
        """
        try:
            # Convert numpy arrays to lists for JSON serialization
            data = {
                'faces': [],
                'version': '1.0'
            }
            
            for face in self.faces:
                data['faces'].append({
                    'name': face['name'],
                    'encoding': face['encoding'].tolist(),
                    'date_added': face.get('date_added', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                })
            
            with open(self.db_path, 'w') as f:
                json.dump(data, f, indent=2)
            
            print(f"Saved {len(self.faces)} face(s) to database")
            return True
            
        except Exception as e:
            print(f"Error saving database: {e}")
            return False
    
    def add_face(self, name: str, image_path: Optional[str] = None, 
                 image_array: Optional[np.ndarray] = None) -> bool:
        """
        Add a new face to the database.
        
        Args:
            name: Name of the person
            image_path: Path to image file (optional if image_array provided)
            image_array: Numpy array of image (optional if image_path provided)
            
        Returns:
            True if face added successfully, False otherwise
        """
        if not name or not name.strip():
            print("ERROR: Name cannot be empty")
            return False
        
        # Check if name already exists
        if self.get_face_by_name(name):
            print(f"ERROR: Face with name '{name}' already exists")
            return False
        
        # Load image
        if image_array is not None:
            image = image_array
        elif image_path and os.path.exists(image_path):
            image = face_recognition.load_image_file(image_path)
        else:
            print("ERROR: Must provide either image_path or image_array")
            return False
        
        # Find face encodings
        face_encodings = face_recognition.face_encodings(image)
        
        if len(face_encodings) == 0:
            print("ERROR: No face detected in image")
            return False
        
        if len(face_encodings) > 1:
            print(f"WARNING: Multiple faces detected ({len(face_encodings)}), using first one")
        
        # Add to database
        self.faces.append({
            'name': name,
            'encoding': face_encodings[0],
            'date_added': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        
        # Save to file
        if self.save():
            print(f"Successfully added face: {name}")
            return True
        else:
            # Remove from memory if save failed
            self.faces.pop()
            return False
    
    def remove_face(self, name: str) -> bool:
        """
        Remove a face from the database.
        
        Args:
            name: Name of the person to remove
            
        Returns:
            True if removed successfully, False otherwise
        """
        original_count = len(self.faces)
        self.faces = [f for f in self.faces if f['name'] != name]
        
        if len(self.faces) < original_count:
            self.save()
            print(f"Removed face: {name}")
            return True
        else:
            print(f"Face not found: {name}")
            return False
    
    def get_face_by_name(self, name: str) -> Optional[Dict]:
        """
        Get face data by name.
        
        Args:
            name: Name of the person
            
        Returns:
            Face dictionary or None if not found
        """
        for face in self.faces:
            if face['name'] == name:
                return face
        return None
    
    def find_match(self, face_encoding: np.ndarray, 
                   tolerance: float = 0.6) -> Optional[Tuple[str, float]]:
        """
        Find matching face in database.
        
        Args:
            face_encoding: Face encoding to match
            tolerance: Distance tolerance (lower = stricter), default 0.6
            
        Returns:
            Tuple of (name, distance) if match found, None otherwise
        """
        if len(self.faces) == 0:
            return None
        
        # Get all known encodings
        known_encodings = [f['encoding'] for f in self.faces]
        known_names = [f['name'] for f in self.faces]
        
        # Calculate face distances
        face_distances = face_recognition.face_distance(known_encodings, face_encoding)
        
        # Find best match
        best_match_index = np.argmin(face_distances)
        best_distance = face_distances[best_match_index]
        
        if best_distance <= tolerance:
            return (known_names[best_match_index], best_distance)
        
        return None
    
    def recognize_faces(self, image_array: np.ndarray, 
                       tolerance: float = 0.6) -> List[Tuple[str, float]]:
        """
        Recognize all faces in an image.
        
        Args:
            image_array: Numpy array of image
            tolerance: Distance tolerance (lower = stricter)
            
        Returns:
            List of tuples (name, distance) for recognized faces
        """
        # Find all face encodings in image
        face_encodings = face_recognition.face_encodings(image_array)
        
        results = []
        for encoding in face_encodings:
            match = self.find_match(encoding, tolerance)
            if match:
                results.append(match)
        
        return results
    
    def list_faces(self) -> List[str]:
        """
        Get list of all known face names.
        
        Returns:
            List of names
        """
        return [f['name'] for f in self.faces]
    
    def count(self) -> int:
        """Get number of faces in database."""
        return len(self.faces)
    
    def clear(self) -> bool:
        """
        Clear all faces from database.
        
        Returns:
            True if cleared successfully
        """
        self.faces = []
        return self.save()


# Command-line utility for testing
if __name__ == "__main__":
    import sys
    
    db = FaceDatabase()
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "list":
            # List all faces
            faces = db.list_faces()
            print(f"Database contains {len(faces)} face(s):")
            for name in faces:
                face = db.get_face_by_name(name)
                print(f"  - {name} (added: {face.get('date_added', 'Unknown')})")
        
        elif command == "add" and len(sys.argv) >= 4:
            # Add face
            name = sys.argv[2]
            image_path = sys.argv[3]
            db.add_face(name, image_path=image_path)
        
        elif command == "remove" and len(sys.argv) >= 3:
            # Remove face
            name = sys.argv[2]
            db.remove_face(name)
        
        elif command == "clear":
            # Clear database
            if db.clear():
                print("Database cleared")
        
        else:
            print("Usage:")
            print("  python3 face_database.py list")
            print("  python3 face_database.py add <name> <image_path>")
            print("  python3 face_database.py remove <name>")
            print("  python3 face_database.py clear")
    else:
        print("Usage:")
        print("  python3 face_database.py list")
        print("  python3 face_database.py add <name> <image_path>")
        print("  python3 face_database.py remove <name>")
        print("  python3 face_database.py clear")
