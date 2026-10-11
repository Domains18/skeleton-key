"""discovers HOST netwrk and the device to import the configurations and files from"""
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives import serialization

"""_summary_
    1. key exhanges;
    the old pc and the new pc will generate a shared secret key using the X25519 algorithm. This key will be used to encrypt and decrypt the data during the transfer process.
    2. key derivation;
    the shared secret key will be used to derive a symmetric encryption key using the HKDF (HMAC-based Key Derivation Function) with SHA-256 as the hash function. This derived key will be used for encrypting and decrypting the data.
    3. data encryption;
    the data to be transferred will be encrypted using the AES-GCM (Advanced Encryption Standard in Galois/Counter Mode) algorithm with the derived symmetric key. AES-GCM provides both confidentiality and integrity for the encrypted data.
"""
class TransferCrypto:
    """handles stateful Ephemeral ECDH key exchange and AES-GCM encruption for a pc to pc dotfile transfer"""
    
    def __init__(self):
        # Generate a private key for the X25519 algorithm
        self._private_key = x25519.X25519PrivateKey.generate()
        self._aesgcm: AESGCM | None = None
        
        
    def get_public_key_bytes(self)-> bytes:
        public_key = self._private_key.public_key()
        return public_key.public_bytes(encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw)
    
    def establish_session(self, remote_public_bytes: bytes, pin: str) -> None:
        if len(remote_public_bytes) != 32:
            raise ValueError("Invalid remote public key length")
        remote_pub_key = x25519.X25519PublicKey.from_public_bytes(remote_public_bytes)
        shared_secret = self._private_key.exchange(remote_pub_key)
        
        hkdf = HKDF(algorithm=hashes.SHA256(), length=32, salt=pin.encode('utf-8'), info="dotfile_transfer".encode('utf-8'))
        
        derived_key = hkdf.derive(shared_secret)
        self._aesgcm = AESGCM(derived_key)
        
        
    def encrypt(self, plaintext: bytes) -> bytes:
        if not self._aesgcm:
            raise ValueError("Session not established. Call establish_session first.")
        nonce = os.urandom(12)
        # AESGCM appends the 16 byte authentication tag to the ciphertext
        ciphertext = self._aesgcm.encrypt(nonce, plaintext, None)
        return nonce + ciphertext  # Prepend nonce to the ciphertext for transmission
    
    
    def decrypt(self, encrypted_data: bytes) -> bytes:
        if not self._aesgcm:
            raise ValueError("Session not established. Call establish_session first.")
        
        if len(encrypted_data) < 28:
            raise ValueError("Invalid encrypted data length")
        nonce = encrypted_data[:12]
        ciphertext = encrypted_data[12:]
        return self._aesgcm.decrypt(nonce, ciphertext, associated_data=None)