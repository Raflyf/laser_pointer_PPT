# Pointer PPT & Laser Remote

Aplikasi web-based untuk mengontrol presentasi PowerPoint dari handphone melalui jaringan lokal (WiFi).

## Fitur
1. **Deteksi PPT Otomatis:** UI di HP akan mendeteksi apakah presentasi sedang berjalan di laptop.
2. **Navigasi:** Tombol "Next" dan "Previous" yang responsif.
3. **Laser Pointer Mode:** Tahan tombol laser (akan memicu `Ctrl+L` di PPT).
4. **Gyroscope Control:** Arahkan HP untuk menggerakkan kursor laser.
5. **Touchpad Control:** Mode geser sentuh yang lebih presisi (alternatif gyroscope).

## Cara Penggunaan
1. Pastikan laptop dan HP terhubung di **jaringan WiFi yang sama** (atau hotspot).
2. Jalankan `run.bat`.
3. Akan muncul QR Code dan IP di terminal laptop (misal: `https://192.168.1.5:5000`).
4. Scan QR Code menggunakan HP.
5. Jika muncul peringatan keamanan *"Connection is not private"*, klik **Advanced** lalu **Proceed**. (Ini wajar karena menggunakan Adhoc SSL untuk HTTPS yang wajib bagi sensor Gyroscope di HP).
6. Buka file PowerPoint di laptop Anda dan masuk ke mode presentasi (`F5`).
7. Gunakan HP untuk mengontrol slide dan laser pointer.

## Teknologi
- **Backend:** Python, Flask, Flask-SocketIO, PyAutoGUI, PyGetWindow.
- **Frontend:** HTML5, CSS3 (Glassmorphism), Vanilla JS (Socket.io-client, DeviceOrientationEvent).
