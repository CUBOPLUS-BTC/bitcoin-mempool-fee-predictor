"""
Data Encryption at Rest for Mempool Snapshots
Implements Fernet symmetric encryption for sensitive data files.

Security: A02:2021 - Cryptographic Failures mitigation
"""

import os
import json
from pathlib import Path
from typing import Optional, Union
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import logging

logger = logging.getLogger(__name__)


class DataEncryptionManager:
    """
    Manages encryption for data at rest.
    
    Features:
    - Fernet symmetric encryption (AES-128-CBC with HMAC)
    - PBKDF2 key derivation from password
    - Automatic file extension detection (.encrypted)
    - Batch encryption/decryption support
    """
    
    def __init__(self, password: Optional[str] = None):
        """
        Initialize encryption manager.
        
        Args:
            password: Encryption password. If None, uses DATA_ENCRYPTION_KEY env var.
        """
        self.password = password or os.getenv("DATA_ENCRYPTION_KEY")
        self._cipher = None
        
        if self.password:
            self._cipher = self._create_cipher(self.password)
            logger.info("✓ Data encryption manager initialized")
        else:
            logger.warning("No encryption key provided - encryption disabled")
    
    def _create_cipher(self, password: str) -> Fernet:
        """Create Fernet cipher from password"""
        # Use PBKDF2 to derive key from password
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'mempool_fee_predictor_salt_v1',  # Fixed salt for key reproducibility
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return Fernet(key)
    
    def encrypt_file(self, filepath: Union[str, Path], output_path: Optional[Path] = None) -> Path:
        """
        Encrypt a file and save with .encrypted extension.
        
        Args:
            filepath: Path to file to encrypt
            output_path: Optional custom output path
            
        Returns:
            Path to encrypted file
        """
        if not self._cipher:
            raise ValueError("Encryption not initialized - set DATA_ENCRYPTION_KEY")
        
        filepath = Path(filepath)
        if not filepath.exists():
            raise FileNotFoundError(f"File not found: {filepath}")
        
        # Determine output path
        if output_path is None:
            output_path = filepath.with_suffix(filepath.suffix + ".encrypted")
        
        # Read and encrypt
        with open(filepath, 'rb') as f:
            data = f.read()
        
        encrypted = self._cipher.encrypt(data)
        
        # Write encrypted data with metadata header
        metadata = {
            "version": "1.0",
            "algorithm": "fernet-aes128",
            "original_filename": filepath.name,
            "encrypted_at": str(Path(__file__).stat().st_mtime if Path(__file__).exists() else 0)
        }
        
        with open(output_path, 'wb') as f:
            # Write metadata as JSON header (fixed 256 bytes)
            meta_bytes = json.dumps(metadata).encode()
            meta_padded = meta_bytes + b' ' * (256 - len(meta_bytes))
            f.write(meta_padded)
            f.write(encrypted)
        
        logger.info(f"✓ Encrypted {filepath} -> {output_path}")
        return output_path
    
    def decrypt_file(self, filepath: Union[str, Path], output_path: Optional[Path] = None) -> Path:
        """
        Decrypt a file and restore original.
        
        Args:
            filepath: Path to encrypted file
            output_path: Optional custom output path
            
        Returns:
            Path to decrypted file
        """
        if not self._cipher:
            raise ValueError("Encryption not initialized - set DATA_ENCRYPTION_KEY")
        
        filepath = Path(filepath)
        if not filepath.exists():
            raise FileNotFoundError(f"File not found: {filepath}")
        
        # Read encrypted data
        with open(filepath, 'rb') as f:
            # Skip metadata header (256 bytes)
            metadata_raw = f.read(256).strip()
            encrypted = f.read()
        
        # Decrypt
        decrypted = self._cipher.decrypt(encrypted)
        
        # Determine output path
        if output_path is None:
            # Remove .encrypted suffix
            output_path = filepath.with_suffix('')
            # Handle double extensions like .parquet.encrypted -> .parquet
            if output_path.suffix == '.encrypted':
                output_path = output_path.with_suffix('')
        
        with open(output_path, 'wb') as f:
            f.write(decrypted)
        
        logger.info(f"✓ Decrypted {filepath} -> {output_path}")
        return output_path
    
    def encrypt_directory(self, directory: Union[str, Path], pattern: str = "*.parquet") -> list[Path]:
        """
        Encrypt all files matching pattern in directory.
        
        Args:
            directory: Directory to scan
            pattern: File pattern to match (default: *.parquet)
            
        Returns:
            List of encrypted file paths
        """
        directory = Path(directory)
        if not directory.exists():
            logger.warning(f"Directory not found: {directory}")
            return []
        
        encrypted_files = []
        for filepath in directory.glob(pattern):
            if not str(filepath).endswith('.encrypted'):
                try:
                    enc_path = self.encrypt_file(filepath)
                    encrypted_files.append(enc_path)
                    # Remove original file after successful encryption
                    filepath.unlink()
                except Exception as e:
                    logger.error(f"Failed to encrypt {filepath}: {e}")
        
        logger.info(f"✓ Encrypted {len(encrypted_files)} files in {directory}")
        return encrypted_files
    
    def decrypt_directory(self, directory: Union[str, Path]) -> list[Path]:
        """
        Decrypt all .encrypted files in directory.
        
        Args:
            directory: Directory to scan
            
        Returns:
            List of decrypted file paths
        """
        directory = Path(directory)
        if not directory.exists():
            logger.warning(f"Directory not found: {directory}")
            return []
        
        decrypted_files = []
        for filepath in directory.glob("*.encrypted"):
            try:
                dec_path = self.decrypt_file(filepath)
                decrypted_files.append(dec_path)
                # Remove encrypted file after successful decryption
                filepath.unlink()
            except Exception as e:
                logger.error(f"Failed to decrypt {filepath}: {e}")
        
        logger.info(f"✓ Decrypted {len(decrypted_files)} files in {directory}")
        return decrypted_files
    
    def is_encrypted(self, filepath: Union[str, Path]) -> bool:
        """Check if file is encrypted by extension"""
        return str(filepath).endswith('.encrypted')
    
    def rotate_key(
        self,
        directory: Union[str, Path],
        new_password: str,
        old_password: Optional[str] = None
    ) -> list[Path]:
        """
        Re-encrypt all files with new key (key rotation).
        
        Args:
            directory: Directory containing encrypted files
            new_password: New encryption password
            old_password: Old password (if not using instance password)
            
        Returns:
            List of re-encrypted files
        """
        old_cipher = self._cipher
        if old_password:
            old_cipher = self._create_cipher(old_password)
        
        new_cipher = self._create_cipher(new_password)
        
        directory = Path(directory)
        reencrypted = []
        
        for filepath in directory.glob("*.encrypted"):
            try:
                # Decrypt with old key
                with open(filepath, 'rb') as f:
                    metadata_raw = f.read(256).strip()
                    encrypted = f.read()
                
                decrypted = old_cipher.decrypt(encrypted)
                
                # Re-encrypt with new key
                reencrypted_data = new_cipher.encrypt(decrypted)
                
                # Write back
                with open(filepath, 'wb') as f:
                    f.write(b' ' * 256)  # Empty metadata placeholder
                    f.write(reencrypted_data)
                
                reencrypted.append(filepath)
                logger.info(f"✓ Rotated key for {filepath}")
            except Exception as e:
                logger.error(f"Failed to rotate key for {filepath}: {e}")
        
        # Update instance cipher
        self.password = new_password
        self._cipher = new_cipher
        
        logger.info(f"✓ Key rotation complete: {len(reencrypted)} files")
        return reencrypted


# Global instance
encryption_manager = DataEncryptionManager()


def encrypt_snapshots(password: Optional[str] = None) -> list[Path]:
    """
    Convenience function to encrypt all snapshot files.
    
    Usage:
        export DATA_ENCRYPTION_KEY="your-secure-password"
        python -c "from src.data_encryption import encrypt_snapshots; encrypt_snapshots()"
    """
    manager = DataEncryptionManager(password)
    
    # Encrypt processed data
    data_dir = Path("data/processed")
    if data_dir.exists():
        manager.encrypt_directory(data_dir, "*.parquet")
        manager.encrypt_directory(data_dir, "*.csv")
    
    # Encrypt predictions
    pred_dir = Path("predictions")
    if pred_dir.exists():
        manager.encrypt_directory(pred_dir, "*.csv")
    
    return []


def decrypt_snapshots(password: Optional[str] = None) -> list[Path]:
    """Convenience function to decrypt all snapshot files"""
    manager = DataEncryptionManager(password)
    
    decrypted = []
    
    for directory in [Path("data/processed"), Path("predictions")]:
        if directory.exists():
            decrypted.extend(manager.decrypt_directory(directory))
    
    return decrypted


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Encrypt/decrypt mempool data files")
    parser.add_argument("action", choices=["encrypt", "decrypt", "status"])
    parser.add_argument("--dir", default="data/processed", help="Target directory")
    parser.add_argument("--password", help="Encryption password (or set DATA_ENCRYPTION_KEY)")
    
    args = parser.parse_args()
    
    if args.action == "encrypt":
        manager = DataEncryptionManager(args.password)
        files = manager.encrypt_directory(args.dir)
        print(f"Encrypted {len(files)} files")
    elif args.action == "decrypt":
        manager = DataEncryptionManager(args.password)
        files = manager.decrypt_directory(args.dir)
        print(f"Decrypted {len(files)} files")
    elif args.action == "status":
        directory = Path(args.dir)
        encrypted = list(directory.glob("*.encrypted"))
        print(f"Found {len(encrypted)} encrypted files in {directory}")
