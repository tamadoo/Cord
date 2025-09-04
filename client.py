import socket
import threading

# def config():
#     with open("client_config.ini", "r", encoding="utf-8") as f:
#         pass

def receive_messages(client_socket):
    while True:
        try:
            message = client_socket.recv(1024).decode("utf-8")
            if not message:
                break
            print(f"{message}")
        except:
            print("\nKapcsolat megszakadt a szerverrel.")
            client_socket.close()
            exit()
            break
            

def send_messages(client_socket):
    uname = input("Felh. név: ")
    client_socket.send(uname.encode("utf-8"))

    while True:
        message = input()
        try:
            client_socket.send(message.encode("utf-8"))
        except:
            print("\nNem sikerült elküldeni az üzenetet.")
            break

def start_client():
    host = input("Szerver IP címe: ")
    port = int(input("Szerver port: "))

    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    while 1:
        try:
            client_socket.connect((host, port))
            break
        except Exception as e:
            print(f"Nem sikerült csatlakozni: {e}")
            print("Újracsatlakozás a kiszolgálóhoz!")

    # uname = "asd"
    # client_socket.send(uname.encode("utf-8"))

    print(f"\nSikeres csatlakozás a következőhöz: {host}")

    threading.Thread(target=receive_messages, args=(client_socket,), daemon=True).start()

    send_messages(client_socket)

if __name__ == "__main__":
    start_client()
