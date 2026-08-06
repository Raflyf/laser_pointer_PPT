<div align="center">

# 🖱️ Pointer PPT & Laser Remote

**Kendalikan presentasi PowerPoint langsung dari handphone — tanpa kabel, tanpa aplikasi tambahan.**

Aplikasi web berbasis **Flask + Socket.IO** yang mengubah laptop menjadi remote presentasi. Cukup scan QR code, dan handphone Anda menjadi *touchpad* dan *laser pointer* untuk slide Anda.

</div>

---

## ✨ Fitur

| Fitur | Deskripsi |
|---|---|
| 📱 **Kontrol dari HP** | UI mobile-first; scan QR, langsung jalan. |
| 🖱️ **Touchpad Natural** | Geser 1 jari gerakkan kursor, 2 jari scroll (dengan *inertia* ala touchpad fisik). Tap = klik kiri, double-tap = klik kanan. |
| 🔭 **Laser Pointer** | Dua mode: *Ctrl+L* (mode PPT) atau *overlay laser* di seluruh layar. |
| 📐 **Gyroscope Control** | Miringkan HP untuk menggerakkan kursor — sensornya butuh koneksi HTTPS. |
| ⏭️ **Navigasi Slide** | Tombol Next / Prev, Esc, dan Mulai Presentasi (F5). |
| 🛡️ **Token Akses Otomatis** | Setiap koneksi divalidasi token acak — orang lain di jaringan tidak bisa mengontrol. |

---

## 🚀 Cara Penggunaan

### Prasyarat
- Python 3.9+
- PowerPoint terbuka di laptop (Windows)

### Menjalankan

```bash
# 1. Install dependensi
pip install -r requirements.txt

# 2. Jalankan
python app.py
```

Atau cukup klik **`run.bat`**.

Server akan menampilkan:
- **QR Code** pop-up + URL lokal (`https://192.168.1.x:5000`)
- **URL ngrok** publik (opsional, untuk akses dari luar jaringan)

### Menggunakan

1. Pastikan laptop & HP di **jaringan WiFi yang sama** (atau hotspot).
2. Scan QR code dari handphone.
3. Bila muncul peringatan *"Connection is not private"*, pilih **Advanced → Proceed**. Ini normal: sertifikat self-signed dipakai agar sensor gyroscope berfungsi (HTTPS).
4. Buka file PowerPoint di laptop, tekan **F5** untuk masuk mode presentasi.
5. Kontrol dari HP: touchpad / gyro / tombol slide.

---

## 🔐 Keamanan

- **Token akses otomatis**: server membuat token acak (`secrets.token_urlsafe`) setiap dijalankan. Client wajib mengirim token lewat `auth.token` saat koneksi Socket.IO — tanpa token benar, koneksi ditolak.
- Gunakan token tetap dengan env `POINTER_TOKEN`; `POINTER_SECRET` untuk kunci Flask.
- HTTPS self-signed dipakai untuk **local IP** (wajib bagi gyroscope di browser HP). Ngrok dipakai sebagai opsi akses jarak jauh.
- ⚠️ Jangan membuka server di jaringan publik tanpa memahami risikonya — token melindungi kontrol, bukan jaringan.

---

## 🛠️ Teknologi

- **Backend**: Python, Flask, Flask-SocketIO, PyAutoGUI, PyGetWindow, pyngrok
- **Frontend**: HTML5, CSS3 (glassmorphism), Vanilla JS (Socket.IO client, DeviceOrientationEvent)
- **Transport**: WebSocket (fallback long-polling)

---

## 📁 Struktur Proyek

```
pointer_PPT/
├── app.py              # Server Flask + Socket.IO + kontrol desktop
├── laser_overlay.py    # Overlay laser transparan di layar
├── templates/
│   └── index.html      # Halaman kontrol HP
├── static/
│   ├── css/style.css   # Styling glassmorphism
│   └── js/main.js      # Logika touchpad, gyro, socket
├── requirements.txt
└── run.bat
```

---

## 📜 Lisensi

Dikembangkan untuk keperluan pribadi. Gunakan dengan bijak.
