import tkinter as tk
import ctypes

class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

_user32 = ctypes.windll.user32

def get_cursor_pos():
    pt = POINT()
    _user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y

root = tk.Tk()
root.title("pointer_ppt_laser_overlay")

w = root.winfo_screenwidth()
h = root.winfo_screenheight()
root.geometry(f"{w}x{h}+0+0")
root.overrideredirect(True)
root.attributes("-topmost", True)
root.attributes("-transparentcolor", "white")
root.config(bg="white")

canvas = tk.Canvas(root, bg="white", highlightthickness=0)
canvas.pack(fill=tk.BOTH, expand=True)

root.update_idletasks()

# Terapkan click-through dan no-activate via WinAPI
# WS_EX_LAYERED=0x80000, WS_EX_TRANSPARENT=0x20, WS_EX_NOACTIVATE=0x8000000
hwnd = _user32.FindWindowW(None, "pointer_ppt_laser_overlay")
if hwnd:
    ex = _user32.GetWindowLongW(hwnd, -20)
    _user32.SetWindowLongW(hwnd, -20, ex | 0x80000 | 0x20 | 0x8000000)

laser_dot = canvas.create_oval(-20, -20, 0, 0, fill="#ff2222", outline="")

def update_position():
    x, y = get_cursor_pos()
    canvas.coords(laser_dot, x - 10, y - 10, x + 10, y + 10)
    root.after(16, update_position)

update_position()
root.mainloop()
