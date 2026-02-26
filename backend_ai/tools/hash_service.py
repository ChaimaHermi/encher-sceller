import hashlib

def compute_hash(content: bytes):
    return hashlib.sha256(content).hexdigest()