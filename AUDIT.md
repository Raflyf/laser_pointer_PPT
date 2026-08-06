# Audit Full Project — Pointer PPT

Tanggal: 2026-08-06
Scope: app.py (349), laser_overlay.py (45), templates/index.html (85), static/js/main.js (385), static/css/style.css (363), README.md, requirements.txt

Ringkasan: **1 high, 6 medium, 4 low**. Aplikasi berfungsi baik; risiko dominan keamanan jaringan (tool remote tanpa auth) dan ketahanan koneksi.

> **STATUS: SEMUA FIXED (2026-08-06).** H1, M1-M7, L2, L4 diperbaiki. L1 dicorek (false positive: `_screen_w/_screen_h` memang dipakai di `_apply_cursor_move:100-101`). L3 diterima (wajar). Lihat README changelog.

---

## HIGH

### H1. Remote control tanpa autentikasi, CORS terbuka, bind 0.0.0.0
`app.py:31` `cors_allowed_origins="*"` + `app.py:348` bind `0.0.0.0` + HTTPS adhoc self-signed. Siapa pun di jaringan yang tahu/scan port bisa:
- gerakkan kursor (`laser_move`), klik, tekan tombol (`action`), jalankan hotkey Ctrl+L
- memicu proses `laser_overlay` berulang

Lokal/pribadi wajar, tapi di Wi-Fi publik = kendali mesin oleh orang asing.

**Fix minimal:** batasi listener ke `127.0.0.1` + `stun/ngrok` tetap sebagai satu-satunya jalur remote (ngrok sudah beri URL unik). Atau tambah token sederhana di header/query saat koneksi WebSocket. `ponytail:` auth penuh tidak perlu untuk tool pribadi; satu secret cukup.

---

## MEDIUM

### M1. Secret key hardcoded
`app.py:27` `SECRET_KEY = 'pointer-secret-key'`. App tidak memakai session login, jadi risiko rendah. Ganti env bila dipublikasikan.

### M2. Belasan `except Exception: pass` menelan error
`app.py:95,110,159,195,198,203,212,214,235,237,303`. Error tersembunyi → sulit debug (sesuai dengan pola "silent failure"). Minimal `logger.exception()` di cabang penting (laser toggle, cursor move, QR).

### M3. Tidak ada rate-limit/throttle command
`handle_action` (`app.py:125-138`) mengeksekusi keystroke tanpa batas. Socket flood = rentetan keypress. `scroll` sudah clamp `-50..50` (baik), tapi `next/prev/click` tidak. Tambah throttle per-deteksi-ketik (mis. min interval antar aksi 30-50ms).

### M4. `terminate()` tanpa kill tree untuk laser_overlay
`app.py:166` `laser_process.terminate()` hanya kirim sinyal ke parent. Di Windows, `tkinter` child/proses turunan bisa tertinggal (riwayat commit "sweep orphan laser_overlay" menunjukkan ini pernah terjadi). Pakai `taskkill /F /T` atau tunggu `poll()` + timeout, lalu kill tree.

### M5. WebSocket-only, tanpa fallback polling
`main.js:2` `transports: ['websocket'], upgrade: false`. Jika WS ditolak (proxy ketat, mobile network), app mati total tanpa pesan. Tambah fallback `polling` atau minimal tampilkan status error saat koneksi gagal. (Ada trade-off latency — sengaja, tapi perlu pesan gagal koneksi yang jelas.)

### M6. `user-scalable=no` + `maximum-scale=1.0` — WCAG 1.4.4
`index.html:5` mematikan zoom. Melanggar WCAG 1.4.4 (Resize Text). Hierarki a11y di AGENTS.md menang mutlak. Hapus `user-scalable=no`; UI sudah responsif. iOS Safari tetap izin pinch tanpa meta ini.

### M7. Tidak ada `aria-live` untuk status
`status-text` mengubah teks status koneksi/gesek tanpa `aria-live="polite"` → pengguna screen reader tak dapat update. Tambahkan `aria-live="polite"` pada elemen status.

---

## LOW

### L1. `_screen_w/_screen_h` cache tak terpakai
`app.py:49` diset tapi tidak dipakai di mana pun. Kandidat hapus (YAGNI) atau pakai untuk clamp.

### L2. Google Fonts external tanpa `fallback` lokal
`index.html:9-11`. Saat offline/ngrok terbatas, font jatuh ke sistem. Wajar, tapi jadi dependensi eksternal tambahan.

### L3. Hardcoded title window untuk FindWindow
`laser_overlay.py:32` cocokkan title "pointer_ppt_laser_overlay". Rapuh jika title berubah; acceptable.

### L4. README ringkas (59 baris)
README sudah catat riwayat fix. Tidak ada bagian "cara pakai", keamanan (H1), atau struktur. Tambah bagian cara pakai + limitasi.

---

## Yang Sudah Baik (pertahankan)
- Queue `maxsize=1` + thread kursor dedicated → gerakan mulus bebas backlog (`app.py:54-63`).
- Clamp gyro `FOV_X/FOV_Y`, deadzone 0.05° tanpa center-lock.
- EMA smoothing gyro, throttle emit (`main.js` GYRO_MIN_INTERVAL).
- `prefers-reduced-motion` dihormati (`style.css:357`).
- Validasi tipe payload semua handler Socket.IO (fix sebelumnya).
- Validasi `scroll` clamp `-50..50`.
- Pemisahan dual-listener HTTPS-local + HTTP-ngrok terdokumentasi.

---

## Rekomendasi Prioritas
1. H1 → token sederhana / batasi bind (dulu, jika dipakai di jaringan publik).
2. M3 rate-limit action, M4 kill-tree overlay (stabilitas).
3. M5 fallback + pesan koneksi, M6-M7 a11y (murah, langsung).
4. M2 logging error (maintainability).

Selesai audit. Update dokumentasi wajib per aturan global.
