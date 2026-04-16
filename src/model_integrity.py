"""
Model Integrity Checker
Verifies cryptographic hashes of ML models before loading
Prevents model poisoning attacks
"""

import hashlib
import json
from pathlib import Path
from typing import Dict, Optional
from loguru import logger


class ModelIntegrityError(Exception):
    """Raised when model integrity check fails"""
    pass


class ModelIntegrityChecker:
    """
    Verifies SHA-256 hashes of ML models before loading.
    Prevents model poisoning by ensuring models haven't been tampered with.
    """
    
    def __init__(self, hashes_file: Optional[str] = None):
        """
        Initialize integrity checker
        
        Args:
            hashes_file: Path to JSON file containing model hashes
        """
        self.hashes_file = Path(hashes_file) if hashes_file else None
        self.hashes: Dict[str, str] = {}
        self._load_hashes()
    
    def _load_hashes(self):
        """Load model hashes from file"""
        if self.hashes_file and self.hashes_file.exists():
            try:
                with open(self.hashes_file, 'r') as f:
                    self.hashes = json.load(f)
                logger.info(f"Loaded {len(self.hashes)} model hashes from {self.hashes_file}")
            except Exception as e:
                logger.warning(f"Could not load model hashes: {e}")
                self.hashes = {}
    
    def compute_hash(self, file_path: Path) -> str:
        """
        Compute SHA-256 hash of a file
        
        Args:
            file_path: Path to file
            
        Returns:
            Hex digest of SHA-256 hash
        """
        sha256_hash = hashlib.sha256()
        
        with open(file_path, 'rb') as f:
            # Read in chunks to handle large files
            for chunk in iter(lambda: f.read(8192), b""):
                sha256_hash.update(chunk)
        
        return sha256_hash.hexdigest()
    
    def verify(self, model_path: Path) -> bool:
        """
        Verify model integrity against stored hash
        
        Args:
            model_path: Path to model file
            
        Returns:
            True if hash matches or no hash stored (warning)
            
        Raises:
            ModelIntegrityError: If hash doesn't match (tampering detected)
        """
        model_name = model_path.name
        
        # If no hashes configured, allow but warn
        if not self.hashes:
            logger.warning(f"No integrity hashes configured for {model_name} - skipping verification")
            return True
        
        expected_hash = self.hashes.get(model_name)
        
        # If no hash for this model, allow but warn
        if not expected_hash:
            logger.warning(f"No hash configured for {model_name} - skipping verification")
            return True
        
        # Compute actual hash
        try:
            actual_hash = self.compute_hash(model_path)
        except Exception as e:
            raise ModelIntegrityError(f"Failed to compute hash for {model_name}: {e}")
        
        # Verify
        if actual_hash != expected_hash:
            logger.error(f"Model integrity check FAILED for {model_name}")
            logger.error(f"Expected: {expected_hash}")
            logger.error(f"Actual:   {actual_hash}")
            raise ModelIntegrityError(
                f"Model {model_name} has been tampered with! "
                f"Expected hash {expected_hash[:16]}..., got {actual_hash[:16]}..."
            )
        
        logger.info(f"Model integrity verified: {model_name}")
        return True
    
    def generate_hashes(self, models_dir: Path, output_file: Optional[str] = None) -> Dict[str, str]:
        """
        Generate hashes for all models in directory
        Useful for initial setup
        
        Args:
            models_dir: Directory containing model files
            output_file: Optional path to save hashes JSON
            
        Returns:
            Dictionary of model names to hashes
        """
        hashes = {}
        
        # Supported model extensions
        extensions = ['.json', '.txt', '.pkl', '.joblib', '.model']
        
        for ext in extensions:
            for model_file in models_dir.rglob(f'*{ext}'):
                if model_file.is_file():
                    model_name = model_file.name
                    file_hash = self.compute_hash(model_file)
                    hashes[model_name] = file_hash
                    logger.info(f"Generated hash for {model_name}: {file_hash[:16]}...")
        
        # Save to file if requested
        if output_file:
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w') as f:
                json.dump(hashes, f, indent=2)
            logger.info(f"Saved hashes to {output_path}")
        
        return hashes


def create_integrity_checker(config_path: str = "config/config.yaml") -> ModelIntegrityChecker:
    """
    Factory function to create integrity checker from config
    
    Args:
        config_path: Path to configuration file
        
    Returns:
        Configured ModelIntegrityChecker instance
    """
    import os
    
    # Check for hashes file in standard locations
    hashes_locations = [
        "models/hashes.json",
        "models/production/hashes.json",
        os.getenv("MODEL_HASHES_FILE", ""),
    ]
    
    hashes_file = None
    for location in hashes_locations:
        if location and Path(location).exists():
            hashes_file = location
            break
    
    return ModelIntegrityChecker(hashes_file)
