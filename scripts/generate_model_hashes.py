#!/usr/bin/env python3
"""
Generate SHA-256 hashes for model files
Usage: python scripts/generate_model_hashes.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.model_integrity import ModelIntegrityChecker


def main():
    """Generate and save model hashes"""
    models_dir = Path("models/production")
    
    if not models_dir.exists():
        print(f"Models directory not found: {models_dir}")
        sys.exit(1)
    
    checker = ModelIntegrityChecker()
    
    print("Generating hashes for production models...")
    hashes = checker.generate_hashes(models_dir, output_file="models/hashes.json")
    
    print(f"\nGenerated {len(hashes)} model hashes:")
    for name, hash_value in hashes.items():
        print(f"  {name}: {hash_value[:16]}...")
    
    print(f"\nHashes saved to: models/hashes.json")
    print("\nTo enable strict verification, set STRICT_MODEL_INTEGRITY=true")


if __name__ == "__main__":
    main()
