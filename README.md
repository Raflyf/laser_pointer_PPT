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

## Changelog

### 2026-08-05 — Ngrok tidak lagi jadi ghost saat Ctrl+C
- **Fix:** `cleanup` kini setelah `ngrok.kill()` juga menyapu paksa semua proses `ngrok.exe` via psutil — Ctrl+C dijamin tidak menyisakan ghost ngrok.
- **Fix:** Tunnel ngrok gagal dengan `ERR_NGROK_334` karena `ngrok.exe` ghost dari sesi sebelumnya masih memegang endpoint. Sapuan ghost saat startup kini juga membunuh `ngrok.exe`.
- **Fix:** `cleanup` kini terminate -> wait -> kill paksa subproses `laser_overlay.py` (tidak ada ghost saat Ctrl+C).
- **Fix:** Tambah handler `SIGBREAK` dan `atexit` agar cleanup tetap jalan walau proses ditutup paksa.
- **Fix:** Saat server start, sapu otomatis `laser_overlay.py` sisa dari sesi sebelumnya (tidak menumpuk ghost).

### 2026-08-05 — Fix Gyro "Stuck" di Tengah Layar
- **Fix:** Hilangkan guard backend `<1.0°` yang memblokir pergerakan — pointer tidak lagi "menempel" saat melintasi/berhenti di tengah layar.
- **Fix:** Deadzone dipindah dari input mentah ke hasil akhir EMA dan diturunkan `1.2°` -> `0.4°` — meredam wobble mikro tanpa mengunci pointer.
- **Fix:** Tombol **Bidik Tengah** kini langsung mengirim `dGamma=0, dBeta=0` sehingga kursor pindah ke tengah seketika saat diklik.

### 2026-08-05 — Audit & Perbaikan Logika
- **Fix:** Deteksi status PPT hanya menyala saat jendela *PowerPoint Slide Show* benar-benar terbuka (sebelumnya mode editing terhitung "aktif").
- **Fix:** Hilangkan variabel mati `primary_url`.
- **Fix:** Validasi tipe payload di semua handler Socket.IO (`action`, `laser_toggle`, `laser_move`) — payload tak valid tidak lagi memicu exception.
- **Fix:** Kursor tidak lagi tersnap ke tengah layar saat gyro baru aktif/netral.
- **Improvisasi:** Deadzone sensor gyro (1.2°) untuk membunuh jitter mikro saat HP diam.
- **Improvisasi:** EMA gyro dinaikkan `0.15` -> `0.20` agar pelacakan lebih responsif.
- **Improvisasi:** Event `laser_move` tidak lagi dikirim saat delta nol (jari diam) — mengurangi beban jaringan dan gerakan bergetar.
