# ============================================================
# security.py — Password encryption utilities
# ============================================================
# Uses Fernet symmetric encryption from the cryptography library.
# 
# How it works:
# - encrypt_password() takes a plain text password and returns
#   an encrypted string that's safe to store in the database
# - decrypt_password() takes the encrypted string and returns
#   the original password (only when we need to connect)
#
# The encryption key is loaded from config.py.
# Without the key, encrypted passwords cannot be decrypted.
# ============================================================

from cryptography.fernet import Fernet
from app.core.config import ENCRYPTION_KEY


# Create a Fernet cipher object using our encryption key
# This is created once and reused for all encrypt/decrypt operations
cipher = Fernet(ENCRYPTION_KEY.encode())


def encrypt_password(plain_password: str) -> str:
    """
    Encrypt a plain text password.
    
    Example:
        encrypt_password("admin123") 
        → "gAAAAABh3X2YfQ4...rJK8="
    
    The encrypted string is safe to store in the database.
    Even if someone steals the database, they can't read passwords
    without the encryption key.
    """
    if not plain_password:
        return ""
    
    # Convert string to bytes, encrypt, then convert back to string
    encrypted_bytes = cipher.encrypt(plain_password.encode())
    return encrypted_bytes.decode()


def decrypt_password(encrypted_password: str) -> str:
    """
    Decrypt an encrypted password back to plain text.
    
    Only called when we need to actually connect to the user's database.
    The decrypted password is held in memory briefly and never stored.
    
    Example:
        decrypt_password("gAAAAABh3X2YfQ4...rJK8=") 
        → "admin123"
    """
    if not encrypted_password:
        return ""
    
    try:
        decrypted_bytes = cipher.decrypt(encrypted_password.encode())
        return decrypted_bytes.decode()
    except Exception as e:
        # If decryption fails (wrong key, corrupted data), return empty
        # This will cause the connection to fail safely
        return ""