

import os
import sys
import subprocess
import socket
import signal
import threading
import time
import pygetwindow as gw
import pyautogui
from flask import Flask, render_template, request
from flask_socketio import SocketIO
import qrcode
from pyngrok import ngrok

app = Flask(__name__)
app.config['SECRET_KEY'] = 'pointer-secret-key'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Konfigurasi pyautogui
pyautogui.FAILSAFE = False
pyautogui.MINIMUM_SLEEP = 0
pyautogui.MINIMUM_DURATION = 0

is_ppt_active = False
laser_process = None

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Tidak harus bisa terkoneksi, hanya untuk mencari interface jaringan yang aktif
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

def check_ppt_status():
    global is_ppt_active
    while True:
        try:
            # Cari jendela yang mengandung teks "PowerPoint Slide Show" atau "PowerPoint"
            windows = gw.getWindowsWithTitle('PowerPoint Slide Show')
            if not windows:
                windows = gw.getWindowsWithTitle('PowerPoint')
            
            currently_active = False
            for w in windows:
                if 'PowerPoint' in w.title:
                    currently_active = True
                    break
            
            if currently_active != is_ppt_active:
                is_ppt_active = currently_active
                socketio.emit('ppt_status', {'active': is_ppt_active})
                
        except Exception as e:
            pass
        time.sleep(2)

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('connect')
def test_connect():
    socketio.emit('ppt_status', {'active': is_ppt_active}, to=request.sid)

@socketio.on('action')
def handle_action(data):
    command = data.get('command')
    if command == 'next':
        pyautogui.press('right')
    elif command == 'prev':
        pyautogui.press('left')
    elif command == 'left_click':
        pyautogui.click()
    elif command == 'right_click':
        pyautogui.rightClick()
    elif command == 'esc':
        pyautogui.press('esc')
    elif command == 'f5':
        pyautogui.press('f5')

@socketio.on('laser_toggle')
def handle_laser_toggle(data):
    global laser_process
    state = data.get('state') # True or False
    laser_type = data.get('type') # 'ppt' or 'global'
    
    if state:
        if laser_type == 'global':
            if laser_process is None:
                active_win = gw.getActiveWindow()
                laser_process = subprocess.Popen([sys.executable, "laser_overlay.py"])
                
                # Kembalikan fokus ke window sebelumnya (PPT) agar F5/Esc/Klik tetap berfungsi
                def restore_focus():
                    time.sleep(0.5)
                    if active_win:
                        try:
                            active_win.activate()
                        except:
                            pass
                threading.Thread(target=restore_focus, daemon=True).start()
                
        elif laser_type == 'ppt':
            pyautogui.hotkey('ctrl', 'l')
    else:
        if laser_process is not None:
            laser_process.terminate()
            laser_process = None
        if laser_type == 'ppt':
            pyautogui.hotkey('ctrl', 'a')

@socketio.on('laser_move')
def handle_laser_move(data):
    # dx, dy dari touchpad/gyro
    dx = data.get('dx', 0)
    dy = data.get('dy', 0)
    
    # Pengali kecepatan
    speed_multiplier = 3.0
    
    import ctypes
    class POINT(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
    pt = POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    current_x, current_y = pt.x, pt.y
    
    new_x = current_x + (dx * speed_multiplier)
    new_y = current_y + (dy * speed_multiplier)
    
    # Batasi agar tidak keluar layar
    screen_width, screen_height = pyautogui.size()
    new_x = max(0, min(screen_width - 1, int(new_x)))
    new_y = max(0, min(screen_height - 1, int(new_y)))
    
    ctypes.windll.user32.SetCursorPos(new_x, new_y)

def cleanup(signum, frame):
    print("\n[!] Menutup server dan membersihkan ghost process...")
    global laser_process
    if laser_process is not None:
        laser_process.terminate()
    try:
        ngrok.kill()
    except:
        pass
    sys.exit(0)

if __name__ == '__main__':
    # Daftarkan handler untuk Ctrl+C
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)
    
    # Mulai thread pengecekan PPT
    threading.Thread(target=check_ppt_status, daemon=True).start()
    
    ip = get_local_ip()
    port = 5000
    local_url = f"http://{ip}:{port}"
    
    ngrok_url = None
    print("\n" + "="*50)
    print("Membuka tunnel Ngrok...")
    try:
        ngrok_url = ngrok.connect(port).public_url
    except Exception as e:
        print(f"Gagal menjalankan Ngrok: {e}")
        
    print("\nPOINTER PPT SERVER BERJALAN!")
    print(f"LOKAL IP  : {local_url}")
    if ngrok_url:
        print(f"NGROK URL : {ngrok_url}")
    print("="*50 + "\n")
    
    # Generate QR Code dan simpan ke file statis
    primary_url = ngrok_url if ngrok_url else local_url
    try:
        import qrcode
        import webbrowser
        img = qrcode.make(primary_url)
        qr_path = os.path.join(app.root_path, 'static', 'qr.png')
        img.save(qr_path)
        # Buka QR Code di browser default laptop setelah server siap (delay 2 detik)
        threading.Timer(2.0, lambda: webbrowser.open(f"http://127.0.0.1:{port}/static/qr.png")).start()
    except Exception as e:
        print("Gagal membuat QR Code otomatis.")
    
    if not ngrok_url:
        print("\nPENTING: Karena tidak menggunakan Ngrok, browser HP mungkin menampilkan 'Connection is not private'.")
        print("Pilih 'Advanced' -> 'Proceed' untuk melanjutkan.\n")
    
    socketio.run(app, host='0.0.0.0', port=port, debug=False, allow_unsafe_werkzeug=True)
