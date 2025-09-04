import socket
import threading

clients = []

def handle_client(conn, addr):
    uname = conn.recv(1024).decode('utf-8')
    print(f'{uname} {addr} csatlakozott.')
    broadcast(f'{uname} {addr} csatlakozott.', conn)

    while True:
        try:
            message = uname + ": " + conn.recv(1024).decode('utf-8')
            if not message:
                break
            print(f"{message}")
            broadcast(message, conn)
        except:
            break

    conn.close()
    clients.remove(conn)
    print(f'{uname} {addr} lecsatlakozott.')
    broadcast(f'{uname} {addr} lecsatlakozott.', conn)

def broadcast(message, connection=None):
    for client in clients:
        if client != connection:
            try:
                client.send(message.encode('utf-8'))
            except:
                client.close()
                clients.remove(client)

# def server_send_messages():
#     while True:
#         message = input("Szerver (te): ")
#         broadcast(f"{message}")

def start_server():
    host = '0.0.0.0'
    port = 7777
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((host, port))
    server_socket.listen()

    print(f"########## Szerver állapot ##########\nSzerver cím: {host}\nSzerver port: {port}\n#####################################")

    # threading.Thread(target=server_send_messages).start()

    while True:
        conn, addr = server_socket.accept()
        clients.append(conn)
        thread = threading.Thread(target=handle_client, args=(conn, addr))
        thread.start()

start_server()