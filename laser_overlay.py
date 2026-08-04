import tkinter as tk
import ctypes

class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

def get_cursor_pos():
    pt = POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y

root = tk.Tk()
root.title("pointer_ppt_laser_overlay")

# Gunakan full screen dan sembunyikan dekorasi
w = root.winfo_screenwidth()
h = root.winfo_screenheight()
root.geometry(f"{w}x{h}+0+0")
root.overrideredirect(True)

# Set properti tembus pandang dan kebal klik
root.attributes("-topmost", True)
root.attributes("-transparentcolor", "white")
root.attributes("-disabled", True)
root.config(bg="white")

canvas = tk.Canvas(root, bg="white", highlightthickness=0)
canvas.pack(fill=tk.BOTH, expand=True)

# Wajib dipanggil agar Windows mendaftarkan window ini sebelum kita ambil HWND-nya
root.update_idletasks()

# JADIKAN JENDELA INI 100% TEMBUS KLIK (CLICK-THROUGH) KE APLIKASI DI BAWAHNYA
hwnd = ctypes.windll.user32.FindWindowW(None, "pointer_ppt_laser_overlay")
if hwnd:
    # GWL_EXSTYLE = -20
    ex_style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
    # WS_EX_LAYERED = 0x00080000, WS_EX_TRANSPARENT = 0x00000020, WS_EX_NOACTIVATE = 0x08000000
    ctypes.windll.user32.SetWindowLongW(hwnd, -20, ex_style | 0x00080000 | 0x00000020 | 0x08000000)

# Gambar laser merah di luar layar pada awalnya
laser_dot = canvas.create_oval(-20, -20, 0, 0, fill="#ff0000", outline="#ff0000")

def update_position():
    x, y = get_cursor_pos()
    # Pindahkan HANYA objek merah di dalam canvas, BUKAN memindahkan window OS
    canvas.coords(laser_dot, x - 10, y - 10, x + 10, y + 10)
    root.after(16, update_position) # ~60 FPS

update_position()
root.mainloop()
