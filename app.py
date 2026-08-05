import os
import sys
import ctypes
import queue
import subprocess
import socket
import signal
import threading
import time
import tkinter as tk
from PIL import Image, ImageTk
import io
import pygetwindow as gw
import pyautogui
from flask import Flask, render_template, request
from flask_socketio import SocketIO
from pyngrok import ngrok
import qrcode

# --- Struktur ctypes di level modul (bukan di dalam handler) ---
class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

_user32 = ctypes.windll.user32

app = Flask(__name__)
app.config['SECRET_KEY'] = 'pointer-secret-key'
# allow_upgrades=False + ping_timeout tinggi agar koneksi WebSocket stabil saat idle
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode='threading',
    ping_timeout=60,
    ping_interval=25,
    max_http_buffer_size=1_000_000,
)

NGROK_LOCAL_PORT = 5001  # port HTTP polos khusus tunnel ngrok (server utama HTTPS-only)

# Konfigurasi pyautogui
pyautogui.FAILSAFE = False
pyautogui.MINIMUM_SLEEP = 0
pyautogui.MINIMUM_DURATION = 0

is_ppt_active = False
laser_process = None

# Cache ukuran layar agar tidak dipanggil tiap event
_screen_w, _screen_h = pyautogui.size()

# --- Dedicated cursor thread ---
# Queue maxsize=1: jika server lambat, event lama dibuang, hanya event TERBARU yang dieksekusi.
# Ini menghilangkan antrean yang menumpuk dan membuat gerakan terasa lag.
_move_queue: queue.Queue = queue.Queue(maxsize=1)

def _cursor_worker():
    """Thread terpisah khusus untuk menggerakkan kursor, bebas dari GIL SocketIO."""
    while True:
        try:
            data = _move_queue.get(timeout=1.0)
            _apply_cursor_move(data)
        except queue.Empty:
            continue

def _apply_cursor_move(data):
    if not isinstance(data, dict):
        return
    is_absolute = data.get('absolute', False)
    if is_absolute:
        dGamma = data.get('dGamma', 0)
        dBeta  = data.get('dBeta', 0)
        FOV_X = 25.0
        FOV_Y = 20.0
        ratio_x = max(-1.0, min(1.0, dGamma / FOV_X))
        ratio_y = max(-1.0, min(1.0, -dBeta  / FOV_Y))
        new_x = int((_screen_w / 2) + (ratio_x * (_screen_w / 2)))
        new_y = int((_screen_h / 2) + (ratio_y * (_screen_h / 2)))
    else:
        dx = data.get('dx', 0)
        dy = data.get('dy', 0)
        pt = POINT()
        _user32.GetCursorPos(ctypes.byref(pt))
        new_x = int(pt.x + dx * 3.0)
        new_y = int(pt.y + dy * 3.0)

    new_x = max(0, min(_screen_w - 1, new_x))
    new_y = max(0, min(_screen_h - 1, new_y))
    _user32.SetCursorPos(new_x, new_y)

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
            currently_active = bool(windows) and any('Slide Show' in w.title for w in windows)
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
    if not isinstance(data, dict):
        return
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
    if not isinstance(data, dict):
        return
    state = data.get('state')
    laser_type = data.get('type')

    if state:
        if laser_type == 'global':
            if laser_process is None:
                active_win = gw.getActiveWindow()
                laser_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "laser_overlay.py")
                laser_process = subprocess.Popen([sys.executable, laser_script])
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
    if not isinstance(data, dict):
        return
    # Handler ini langsung mengembalikan kontrol ke SocketIO.
    # Proses cursor dilakukan oleh _cursor_worker di thread terpisah.
    # Jika queue penuh (server tertinggal), buang event lama dan pakai yang terbaru.
    if _move_queue.full():
        try:
            _move_queue.get_nowait()
        except queue.Empty:
            pass
    try:
        _move_queue.put_nowait(data)
    except queue.Full:
        pass

def cleanup(signum=None, frame=None):
    print("\n[!] Menutup server dan membersihkan ghost process...")
    global laser_process
    if laser_process is not None:
        try:
            laser_process.terminate()
            laser_process.wait(timeout=3)
        except Exception:
            try:
                laser_process.kill()
            except Exception:
                pass
        laser_process = None
    try:
        ngrok.kill()
    except Exception:
        pass
    # Pastikan tidak ada ngrok.exe tersisa saat server ditutup (anti ghost)
    try:
        import psutil
        for proc in psutil.process_iter(['name']):
            try:
                if 'ngrok' in (proc.info.get('name') or ''):
                    proc.kill()
            except Exception:
                pass
    except Exception:
        pass
    sys.exit(0)

if __name__ == '__main__':
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)
    if hasattr(signal, 'SIGBREAK'):
        signal.signal(signal.SIGBREAK, cleanup)
    import atexit
    atexit.register(cleanup)

    # Sapu sisa ghost process dari sesi sebelumnya (laser_overlay.py & ngrok.exe)
    try:
        import psutil
        for proc in psutil.process_iter(['name', 'cmdline']):
            try:
                cmd = proc.info.get('cmdline') or []
                name = (proc.info.get('name') or '')
                if 'ngrok' in name or any('laser_overlay.py' in c for c in cmd):
                    proc.kill()
            except Exception:
                pass
    except Exception:
        pass

    threading.Thread(target=check_ppt_status, daemon=True).start()
    threading.Thread(target=_cursor_worker, daemon=True).start()

    ip = get_local_ip()
    port = 5000
    local_url = f"https://{ip}:{port}"  # HTTPS agar gyroscope aktif di local IP

    print("\n" + "=" * 50)
    print("Membuka tunnel Ngrok...")
    ngrok_url = None
    try:
        ngrok_url = ngrok.connect(NGROK_LOCAL_PORT).public_url
    except Exception as e:
        print(f"Gagal menjalankan Ngrok: {e}")

    print("\nPOINTER PPT SERVER BERJALAN!")
    print(f"LOKAL IP  : {local_url}")
    if ngrok_url:
        print(f"NGROK URL : {ngrok_url}")
    print("=" * 50 + "\n")

    # Tampilkan popup QR Code via Tkinter (bukan browser)
    def show_qr_popup():
        time.sleep(1.5)  # Tunggu server siap
        
        def make_qr_image(url, size=200):
            qr = qrcode.QRCode(box_size=4, border=2)
            qr.add_data(url)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            img = img.resize((size, size), Image.LANCZOS)
            return img
        
        root_qr = tk.Tk()
        root_qr.title("Pointer PPT - QR Code")
        root_qr.configure(bg="#0f1117")
        root_qr.resizable(False, False)
        
        # Pusatkan window
        root_qr.update_idletasks()
        sw = root_qr.winfo_screenwidth()
        sh = root_qr.winfo_screenheight()
        
        frame = tk.Frame(root_qr, bg="#0f1117", padx=24, pady=20)
        frame.pack()
        
        tk.Label(frame, text="Scan untuk membuka Pointer PPT",
                 bg="#0f1117", fg="#ffffff",
                 font=("Segoe UI", 12, "bold")).pack(pady=(0, 16))
        
        cols = tk.Frame(frame, bg="#0f1117")
        cols.pack()
        
        def add_qr_column(parent, label_text, url, color):
            col = tk.Frame(parent, bg="#0f1117", padx=12)
            col.pack(side=tk.LEFT)
            
            try:
                img = make_qr_image(url)
                photo = ImageTk.PhotoImage(img)
                lbl_img = tk.Label(col, image=photo, bg="white", padx=4, pady=4)
                lbl_img.image = photo  # Cegah GC
                lbl_img.pack()
            except Exception:
                tk.Label(col, text="[QR Error]", bg="#0f1117", fg="red").pack()
            
            tk.Label(col, text=label_text, bg="#0f1117", fg=color,
                     font=("Segoe UI", 10, "bold")).pack(pady=(8, 2))
            tk.Label(col, text=url, bg="#0f1117", fg="#888888",
                     font=("Segoe UI", 7), wraplength=200).pack()
        
        if ngrok_url:
            add_qr_column(cols, "Ngrok (Internet)", ngrok_url, "#60a5fa")
        
        add_qr_column(cols, "Local IP (WiFi sama)", local_url, "#4ade80")
        
        tk.Label(frame, text="Tutup jendela ini setelah scan",
                 bg="#0f1117", fg="#555555",
                 font=("Segoe UI", 9)).pack(pady=(16, 0))
        
        # Pusatkan window setelah konten dirender
        root_qr.update_idletasks()
        w = root_qr.winfo_width()
        h = root_qr.winfo_height()
        x = (sw - w) // 2
        y = (sh - h) // 2
        root_qr.geometry(f"+{x}+{y}")
        root_qr.attributes("-topmost", True)
        root_qr.mainloop()
    
    threading.Thread(target=show_qr_popup, daemon=True).start()

    print("\nPENTING: Saat membuka Local IP di HP, browser akan menampilkan peringatan keamanan.")
    print("Pilih 'Lanjutkan' atau 'Advanced' -> 'Proceed to ...(unsafe)' untuk membuka halaman.")
    print("Hal ini normal untuk self-signed certificate dan AMAN digunakan di jaringan lokal.\n")

    # Backend HTTPS (adhoc) untuk Local IP — gyroscope butuh secure context.
    # Backend HTTP polos di 127.0.0.1:5001 khusus tunnel ngrok,
    # karena ngrok menghentikan TLS di edge dan mengirim HTTP polos ke localhost.
    def run_http_for_ngrok():
        socketio.run(app, host='127.0.0.1', port=NGROK_LOCAL_PORT,
                     debug=False, allow_unsafe_werkzeug=True, use_reloader=False)

    threading.Thread(target=run_http_for_ngrok, daemon=True).start()
    socketio.run(app, host='0.0.0.0', port=port, debug=False,
                 allow_unsafe_werkzeug=True, ssl_context='adhoc')
