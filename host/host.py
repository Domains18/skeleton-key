import socket
import secrets
import json
import os
from zeroconf import ServiceInfo, Zeroconf
from crypto.crypto import TransferCrypto
from network.network import recv_msg, send_msg


def scan_pc_for_dotfiles()-> list[str]:
    """scans the pc for dotfiles and returns a list of file paths"""
    dotfiles = []
    home_dir = os.path.expanduser("~")
    for root, dirs, files in os.walk(home_dir):
        for file in files:
            if file.startswith("."):
                dotfiles.append(os.path.join(root, file))
    return dotfiles


def scan_file_structure()-> dict:
    """
    Scans exposed directory structure for the new pc to copy. 
    specifically look for Documents-> github child directory and return a list of files and directories to copy. adjust your search path as needed.
    """
    
    home_dir = os.path.expanduser("~")
    target_dir = os.path.join(home_dir, "Documents", "github")
    file_structure = {}
    
    for root, dirs, files in os.walk(target_dir):
        relative_root = os.path.relpath(root, target_dir)
        file_structure[relative_root] = {
            "dirs": dirs,
            "files": files
        }
        
        """
        TODO: Implement a more sophisticated file structure scanning mechanism, automatically identify larger files like node_modules and exclude them from the transfer list. This will help in optimizing the transfer process and avoid unnecessary data transfer. if the file is too large, just resolve the project github domain and clone the repo instead of transferring the entire node_modules directory. This will save time and bandwidth during the transfer process. 
        """
        
    
    return file_structure

def start_host():
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.bind(('0.0.0.0', 0))  # Bind to an available port
    server_sock.listen(1)
    port = server_sock.getsockname()[1]
    
    
    hostname = socket.gethostname()
    info = ServiceInfo(
        "_dotfiletransfer._tcp.local.",
        f"{hostname}._dotfiletransfer._tcp.local.",
        addresses=[socket.inet_aton(socket.gethostbyname(hostname))],
        port=port,
        properties={},
        server=f"{hostname}.local.",
    )
    
    zeroconf = Zeroconf()
    zeroconf.register_service(info)
    print(f"Service registered: {hostname} on port {port}")
    pin=str(secrets.randbelow(1000000)).zfill(6)  # Generate a random 6-digit PIN
    
    
    try:
        conn, addr = server_sock.accept()
        print(f"Authentication request from {addr}")
        print(f"Pairing pin: {pin}")
        crypto = TransferCrypto()
        send_msg(conn, crypto.get_public_key_bytes())
        crypto.establish_session(recv_msg(conn), pin)
        print("Secure session established. waiting for client request...")
        
        # command loop
        while True:
            try:
                encrypted_req = recv_msg(conn)
                if not encrypted_req:
                    print("Client disconnected.")
                    break
                
                req = json.loads(crypto.decrypt(encrypted_req).decode('utf-8'))
                if req.get("action") == "LIST:DOTFILES":
                    response_data = json.dumps(scan_pc_for_dotfiles()).encode('utf-8')
                    send_msg(conn, crypto.encrypt(response_data))
                elif req.get("action") == "LIST:FILE_STRUCTURE":
                    response_data = json.dumps(scan_file_structure()).encode('utf-8')
                    send_msg(conn, crypto.encrypt(response_data))
                else:
                    send_msg(conn, crypto.encrypt(b"Unknown action or unauthorized request"))
            except Exception as e:
                print(f"Error processing request: {e}")
                break
    finally:
        zeroconf.unregister_service(info)
        zeroconf.close()
        server_sock.close()
        

if __name__== "__main__":
    start_host()