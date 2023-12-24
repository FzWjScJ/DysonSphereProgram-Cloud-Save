import sys
import requests
from PyQt6 import QtWidgets, uic, QtGui
from PyQt6.QtWidgets import QMessageBox
from qt_material import apply_stylesheet
import subprocess
import hashlib
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad,unpad
import os

app = QtWidgets.QApplication(sys.argv)

def check_server(server_ip):
    try:
        if server_ip == "":
            QMessageBox.warning(window, "错误", "请输入存档服务器IP地址。")
        else:
            response = requests.get(f'http://{server_ip}/ping',timeout=3)
            response.raise_for_status()

        if response.text.strip() == "PONG!!!":
            return True 
        else:
            QMessageBox.warning(window, "服务器异常", "服务器返回了一个意外的响应。")
            return False
    except requests.exceptions.RequestException as e:
        QMessageBox.critical(window, "连接错误", "无法连接到服务器。")
        print(e)
        return False

def on_button1_clicked():
    server_ip = window.lineEdit_3.text()
    if not server_ip or not check_server(server_ip):
        return 
    existing_uuid = window.lineEdit_2.text()
    if existing_uuid:
        reply = QMessageBox.question(window, "创建新的 UUID", "用户ID 中已有 UUID。是否要创建新的 UUID?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.No:
            return 

    try:
        response = requests.get(f'http://{server_ip}/init-uuid', timeout=3)
        response.raise_for_status()

        uuid = response.text
        if uuid:
            window.lineEdit_2.setText(uuid)
        else:
            QMessageBox.warning(window, "获取失败", "未能从服务器获取 UUID。")
    except requests.exceptions.RequestException as e:
        QMessageBox.critical(window, "连接错误", "无法连接到服务器。")
        print(e)

def generate_data_with_progress(file_path, progress_callback):
    def read_and_update_chunk(file, chunk_size=8192):
        while True:
            data = file.read(chunk_size)
            if not data:
                break
            progress_callback(len(data))
            yield data

    with open(file_path, 'rb') as f:
        for chunk in read_and_update_chunk(f):
            yield chunk

def encrypt_file(key, source_file, dest_file):
    aes_key = key.digest()[:32]

    with open(source_file, 'rb') as file:
        file_data = file.read()
    
    cipher = AES.new(aes_key, AES.MODE_ECB)

    encrypted_data = cipher.encrypt(pad(file_data, AES.block_size))

    with open(dest_file, 'wb') as file:
        file.write(encrypted_data)

class FileWithProgress:
    def __init__(self, file_path, progress_callback):
        self.file_path = file_path
        self.progress_callback = progress_callback
        self.file = None
        self.total_read = 0

    def __enter__(self):
        self.file = open(self.file_path, 'rb')
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.file:
            self.file.close()

    def __iter__(self):
        return self

    def __next__(self):
        chunk = self.file.read(8192)
        if not chunk:
            raise StopIteration
        self.total_read += len(chunk)
        self.progress_callback(self.total_read)
        return chunk

    def read(self, size=-1):
        chunk = self.file.read(size)
        if chunk:
            self.total_read += len(chunk)
            self.progress_callback(self.total_read)
        return chunk

def upload_file_with_progress(file_path, server_ip, uuid):

    with open(file_path, 'rb') as f:
        files = {'file': (os.path.basename(file_path), f, 'application/octet-stream')}
        response = requests.post(f"http://{server_ip}/upload?uuid={uuid}", files=files)
        if response.status_code == 200:
            QMessageBox.information(window, "成功", "文件上传成功。")
        else:
            QMessageBox.warning(window, "失败", f"文件上传失败。服务器响应: {response.status_code}, {response.text}")

def create_tar_archive(source_folder, output_filename):
    parent_dir, folder_name = os.path.split(source_folder)
    
    output_filename = os.path.abspath(output_filename)
    
    if not parent_dir:
        parent_dir = '.'

    try:
        subprocess.run(["tar", "-czf", output_filename, folder_name], check=True, cwd=parent_dir)
    except subprocess.SubprocessError as e:
        print("打包过程中发生错误：", e)
        return False
    return True

def on_button2_clicked():
    server_ip = window.lineEdit_3.text()
    uuid = window.lineEdit_2.text()
    if not server_ip or not uuid or not check_server(server_ip):
        QMessageBox.warning(window, "错误", "服务器 IP 或 UUID 无效。")
        return 
    archive_path = "./archive.tar.gz"
    encrypted_archive_path = "./archive.enc"

    archive_folder = window.lineEdit.text()
    archive_folder = os.path.expandvars(archive_folder)
    if not os.path.exists(archive_folder):
        QMessageBox.warning(window, "路径错误", "指定的目录不存在。请更改路径。")
        window.lineEdit.setReadOnly(False)
        return

    if not create_tar_archive(archive_folder, archive_path):
        return

    key = hashlib.md5(hashlib.sha512(uuid.encode()).hexdigest().encode())
    encrypt_file(key, archive_path, encrypted_archive_path)
    upload_file_with_progress(encrypted_archive_path, server_ip, uuid)
    os.remove(encrypted_archive_path)
    os.remove(archive_path)

def decrypt_file(key, source_file, dest_file):
    aes_key = key.digest()[:32]
    
    try:
        with open(source_file, 'rb') as file:
            encrypted_data = file.read()
        
        cipher = AES.new(aes_key, AES.MODE_ECB)
        decrypted_data = unpad(cipher.decrypt(encrypted_data), AES.block_size)
        
        with open(dest_file, 'wb') as file:
            file.write(decrypted_data)
        return True
    except Exception as e:
        print(f"解密失败：{e}")
        return False

def extract_tar_archive(archive_path, extract_to):
    try:
        subprocess.run(["tar", "-xzf", archive_path, "-C", extract_to+"/../"], check=True)
    except subprocess.SubprocessError as e:
        print("解压过程中发生错误：", e)
        return False
    return True

def on_button3_clicked():
    server_ip = window.lineEdit_3.text()
    uuid = window.lineEdit_2.text()
    archive_folder = window.lineEdit.text()
    archive_folder = os.path.expandvars(archive_folder)

    if not server_ip or not uuid or not check_server(server_ip):
        QMessageBox.warning(window, "错误", "服务器 IP 或 UUID 无效。")
        return

    if not os.path.exists(archive_folder):
        os.makedirs(archive_folder)

    encrypted_archive_path = os.path.join(archive_folder, "archive.enc")
    decrypted_archive_path = os.path.join(archive_folder, "archive.tar.gz")

    try:
        response = requests.get(f"http://{server_ip}/download?uuid={uuid}", stream=True)
        
        if response.status_code == 200:
            with open(encrypted_archive_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
        else:
            QMessageBox.warning(window, "下载失败", f"服务器响应: {response.status_code}, {response.text}")
            return
    except Exception as e:
        QMessageBox.critical(window, "下载异常", str(e))
        return

    key = hashlib.md5(hashlib.sha512(uuid.encode()).hexdigest().encode())
    decryption_successful = decrypt_file(key, encrypted_archive_path, decrypted_archive_path)
    if decryption_successful:
        if extract_tar_archive(decrypted_archive_path, archive_folder):
            QMessageBox.information(window, "成功", "文件下载和解压成功。")
        else:
            QMessageBox.critical(window, "解压失败", "无法解压缩文件。")
    else:
        QMessageBox.critical(window, "解密失败", "无法解密下载的文件。")
    os.remove(encrypted_archive_path)
    os.remove(decrypted_archive_path)


def resource_path(relative_path):
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)

client_ui_path = resource_path("client.ui")
window = uic.loadUi(client_ui_path)
window.setWindowIcon(QtGui.QIcon('logo.ico'))
button1 = window.pushButton
button1.clicked.connect(on_button1_clicked)

button2 = window.pushButton_2
button2.clicked.connect(on_button2_clicked)

button3 = window.pushButton_3
button3.clicked.connect(on_button3_clicked)

apply_stylesheet(app, theme='dark_teal.xml')

window.show()
sys.exit(app.exec())