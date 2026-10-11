import socket
import struct

def send_msg(sock: socket.socket, msg: bytes) -> None:
    """
    Prefixes the message with a 4-byte length header and sends it.
    
    Args:
        sock: The active TCP socket.
        msg: The raw bytes to send (usually an encrypted payload).
    """
    # '>I' formats the length as a 4-byte unsigned integer in big-endian (network) byte order
    msg_length = len(msg)
    encoded_length = struct.pack('>I', msg_length)
    
    # sendall ensures the entire buffer is sent even if network buffers are full
    sock.sendall(encoded_length + msg)


def recv_msg(sock: socket.socket) -> bytes:
    """
    Reads the 4-byte length header, then reads exactly that many bytes from the socket.
    
    Returns:
        The exact byte payload sent by the other side.
        
    Raises:
        ConnectionError: If the socket closes mid-transfer or before reading.
    """
    # Read the 4-byte length header
    raw_msglen = _recvall(sock, 4)
    if not raw_msglen:
        raise ConnectionError("Socket closed gracefully by the other end.")
    
    # Unpack the 4 bytes back into an integer
    msglen = struct.unpack('>I', raw_msglen)[0]
    
    # Read exactly 'msglen' bytes for the actual payload
    data = _recvall(sock, msglen)
    if not data:
        raise ConnectionError(f"Socket closed unexpectedly while expecting {msglen} bytes.")
        
    return data


def _recvall(sock: socket.socket, n: int) -> bytes | None:
    """
    Helper function to reliably read exactly n bytes from the socket.
    `socket.recv()` is not guaranteed to return all requested bytes at once,
    especially for large files, so we loop until we have everything.
    """
    data = bytearray()
    while len(data) < n:
        # Ask for the remaining bytes we need
        packet = sock.recv(n - len(data))
        
        # If recv returns an empty byte string, the connection was closed
        if not packet:
            return None
            
        data.extend(packet)
        
    return bytes(data)