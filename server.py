import socket
import threading
import datetime
import time
import os
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa

clients = {}
v_clients = {}

BUF_SIZE = 4096

def exchange_key(conn):
    client_pub_pem = conn.recv(4096)
    client_public_key = serialization.load_pem_public_key(client_pub_pem)
    session_key = Fernet.generate_key()
    cipher = Fernet(session_key)
    encrypted_session_key = client_public_key.encrypt(session_key,padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()),algorithm=hashes.SHA256(),label=None))
    conn.send(encrypted_session_key)
    return cipher

def log_handler(message, print_b=True):
    if os.path.exists("logs"):
        pass
    else:
        os.system("mkdir logs")
    with open(f'logs/log{date}.txt', 'a+', encoding='utf-8') as log:
        if print_b == True:
            print(f"{str(message)}")
        log.write(f"{str(message)}\n")
        # return log

def handle_client(conn, addr):
    try:
        cipher = exchange_key(conn)
        encrypted_uname = conn.recv(4096)
        uname = cipher.decrypt(encrypted_uname).decode("utf-8")
        clients[conn] = {"addr": addr, "cipher": cipher, "uname": uname}
        broadcast(f"{uname} {addr} csatlakozott.", conn)
        log_handler(f"{uname} {addr} csatlakozott.")
        # with open(f'msg_log{date}.txt', 'r', encoding='utf-8') as log:
        #     for i in log.readlines():
        #         broadcast(i, conn)

        while True:
            encrypted_msg = conn.recv(4096)
            if not encrypted_msg:
                break

            message = cipher.decrypt(encrypted_msg).decode("utf-8")
            formatted = f"{uname}: {message}"
            broadcast(formatted, conn)
            log_handler(formatted)

    except Exception as e:
        try:
            if str(e.split(" ")[1].strip("]")) == "10053":
                log_handler(f"Sikeresen lezárult a kapcsolat a következővel: {addr}")
        except AttributeError as e2:
            log_handler(e2)

    finally:
        if conn in clients:
            uname = clients[conn]["uname"]
            broadcast(f"{uname} {addr} lecsatlakozott.", conn)
            log_handler(f"{uname} {addr} lecsatlakozott.")
            del clients[conn]
            conn.close()

def handle_packets(server):
    while voice:
        try:
            data, addr = server.recvfrom(BUF_SIZE)

            if data.startswith(b"REGISTER:"):
                uname = data.split(b":", 1)[1].decode("utf-8", errors="ignore")
                v_clients[addr] = uname
                log_handler(f"VoIP client registered: {uname} {addr}")
                continue

            if addr not in v_clients:
                continue

            for caddr in list(v_clients.keys()):
                print(caddr)
                if caddr == addr:
                    continue
                try:
                    server.sendto(data, caddr)
                except OSError as e:
                    log_handler(e, False)
                    del v_clients[caddr]
        except OSError as e:
            log_handler(e, False)

def broadcast(message, connection=None):
    for client, info in list(clients.items()):
        if client != connection:
            try:
                encrypted_msg = info["cipher"].encrypt(message.encode("utf-8"))
                client.send(encrypted_msg)
            except:
                client.close()
                del clients[client]

def connection_thread(ts):
    while True:
        try:
            conn, addr = ts.accept()
            text_server = threading.Thread(target=handle_client, args=(conn, addr))
            text_server.start()
        except OSError as e:
            log_handler(e, False)
            time.sleep(1)
            break

def console_thread(vs, ts, host, port, vport):
    global voice
    voice = False
    while True:
        try:
            cmd = input("cord-server> ").strip().lower()
            log_handler(cmd, False)
            if cmd.startswith("voice"):
                try:
                    if cmd.split(" ")[1] == "start":
                        voice = True
                        voice_server = threading.Thread(target=handle_packets,args=(vs,), daemon=True)
                        voice_server.start()
                    elif cmd.split(" ")[1] == "stop":
                        voice = False
                        vs.close()
                        log_handler("Hanghívás leállítva.")
                    elif cmd.split(" ")[1] == "kick":
                        target = cmd.split(" ", 1)[2]
                        if len(cmd.split(" ")) > 3:
                            reason = "\nIndok: ",cmd.split(" ")[3:]
                        else:
                            reason = ""
                        for addr,uname in list(v_clients.items()):
                            if uname == target or f"{addr[0]}:{addr[1]}" == target:
                                del v_clients[addr]
                                log_handler(f"kicked {addr} {uname}{reason}")
                except IndexError:
                    log_handler("voice start - Hívás indítása\nvoice stop - Hívás leállítása\nvoice kick <név> <indok (ha van)>")
            elif cmd == "list":
                for addr, uname in clients.items():
                    log_handler(f"{uname} {addr}")
            elif cmd == "status":
                log_handler(f"IP: {host}\nPort: {port}")
                if voice:
                    log_handler(f"VoIP: Fut\nPort: {vport}")
                else:
                    log_handler("VoIP: Nem fut (start voice paranccsal indítható)")
            elif cmd.startswith("kick "):
                target = cmd.split(" ", 1)[1]
                if len(cmd.split(" ")) > 2:
                    reason = "\nIndok: ",cmd.split(" ")[3:]
                else:
                    reason = ""
                for client,uname in list(clients.items()):
                    if uname['uname'] == target or uname['addr'][0].strip("'") == target:
                        log_handler(f"kicked {uname['addr']} {uname['uname']} {reason}")
                        client.close()
            elif cmd in ("stop", "quit", "exit"):
                log_handler("Szerver leállítása.")
                try:
                    vs.close()
                except OSError as e:
                    log_handler(e, False)
                    continue
                ts.close()
                break
        except OSError as e:
            log_handler(e, False)
            time.sleep(1)
            break

def start_server():
    global date
    date = datetime.datetime.now().strftime("_%Y%m%d_%H%M%S")
    HOST = "0.0.0.0"
    PORT = 7777
    VPORT = 9700
    text_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    voice_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    text_socket.bind((HOST, PORT))
    voice_socket.bind((HOST, VPORT))
    text_socket.listen()

    log_handler("A szerver elindult!\nHasználd a status parancsot egyéb információkért!", True)

    threading.Thread(target=connection_thread,args=(text_socket,), daemon=True).start()
    threading.Thread(target=console_thread,args=(voice_socket,text_socket, HOST, PORT, VPORT)).start()

start_server()