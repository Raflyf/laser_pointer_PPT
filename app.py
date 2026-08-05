import os
import sys
import ctypes
import subprocess
import socket
import signal
import threading
import time
import pygetwindow as gw
import pyautogui
from flask import Flask, render_template, request
from flask_socketio import SocketIO
from pyngrok import ngrok

# --- Struktur ctypes di level modul (bukan di dalam handler) ---
class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

_user32 = ctypes.windll.user32

app = Flask(__name__)
app.config['SECRET_KEY'] = 'pointer-secret-key'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Konfigurasi pyautogui
pyautogui.FAILSAFE = False
pyautogui.MINIMUM_SLEEP = 0
pyautogui.MINIMUM_DURATION = 0

is_ppt_active = False
laser_process = None

# Cache ukuran layar agar tidak dipanggil tiap event
_screen_w, _screen_h = pyautogui.size()

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
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
            windows = gw.getWindowsWithTitle('PowerPoint Slide Show')
            if not windows:
                windows = gw.getWindowsWithTitle('PowerPoint')
            currently_active = any('PowerPoint' in w.title for w in windows)
            if currently_active != is_ppt_active:
                is_ppt_active = currently_active
                socketio.emit('ppt_status', {'active': is_ppt_active})
        except Exception:
            pass
        time.sleep(2)

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('connect')
def handle_connect():
    socketio.emit('ppt_status', {'active': is_ppt_active}, to=request.sid)

@socketio.on('action')
def handle_action(data):
    command = data.get('command')
    actions = {
        'next':        lambda: pyautogui.press('right'),
        'prev':        lambda: pyautogui.press('left'),
        'left_click':  lambda: pyautogui.click(),
        'right_click': lambda: pyautogui.rightClick(),
        'esc':         lambda: pyautogui.press('esc'),
        'f5':          lambda: pyautogui.press('f5'),
    }
    action_fn = actions.get(command)
    if action_fn:
        action_fn()

@socketio.on('laser_toggle')
def handle_laser_toggle(data):
    global laser_process
    state = data.get('state')
    laser_type = data.get('type')

    if state:
        if laser_type == 'global':
            if laser_process is None:
                active_win = gw.getActiveWindow()
                laser_process = subprocess.Popen([sys.executable, "laser_overlay.py"])
                def restore_focus():
                    time.sleep(0.5)
                    if active_win:
                        try:
                            active_win.activate()
                        except Exception:
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
    is_absolute = data.get('absolute', False)

    if is_absolute:
        # Mode Absolute Pointer: sudut kemiringan HP dipetakan langsung ke koordinat layar
        dGamma = data.get('dGamma', 0)
        dBeta = data.get('dBeta', 0)

        # FOV: +/- derajat dari titik tengah untuk melintasi setengah layar
        FOV_X = 25.0
        FOV_Y = 20.0

        ratio_x = max(-1.0, min(1.0, dGamma / FOV_X))
        ratio_y = max(-1.0, min(1.0, -dBeta / FOV_Y))

        new_x = int((_screen_w / 2) + (ratio_x * (_screen_w / 2)))
        new_y = int((_screen_h / 2) + (ratio_y * (_screen_h / 2)))
    else:
        # Mode Touchpad Relatif
        dx = data.get('dx', 0)
        dy = data.get('dy', 0)
        speed = 3.0

        pt = POINT()
        _user32.GetCursorPos(ctypes.byref(pt))

        new_x = int(pt.x + dx * speed)
        new_y = int(pt.y + dy * speed)

    # Kunci agar tidak keluar batas layar
    new_x = max(0, min(_screen_w - 1, new_x))
    new_y = max(0, min(_screen_h - 1, new_y))
    _user32.SetCursorPos(new_x, new_y)

def cleanup(signum=None, frame=None):
    print("\n[!] Menutup server dan membersihkan ghost process...")
    global laser_process
    if laser_process is not None:
        laser_process.terminate()
    try:
        ngrok.kill()
    except Exception:
        pass
    sys.exit(0)

if __name__ == '__main__':
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    threading.Thread(target=check_ppt_status, daemon=True).start()

    ip = get_local_ip()
    port = 5000
    local_url = f"http://{ip}:{port}"

    print("\n" + "=" * 50)
    print("Membuka tunnel Ngrok...")
    ngrok_url = None
    try:
        ngrok_url = ngrok.connect(port).public_url
    except Exception as e:
        print(f"Gagal menjalankan Ngrok: {e}")

    print("\nPOINTER PPT SERVER BERJALAN!")
    print(f"LOKAL IP  : {local_url}")
    if ngrok_url:
        print(f"NGROK URL : {ngrok_url}")
    print("=" * 50 + "\n")

    primary_url = ngrok_url if ngrok_url else local_url
    try:
        import qrcode
        import webbrowser
        img = qrcode.make(primary_url)
        qr_path = os.path.join(app.root_path, 'static', 'qr.png')
        img.save(qr_path)
        threading.Timer(2.0, lambda: webbrowser.open(f"http://127.0.0.1:{port}/static/qr.png")).start()
    except Exception:
        print("Gagal membuat QR Code otomatis.")

    socketio.run(app, host='0.0.0.0', port=port, debug=False, allow_unsafe_werkzeug=True)
