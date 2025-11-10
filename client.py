import socket
import threading
import queue
import os
import time
import csv
import numpy as np
import sounddevice as sd
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes, serialization
from textual.app import App, ComposeResult
from textual.widgets import RichLog, Input, Button, Header
from textual.reactive import var

RATE = 16000
CHANNELS = 1
CHUNK = 960
BUF_SIZE = 4096
DTYPE = "int16"
VPORT = 9700
TCP_BUF = 4096

incoming_messages = queue.Queue()
outgoing_messages = queue.Queue()

state = {
    "host": None,
    "port": None,
    "uname": None,
    "text_socket": None,
    "voice_socket": None,
    "cipher": None,
    "voice": False,
    "mute": False,
    "deafen": False,
    "running": True,
}

def generate_rsa_keys():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    return private_key, public_key

def exchange_key(text_socket):
    private_key, public_key = generate_rsa_keys()
    client_pub_pem = public_key.public_bytes(encoding=serialization.Encoding.PEM,format=serialization.PublicFormat.SubjectPublicKeyInfo)
    text_socket.send(client_pub_pem)
    encrypted_session_key = text_socket.recv(TCP_BUF)
    session_key = private_key.decrypt(encrypted_session_key,padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None))
    return Fernet(session_key)

def handle_command(msg: str):
    try:
        if msg.startswith("/voice"):
            parts = msg.split()
            cmd = parts[1] if len(parts) > 1 else ""
            if cmd == "join":
                if state["voice"]:
                    incoming_messages.put(f"[yellow]{language()[0][config()]}[/yellow]")
                    return None
                if not state["voice_socket"]:
                    usock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    state["voice_socket"] = usock
                pkt = f"REGISTER:{state['uname']}".encode("utf-8")
                state["voice_socket"].sendto(pkt, (state["host"], VPORT))
                state["voice"] = True
                threading.Thread(target=send_audio_loop, args=(state["voice_socket"],), daemon=True).start()
                threading.Thread(target=recv_audio_loop, args=(state["voice_socket"],), daemon=True).start()
                incoming_messages.put(f"[green]{language()[1][config()]}: {language()[2][config()]}[/green]")
                return None
            elif cmd in ("exit", "stop", "quit", "disconnect", "abort"):
                state["voice"] = False
                incoming_messages.put(f"[green]{language()[1][config()]}: {language()[3][config()]}[/green]")
                return None
            elif cmd == "mute":
                state["mute"] = True
                incoming_messages.put(f"[yellow]{language()[4][config()]}[/yellow]")
                return None
            elif cmd == "unmute":
                state["mute"] = False
                incoming_messages.put(f"[yellow]{language()[5][config()]}[/yellow]")
                return None
            elif cmd == "deafen":
                state["deafen"] = True
                state["mute"] = True
                incoming_messages.put(f"[yellow]{language()[6][config()]}[/yellow]")
                return None
            elif cmd == "undeafen":
                state["deafen"] = False
                state["mute"] = False
                incoming_messages.put(f"[yellow]{language()[7][config()]}[/yellow]")
                return None
            else:
                incoming_messages.put(f"[cyan]{language()[8][config()]}[/cyan]")
                return None
    except Exception as e:
        incoming_messages.put(f"[red]{language()[9][config()]}:[/red] {e}")
        return None
    return msg

def send_audio_loop(udp_sock: socket.socket):
    try:
        with sd.RawInputStream(samplerate=RATE, channels=CHANNELS, dtype=DTYPE, blocksize=CHUNK) as stream:
            incoming_messages.put(f"[green]{language()[1][config()]}: {language()[10][config()]}[/green]")
            while state["running"] and state["voice"]:
                if state["mute"]:
                    time.sleep(0.05)
                    continue
                try:
                    data, overflow = stream.read(CHUNK)
                    udp_sock.sendto(bytes(data), (state["host"], VPORT))
                except Exception as e:
                    incoming_messages.put(f"[red]{language()[11][config()]}:[/red] {e}")
                    break
    except Exception as e:
        incoming_messages.put(f"[red]Error:[/red] {e}")
    finally:
        incoming_messages.put(f"[yellow]{language()[1][config()]}: {language()[13][config()]}[/yellow]")

def recv_audio_loop(udp_sock: socket.socket):
    try:
        with sd.RawOutputStream(samplerate=RATE, channels=CHANNELS, dtype=DTYPE, blocksize=CHUNK) as out:
            incoming_messages.put(f"[green]{language()[1][config()]}: {language()[14][config()]}[/green]")
            while state["running"] and state["voice"]:
                if state["deafen"]:
                    time.sleep(0.05)
                    continue
                try:
                    pkt, _ = udp_sock.recvfrom(BUF_SIZE)
                    arr = np.frombuffer(pkt, dtype=np.int16)
                    if CHANNELS > 1:
                        arr = arr.reshape(-1, CHANNELS)
                    out.write(arr)
                except Exception as e:
                    incoming_messages.put(f"[red]{language()[15][config()]}:[/red] {e}")
                    break
    except Exception as e:
        incoming_messages.put(f"[red]Error:[/red] {e}")
    finally:
        incoming_messages.put(f"[yellow]{language()[1][config()]}: {language()[16][config()]}[/yellow]")

def sender_thread():
    while state["running"]:
        try:
            msg = outgoing_messages.get(timeout=0.1)
        except queue.Empty:
            continue
        try:
            if state["cipher"] is None or state["text_socket"] is None:
                incoming_messages.put(f"[red]{language()[17][config()]}[/red]")
                continue
            encrypted = state["cipher"].encrypt(msg.encode("utf-8"))
            state["text_socket"].send(encrypted)
        except Exception as e:
            incoming_messages.put(f"[red]{language()[12][config()]}:[/red] {e}")

def receiver_thread(text_socket):
    try:
        while state["running"]:
            try:
                encrypted_msg = text_socket.recv(TCP_BUF)
                if not encrypted_msg:
                    incoming_messages.put(f"[red]{language()[18][config()]}[/red]")
                    break
                if state["cipher"]:
                    try:
                        message = state["cipher"].decrypt(encrypted_msg).decode("utf-8")
                        incoming_messages.put(message)
                    except Exception as e:
                        incoming_messages.put(f"[red]{language()[12][config()]}:[/red] {e}")
                else:
                    incoming_messages.put(f"[red]{language()[12][config()]}! {language()[19][config()]}[/red]")
            except ConnectionResetError:
                incoming_messages.put(f"[red]{language()[20][config()]}[/red]")
                break
            except Exception as e:
                incoming_messages.put(f"[red]{language()[12][config()]}:[/red] {e}")
                break
    finally:
        try:
            text_socket.close()
        except:
            pass
        state["text_socket"] = None
        state["cipher"] = None

def connect_to_server(host: str, port: int, uname: str):
    try:
        tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp.connect((host, port))
        incoming_messages.put(f"[green]{language()[21][config()]}: {host}:{port}[/green]")

        cipher = exchange_key(tcp)

        tcp.send(cipher.encrypt(uname.encode("utf-8")))

        state["text_socket"] = tcp
        state["cipher"] = cipher
        state["host"] = host
        state["port"] = port
        state["uname"] = uname

        threading.Thread(target=receiver_thread, args=(tcp,), daemon=True).start()

        return True, None
    except Exception as e:
        incoming_messages.put(f"[red]{language()[12][config()]}:[/red] {e}")
        return False, e

class CHeader(Header):
    def compose(self):
        for widget in super().compose():
            yield widget
        # yield Button("Mute", id="mute", classes="extra")
        # yield Button("Deafen", id="deaf", classes="extra")

class tui(App):
    ENABLE_COMMAND_PALETTE = False
    CSS_PATH = 'assets/style.tcss'
    TITLE = "Cord"

    mode = var("welcome")
    title_prefix = "Cord"

    def compose(self) -> ComposeResult:
        yield Header(id="header",show_clock=True)
        yield RichLog(id="chat", highlight=True, markup=True, wrap=True)
        yield Input(placeholder=f"{language()[23][config()]}...", id="input")

    async def on_mount(self) -> None:
        self.chat = self.query_one("#chat", RichLog)
        self.input = self.query_one("#input", Input)
        self.set_focus(self.input)
        threading.Thread(target=sender_thread, daemon=True).start()
        self.set_interval(0.05, self._poll_incoming) 

    def _poll_incoming(self):
        while True:
            try:
                msg = incoming_messages.get_nowait()
            except queue.Empty:
                break
            try:
                self.chat.write(msg)
            except Exception:
                pass

    async def on_input_submitted(self, event: Input.Submitted):
        text = event.value.strip()
        event.input.value = ""
        if not text:
            return

        if text == "/quit":
            await self.action_quit()
            return

        
        if text.startswith("/con") or text.startswith("/connect"):
            try:
                if len(text.split(" ")) > 1:
                    h, p = text.split(" ")[1].split(":")
                    self.mode = "uname"
                else:
                    self.mode = "host"
                    incoming_messages.put(f"[cyan]{language()[24][config()]}:[/cyan]")
                return
            except ValueError as e:
                incoming_messages.put(f"{language()[32][config()]}")
                self.mode = "host"

        if self.mode == "host":
            if ":" in text:
                h, p = text.split(":", 1)
                try:
                    p = int(p)
                except:
                    incoming_messages.put(f"[red]{language()[25][config()]}[/red]")
                    return
                self.mode = "uname"
                state["host"] = h
                state["port"] = p
                incoming_messages.put(f"[cyan]{language()[26][config()]}:[/cyan]")
                return
            else:
                state["host"] = text
                self.mode = "port"
                incoming_messages.put(f"[cyan]{language()[27][config()]}:[/cyan]")
                return

        if self.mode == "port":
            if text == "":
                p = 7777
            else:
                try:
                    p = int(text)
                except:
                    incoming_messages.put(f"[red]{language()[25][config()]}[/red]")
                    return
            state["port"] = p
            self.mode = "uname"
            incoming_messages.put(f"[cyan]{language()[26][config()]}:[/cyan]")
            return

        if self.mode == "uname":
            uname = text
            state["uname"] = uname
            incoming_messages.put(f"[cyan]{language()[28][config()]}...[/cyan]")
            host = state.get("host")
            port = state.get("port")
            threading.Thread(target=self.initialization, args=(host, port, uname), daemon=True).start()
            self.mode = "connected"
            return

        if text.startswith("/"):
            try:
                result = handle_command(text, self)
                if result:
                    outgoing_messages.put(result)
                    self.chat.write(f"[bold green]{language()[29][config()]}:[/bold green] {result}")
                return
            except IndexError as e:
                incoming_messages.put(f"{language()[12][config()]}: {e}")
        else:
            if state["text_socket"] is None or state["cipher"] is None:
                incoming_messages.put(f"[red]{language()[17][config()]}.[/red]")
                return
            outgoing_messages.put(text)
            self.chat.write(f"[bold green]{language()[29][config()]}:[/bold green] {text}")

    def initialization(self, host, port, uname):
        success, err = connect_to_server(host, port, uname)
        if success:
            incoming_messages.put(f"[green]{language()[30][config()]}, {uname}[/green]")
            self.mode = "connected"
        else:
            incoming_messages.put(f"[red]{language()[31][config()]}.[/red]")
            self.mode = "welcome"

    async def on_shutdown(self) -> None:
        state["running"] = False
        try:
            if state["text_socket"]:
                state["text_socket"].close()
        except:
            pass
        try:
            if state["voice_socket"]:
                state["voice_socket"].close()
        except:
            pass

def config():
    with open('config.ini', mode='r', encoding='utf-8') as c:
        c_sorok = c.readlines()
        data = {}
        for i in c_sorok:
            data[f'{i.strip("\n").split('=')[0]}'] = i.strip().split('=')[1]
    print(data)
    if data.get("lang") == "hu":
        return 'hu'
    elif data.get("lang") == "en":
        return 'en'

def language():
    with open('assets/language.lf', mode='r', encoding='utf-8') as lf:
        lf_data = csv.DictReader(lf)
        l_data = []
        for row in lf_data:
            l_data.append(row)
    return l_data

if __name__ == "__main__":
    os.system("title Cord")
    tui().run()
