import sys
import os
import socket
import struct
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton,
    QLabel, QFileDialog, QTextEdit
)
from PySide6.QtCore import QThread, Signal

PORT = 5001
BUFFER_SIZE = 4096


def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    finally:
        s.close()
    return ip


# ================= RECEIVER =================
class ReceiverThread(QThread):
    log = Signal(str)

    def __init__(self, save_dir):
        super().__init__()
        self.save_dir = save_dir
        self.running = True

    def run(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind(("", PORT))
        server.listen(5)

        self.log.emit(f"Listening on port {PORT}...")

        while self.running:
            conn, addr = server.accept()
            self.log.emit(f"Connection from {addr}")

            try:
                while True:
                    header = conn.recv(4)
                    if not header:
                        break

                    filename_len = struct.unpack("!I", header)[0]
                    filename = conn.recv(filename_len).decode()

                    filesize = struct.unpack("!Q", conn.recv(8))[0]

                    filepath = os.path.join(self.save_dir, filename)
                    self.log.emit(f"Receiving: {filename} ({filesize} bytes)")

                    with open(filepath, "wb") as f:
                        received = 0
                        while received < filesize:
                            chunk = conn.recv(min(BUFFER_SIZE, filesize - received))
                            if not chunk:
                                break
                            f.write(chunk)
                            received += len(chunk)

                    self.log.emit(f"Saved: {filepath}")

            except Exception as e:
                self.log.emit(f"Error: {e}")

            conn.close()


# ================= SENDER =================
class SenderThread(QThread):
    log = Signal(str)

    def __init__(self, files, target_ip):
        super().__init__()
        self.files = files
        self.target_ip = target_ip

    def run(self):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((self.target_ip, PORT))

            for filepath in self.files:
                filename = os.path.basename(filepath).encode()
                filesize = os.path.getsize(filepath)

                self.log.emit(f"Sending: {filename.decode()}")

                sock.sendall(struct.pack("!I", len(filename)))
                sock.sendall(filename)
                sock.sendall(struct.pack("!Q", filesize))

                with open(filepath, "rb") as f:
                    while True:
                        chunk = f.read(BUFFER_SIZE)
                        if not chunk:
                            break
                        sock.sendall(chunk)

                self.log.emit(f"Sent: {filename.decode()}")

            sock.close()

        except Exception as e:
            self.log.emit(f"Error: {e}")


# ================= GUI =================
class App(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LAN File Share")

        layout = QVBoxLayout()

        self.info = QLabel(f"My IP: {get_local_ip()}:{PORT}")
        layout.addWidget(self.info)

        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        layout.addWidget(self.log_box)

        # Buttons
        self.btn_receive = QPushButton("Start Receiver")
        self.btn_receive.clicked.connect(self.start_receiver)
        layout.addWidget(self.btn_receive)

        self.btn_send = QPushButton("Send Files")
        self.btn_send.clicked.connect(self.send_files)
        layout.addWidget(self.btn_send)

        self.setLayout(layout)

    def log(self, text):
        self.log_box.append(text)

    def start_receiver(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Save Folder")
        if not folder:
            return

        self.receiver = ReceiverThread(folder)
        self.receiver.log.connect(self.log)
        self.receiver.start()

    def send_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select Files")
        if not files:
            return

        ip, ok = QFileDialog.getText(self, "Target IP", "Enter receiver IP:")
        if not ok or not ip:
            return

        self.sender = SenderThread(files, ip)
        self.sender.log.connect(self.log)
        self.sender.start()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = App()
    window.resize(400, 300)
    window.show()
    sys.exit(app.exec())
