import socket
import time
import json
import os
from zeroconf import ServiceBrowser, Zeroconf, ServiceListener
from crypto.crypto import TransferCrypto
from network.network import send_msg, recv_msg



class DofileListener(ServiceListener):
    def __init__(self) -> None:
        self.found_service = None
        
    def add_service(self, zc, type_, name):
        info = zc.get_service_info(type_, name)
        if info:
            self.found_service = (socket.inet_ntoa(info.addresses[0]), info.port, name)
            def update_service(self, zc, type_, name): pass
            def remove_service(self, zc, type_, name): pass
            
    
def run_importer(import_dir: str):
    print("searching for host")
    zeroconf =Zeroconf()
    listener = DofileListener()
    browser = ServiceBrowser(zeroconf, "_dotfiles._tcp.local.", listener)
    
    timeout = 10
    while not listener.found_service and timeout > 0:
        time.sleep(1)
        timeout -= 1
    zeroconf.close()
    
    if not listener.found_service:
        return print("No hosts found")
    
    ip, port, name = listener.found_service
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((ip,port))
    
    
    try:
        crypto = TransferCrypto()
        remote_pub = recv_msg(sock)
        send_msg(sock, crypto.get_public_key_bytes())
        
        pin = input(f"connected to {name}, enter PIN: ").strip()
        crypto.establish_session(remote_pub, pin)
        
        
        #Ask for mapping (LIST)
        req_list = json.dumps({"action": "LIST"}).encode("utf-8")
        send_msg(sock, crypto.encrypt(req_list))
        
        
        response = json.loads(crypto.decrypt(recv_msg(sock)).decode('utf-8'))
        available_files = response.get("files",[])
        print(f"\nHost exposed {len(available_files)} files: {available_files}")
        
        
        os.makedirs(import_dir, exist_ok=True)
        
        for file_key in available_files:
            print(f"fetching {file_key}...")
            req_get = json.dumps({"action": "GET","path": file_key}).encode('utf-8')
            
            file_data = crypto.decrypt(recv_msg(sock))
            
            
            if file_data.startswith(b"ERROR"):
                print(f"failed to fetch {file_key}: {file_data.decode()}")
                continue
            
            save_path = os.path.join(import_dir, file_key)
            with open(save_path, "wb") as f:
                f.write(file_data)
                
        print("\nImport Complete")
        
        
    finally:
        sock.close()
        
if __name__ == "__main__":
    run_importer("./imported_dotfiles")