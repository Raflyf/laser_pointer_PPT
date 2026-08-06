// WebSocket murni utama (latensi rendah); fallback ke polling bila WS ditolak (M5).
const socket = io({
    transports: ['websocket', 'polling'],
    upgrade: true,
    auth: { token: window.POINTER_TOKEN },
});

// =============================================
// DOM References
// =============================================
const statusText      = document.getElementById('status-text');
const btnNext         = document.getElementById('btn-next');
const btnPrev         = document.getElementById('btn-prev');
const btnLaserPPT     = document.getElementById('btn-laser-ppt');
const btnLaserGlobal  = document.getElementById('btn-laser-global');
const btnModeTouch    = document.getElementById('btn-mode-touch');
const btnModeGyro     = document.getElementById('btn-mode-gyro');
const touchpadArea    = document.getElementById('touchpad-area');
const gyroArea        = document.getElementById('gyro-area');
const btnClickLeft    = document.getElementById('btn-click-left');
const btnClickRight   = document.getElementById('btn-click-right');
const btnEsc          = document.getElementById('btn-esc');
const btnF5           = document.getElementById('btn-f5');
const btnRecenter     = document.getElementById('btn-recenter');

// =============================================
// State
// =============================================
let isLaserActive    = false;
let activeLaserType  = null;   // 'ppt' | 'global'
let currentMode      = 'touch'; // 'touch' | 'gyro'

// Gyroscope absolute state
let centerBeta   = null;
let centerGamma  = null;
let lastRawBeta  = 0;
let lastRawGamma = 0;
let smoothAbsX   = 0;
let smoothAbsY   = 0;
const GYRO_EMA      = 0.20;
const GYRO_DEADZONE = 0.05;  // derajat, hanya filter wobble diam, tidak mengunci pointer di tengah

// Touchpad state
let isTouching    = false;
let lastTouchX    = 0;
let lastTouchY    = 0;
let tapMoved      = false;
let touchStartX   = 0;
let touchStartY   = 0;
let touchStartTime = 0;
let tapTimeout    = null;
let lastTapTime   = 0;

// --- Touchpad Emit Throttle ---
// Kirim maksimum setiap 8ms (125Hz). Jika touchmove lebih cepat, delta di-akumulasi
// agar tidak ada gerakan yang hilang (berbeda dengan RAF yang membuang intermediate moves).
let lastTouchEmit = 0;
let accDx = 0;
let accDy = 0;
const TOUCH_MIN_INTERVAL = 6; // ms — sesuai 144Hz display (~6.9ms/frame)

//--- 2-Jari Scroll state ---
let scrollAcc = 0;
let lastScrollY = null;
let scrollVelocity = 0;    // kecepatan scroll per-frame (unit), untuk inertia
let momentumFrame = null;  // id rAF inertia scroll
const SCROLL_MIN_INTERVAL = 16; // 60Hz

// --- Gyro Emit Throttle (Absolute Mode) ---
// Gyro hanya butuh posisi terbaru (latest-wins), cukup throttle tanpa akumulasi.
let lastGyroEmit = 0;
const GYRO_MIN_INTERVAL = 6; // ms — gyro hardware HP ~60Hz, tapi kirim setiap frame layar 144Hz

// =============================================
// Socket Events
// =============================================
socket.on('connect', () => {
    setStatus('Terhubung', 'connected');
});

socket.on('disconnect', () => {
    setStatus('Terputus', '');
});

// M5: tampilkan pesan jelas saat koneksi gagal / token ditolak
socket.on('connect_error', (err) => {
    const rejected = err && err.message && /rejected|token/i.test(err.message);
    setStatus(rejected ? 'Koneksi ditolak (token salah)' : 'Gagal terhubung', '');
});

socket.on('ppt_status', ({ active }) => {
    if (active) {
        setStatus('Terhubung - PPT Aktif', 'ppt-active');
    } else {
        setStatus('Terhubung', 'connected');
    }
});

function setStatus(text, cls) {
    statusText.textContent = text;
    statusText.className = 'status ' + cls;
}

// =============================================
// Action Buttons
// =============================================
const actions = {
    'next':        btnNext,
    'prev':        btnPrev,
    'left_click':  btnClickLeft,
    'right_click': btnClickRight,
    'esc':         btnEsc,
    'f5':          btnF5,
};

Object.entries(actions).forEach(([command, btn]) => {
    btn.addEventListener('click', () => socket.emit('action', { command }));
});

// =============================================
// Laser Toggle
// =============================================
function setLaserOff(type) {
    isLaserActive   = false;
    activeLaserType = null;
    socket.emit('laser_toggle', { state: false, type });
    resetLaserState();
}

function setLaserOn(type, btnEl) {
    if (isLaserActive) {
        // Matikan laser yang sedang aktif dulu
        [btnLaserPPT, btnLaserGlobal].forEach(b => b.setAttribute('aria-pressed', 'false'));
        socket.emit('laser_toggle', { state: false, type: activeLaserType });
    }
    isLaserActive   = true;
    activeLaserType = type;
    btnEl.setAttribute('aria-pressed', 'true');
    socket.emit('laser_toggle', { state: true, type });
    resetLaserState();
}

function resetLaserState() {
    // Reset gyro absolut agar tidak lompat saat laser diaktifkan ulang
    centerBeta  = null;
    centerGamma = null;
    smoothAbsX  = 0;
    smoothAbsY  = 0;
}

btnLaserPPT.addEventListener('click', () => {
    if (isLaserActive && activeLaserType === 'ppt') {
        btnLaserPPT.setAttribute('aria-pressed', 'false');
        setLaserOff('ppt');
    } else {
        [btnLaserPPT, btnLaserGlobal].forEach(b => b.setAttribute('aria-pressed', 'false'));
        setLaserOn('ppt', btnLaserPPT);
    }
});

btnLaserGlobal.addEventListener('click', () => {
    if (isLaserActive && activeLaserType === 'global') {
        btnLaserGlobal.setAttribute('aria-pressed', 'false');
        setLaserOff('global');
    } else {
        [btnLaserPPT, btnLaserGlobal].forEach(b => b.setAttribute('aria-pressed', 'false'));
        setLaserOn('global', btnLaserGlobal);
    }
});

// =============================================
// Mode Switching
// =============================================
btnModeTouch.addEventListener('click', () => {
    currentMode = 'touch';
    btnModeTouch.classList.add('active');
    btnModeTouch.setAttribute('aria-pressed', 'true');
    btnModeGyro.classList.remove('active');
    btnModeGyro.setAttribute('aria-pressed', 'false');
    touchpadArea.style.display = 'flex';
    touchpadArea.removeAttribute('aria-hidden');
    gyroArea.style.display = 'none';
    gyroArea.setAttribute('aria-hidden', 'true');
});

btnModeGyro.addEventListener('click', async () => {
    // iOS 13+ permission
    if (typeof DeviceOrientationEvent !== 'undefined' &&
        typeof DeviceOrientationEvent.requestPermission === 'function') {
        try {
            const state = await DeviceOrientationEvent.requestPermission();
            if (state !== 'granted') {
                alert('Izin sensor gyroscope ditolak.');
                return;
            }
        } catch (err) {
            alert('Akses sensor memerlukan HTTPS.');
            return;
        }
    }

    currentMode = 'gyro';
    btnModeGyro.classList.add('active');
    btnModeGyro.setAttribute('aria-pressed', 'true');
    btnModeTouch.classList.remove('active');
    btnModeTouch.setAttribute('aria-pressed', 'false');
    touchpadArea.style.display = 'none';
    touchpadArea.setAttribute('aria-hidden', 'true');
    gyroArea.style.display = 'flex';
    gyroArea.removeAttribute('aria-hidden');
    resetLaserState();
});

// =============================================
// Touchpad - Gerakan
// =============================================
touchpadArea.addEventListener('touchstart', (e) => {
    e.preventDefault();
    isTouching = true;
    if (momentumFrame) { cancelAnimationFrame(momentumFrame); momentumFrame = null; }
    const t = e.touches[0];
    lastTouchX = touchStartX = t.clientX;
    lastTouchY = touchStartY = t.clientY;
    touchStartTime = Date.now();
    tapMoved = false;
    lastScrollY = null;
    scrollAcc = 0;
    scrollVelocity = 0;
    touchpadArea.classList.add('active-drag');
}, { passive: false });

touchpadArea.addEventListener('touchmove', (e) => {
    e.preventDefault();
    if (!isTouching || currentMode !== 'touch') return;

    // 2-jari scroll gesture
    if (e.touches.length >= 2) {
        const avgY = (e.touches[0].clientY + e.touches[1].clientY) / 2;
        if (lastScrollY !== null) {
            // Arah: geser jari ke bawah = konten naik (wheel-up), sama touchpad fisik klasik.
            // Akumulator fractional: semua delta tersimpan (termasuk sisa <1 unit) sehingga
            // gerak pelan tidak hilang dan scroll terlihat mulus seperti wheel fisik.
            const SCROLL_PX_PER_UNIT = 0.7;  // piksel jari per 1 notch wheel (2.2 terlalu berat)
            scrollAcc += (avgY - lastScrollY) / SCROLL_PX_PER_UNIT;
            const now = performance.now();
            if (now - lastTouchEmit >= SCROLL_MIN_INTERVAL) {
                const whole = Math.trunc(scrollAcc);
                if (whole !== 0) {
                    const unit = Math.max(-120, Math.min(120, whole));
                    socket.emit('action', { command: 'scroll', dy: unit });
                    scrollAcc -= whole;                           // simpan sisa fractional untuk frame berikutnya
                    scrollVelocity = whole;                       // track kecepatan untuk inertia
                    lastTouchEmit = now;
                }
            }
        }
        lastScrollY = avgY;
        lastTouchX = e.touches[0].clientX;
        lastTouchY = e.touches[0].clientY;
        tapMoved = true;
        return;
    }
    lastScrollY = null;

    const t = e.touches[0];
    const dx = t.clientX - lastTouchX;
    const dy = t.clientY - lastTouchY;

    accDx += dx;
    accDy += dy;

    const now = performance.now();
    if (now - lastTouchEmit >= TOUCH_MIN_INTERVAL) {
        if (accDx !== 0 || accDy !== 0) {
            socket.emit('laser_move', { dx: accDx, dy: accDy });
        }
        accDx = 0;
        accDy = 0;
        lastTouchEmit = now;
    }

    lastTouchX = t.clientX;
    lastTouchY = t.clientY;

    if (Math.abs(t.clientX - touchStartX) > 6 || Math.abs(t.clientY - touchStartY) > 6) {
        tapMoved = true;
    }
}, { passive: false });

touchpadArea.addEventListener('touchend', (e) => {
    e.preventDefault();
    isTouching = false;
    lastScrollY = null;
    scrollAcc = 0;
    touchpadArea.classList.remove('active-drag');

    // Inertia scroll: lepas cepat → lajut scroll dengan kecepatan meluruh (momentum).
    if (currentMode === 'touch' && Math.abs(scrollVelocity) >= 4) {
        let vel = scrollVelocity;
        let frames = 0;
        const decay = () => {
            if (frames >= 90) { scrollVelocity = 0; return; }  // batas maks
            frames++;
            const v = (vel *= 0.88);
            if (Math.abs(v) < 0.5) { scrollVelocity = 0; return; }
            socket.emit('action', { command: 'scroll', dy: Math.trunc(v) });
            momentumFrame = requestAnimationFrame(decay);
        };
        momentumFrame = requestAnimationFrame(decay);
        scrollVelocity = 0;
    }

    if (currentMode === 'touch' && !tapMoved) {
        const duration = Date.now() - touchStartTime;
        if (duration < 250) {
            const now = Date.now();
            if (now - lastTapTime < 320) {
                // Double tap = klik kanan
                clearTimeout(tapTimeout);
                lastTapTime = 0;
                socket.emit('action', { command: 'right_click' });
                showTapFeedback('Klik Kanan', touchpadArea);
            } else {
                // Tunggu untuk konfirmasi double tap
                lastTapTime = now;
                tapTimeout = setTimeout(() => {
                    socket.emit('action', { command: 'left_click' });
                    showTapFeedback('Klik Kiri', touchpadArea);
                }, 320);
            }
        }
    }
}, { passive: false });

touchpadArea.addEventListener('touchcancel', () => {
    isTouching = false;
    touchpadArea.classList.remove('active-drag');
});

// =============================================
// Gyroscope Recenter
// =============================================
if (btnRecenter) {
    btnRecenter.addEventListener('click', () => {
        centerBeta  = lastRawBeta;
        centerGamma = lastRawGamma;
        smoothAbsX  = 0;
        smoothAbsY  = 0;
        socket.emit('laser_move', { absolute: true, dGamma: 0, dBeta: 0 });
        showTapFeedback('Tengah Terkunci', gyroArea, true);
    });
}

// =============================================
// Gyroscope - Absolute Mode
// =============================================
window.addEventListener('deviceorientation', (e) => {
    if (document.hidden) return;
    if (currentMode !== 'gyro' || !isLaserActive) return;

    const beta  = e.beta;
    const gamma = e.gamma;

    lastRawBeta  = beta;
    lastRawGamma = gamma;

    // Auto-set titik tengah saat pertama kali aktif
    if (centerBeta === null) {
        centerBeta  = beta;
        centerGamma = gamma;
        return;
    }

    let dBeta  = beta  - centerBeta;
    let dGamma = gamma - centerGamma;

    // Normalisasi wrap-around
    if (dGamma >  180) dGamma -= 360;
    if (dGamma < -180) dGamma += 360;
    if (dBeta  >  180) dBeta  -= 360;
    if (dBeta  < -180) dBeta  += 360;

    // EMA smoothing pada sudut absolut
    smoothAbsX = GYRO_EMA * dGamma + (1 - GYRO_EMA) * smoothAbsX;
    smoothAbsY = GYRO_EMA * dBeta  + (1 - GYRO_EMA) * smoothAbsY;

    // Deadzone halus pada hasil akhir: tekan wobble mikro tanpa menempel di tengah
    if (Math.abs(smoothAbsX) < GYRO_DEADZONE) smoothAbsX = 0;
    if (Math.abs(smoothAbsY) < GYRO_DEADZONE) smoothAbsY = 0;

    const nowGyro = performance.now();
    if (nowGyro - lastGyroEmit >= GYRO_MIN_INTERVAL) {
        socket.emit('laser_move', { absolute: true, dGamma: smoothAbsX, dBeta: smoothAbsY });
        lastGyroEmit = nowGyro;
    }
});

// Reset center saat tab kembali aktif dari background
document.addEventListener('visibilitychange', () => {
    if (!document.hidden) {
        centerBeta  = null;
        centerGamma = null;
    }
});

// =============================================
// Utility: Tap Feedback Toast
// =============================================
function showTapFeedback(text, container, isSuccess = false) {
    const el = document.createElement('span');
    el.className = 'tap-feedback' + (isSuccess ? ' recenter-feedback' : '');
    el.textContent = text;

    container.appendChild(el);

    requestAnimationFrame(() => {
        requestAnimationFrame(() => el.classList.add('fade'));
    });

    setTimeout(() => el.remove(), 700);
}
