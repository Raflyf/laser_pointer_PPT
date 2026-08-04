const socket = io();

// UI Elements
const statusText = document.getElementById('status-text');
const btnNext = document.getElementById('btn-next');
const btnPrev = document.getElementById('btn-prev');
const btnLaserPPT = document.getElementById('btn-laser-ppt');
const btnLaserGlobal = document.getElementById('btn-laser-global');
const btnModeTouch = document.getElementById('btn-mode-touch');
const btnModeGyro = document.getElementById('btn-mode-gyro');
const touchpadArea = document.getElementById('touchpad-area');
const gyroArea = document.getElementById('gyro-area');

// New Utility Buttons
const btnClickLeft = document.getElementById('btn-click-left');
const btnClickRight = document.getElementById('btn-click-right');
const btnEsc = document.getElementById('btn-esc');
const btnF5 = document.getElementById('btn-f5');

// State
let isLaserActive = false;
let activeLaserType = null; // 'ppt' or 'global'
let currentMode = 'touch'; // 'touch' or 'gyro'

// Gyroscope state
let prevBeta = null;
let prevGamma = null;
let smoothedDx = 0;
let smoothedDy = 0;
const EMA_ALPHA = 0.12; // Diturunkan agar pergerakan lebih berat dan tidak licin (0.0 sangat lambat, 1.0 sangat responsif)

// Touchpad state
let isTouching = false;
let lastTouchX = 0;
let lastTouchY = 0;

// Socket Connection Status
socket.on('connect', () => {
    statusText.innerText = 'Status: Connected';
    statusText.style.color = '#4ade80';
});

socket.on('disconnect', () => {
    statusText.innerText = 'Status: Disconnected';
    statusText.style.color = '#ef4444';
});

// PPT Status
socket.on('ppt_status', (data) => {
    if (data.active) {
        statusText.innerText = 'Status: Connected (PPT Aktif)';
        statusText.style.color = '#60a5fa';
    } else {
        statusText.innerText = 'Status: Connected (PPT Tidak Aktif)';
        statusText.style.color = '#4ade80';
    }
});

// --- Action Buttons ---
btnNext.addEventListener('click', () => socket.emit('action', { command: 'next' }));
btnPrev.addEventListener('click', () => socket.emit('action', { command: 'prev' }));
btnClickLeft.addEventListener('click', () => socket.emit('action', { command: 'left_click' }));
btnClickRight.addEventListener('click', () => socket.emit('action', { command: 'right_click' }));
btnEsc.addEventListener('click', () => socket.emit('action', { command: 'esc' }));
btnF5.addEventListener('click', () => socket.emit('action', { command: 'f5' }));

// --- Laser Toggle (Click to Toggle) ---
const toggleLaser = (type, btnElement) => {
    if (isLaserActive && activeLaserType === type) {
        // Matikan jika tipe yang sama diklik lagi
        isLaserActive = false;
        activeLaserType = null;
        btnElement.classList.remove('active-laser');
        socket.emit('laser_toggle', { state: false, type: type });
        prevBeta = null;
        prevGamma = null;
    } else {
        // Matikan tipe lain jika sedang aktif
        if (isLaserActive) {
            btnLaserPPT.classList.remove('active-laser');
            btnLaserGlobal.classList.remove('active-laser');
            socket.emit('laser_toggle', { state: false, type: activeLaserType });
        }
        // Aktifkan tipe baru
        isLaserActive = true;
        activeLaserType = type;
        btnElement.classList.add('active-laser');
        socket.emit('laser_toggle', { state: true, type: type });
        prevBeta = null; // Reset prev gyro to avoid jump
        prevGamma = null;
    }
};

btnLaserPPT.addEventListener('click', () => toggleLaser('ppt', btnLaserPPT));
btnLaserGlobal.addEventListener('click', () => toggleLaser('global', btnLaserGlobal));

// --- Mode Switching ---
btnModeTouch.addEventListener('click', () => {
    currentMode = 'touch';
    btnModeTouch.classList.add('active');
    btnModeGyro.classList.remove('active');
    touchpadArea.style.display = 'flex';
    gyroArea.style.display = 'none';
});

btnModeGyro.addEventListener('click', async () => {
    // Request iOS 13+ permission for DeviceOrientation
    if (typeof DeviceOrientationEvent !== 'undefined' && typeof DeviceOrientationEvent.requestPermission === 'function') {
        try {
            const permissionState = await DeviceOrientationEvent.requestPermission();
            if (permissionState !== 'granted') {
                alert('Izin sensor ditolak.');
                return;
            }
        } catch (error) {
            console.error(error);
            alert('Tidak bisa meminta izin sensor. Pastikan mengakses via HTTPS.');
            return;
        }
    }
    
    currentMode = 'gyro';
    btnModeGyro.classList.add('active');
    btnModeTouch.classList.remove('active');
    touchpadArea.style.display = 'none';
    gyroArea.style.display = 'flex';
    prevBeta = null;
    prevGamma = null;
});

// --- Touchpad Logic ---
let tapTimeout = null;
let lastTapTime = 0;
let tapMoved = false;
let touchStartX = 0;
let touchStartY = 0;
let touchStartTime = 0;

touchpadArea.addEventListener('touchstart', (e) => {
    e.preventDefault();
    isTouching = true;
    const touch = e.touches[0];
    lastTouchX = touch.clientX;
    lastTouchY = touch.clientY;
    
    touchStartX = touch.clientX;
    touchStartY = touch.clientY;
    touchStartTime = Date.now();
    tapMoved = false;
}, {passive: false});

touchpadArea.addEventListener('touchmove', (e) => {
    e.preventDefault();
    // Touchpad selalu merespons gerakan (always on) selama mode touch terpilih
    if (!isTouching || currentMode !== 'touch') return;
    
    const touch = e.touches[0];
    const dx = touch.clientX - lastTouchX;
    const dy = touch.clientY - lastTouchY;
    
    socket.emit('laser_move', { dx: dx, dy: dy });
    
    lastTouchX = touch.clientX;
    lastTouchY = touch.clientY;
    
    // Jika bergeser lebih dari 5 pixel, ini adalah pergerakan mouse, BUKAN tap/klik
    if (Math.abs(touch.clientX - touchStartX) > 5 || Math.abs(touch.clientY - touchStartY) > 5) {
        tapMoved = true;
    }
}, {passive: false});

touchpadArea.addEventListener('touchend', (e) => { 
    e.preventDefault();
    isTouching = false; 
    
    if (currentMode === 'touch' && !tapMoved) {
        const touchDuration = Date.now() - touchStartTime;
        
        // Mencegah long-press (tahan lama) dianggap sebagai tap/klik
        if (touchDuration < 250) {
            const currentTime = Date.now();
            
            // Jeda antar tap kurang dari 300ms = Double Tap (Klik Kanan)
            if (currentTime - lastTapTime < 300) {
                clearTimeout(tapTimeout);
                lastTapTime = 0; // Reset agar klik ke-3 tidak terhitung lagi
                socket.emit('action', { command: 'right_click' });
                showTouchpadFeedback("Klik Kanan");
            } else {
                // Tunggu 300ms, jika tidak ada tap ke-2, eksekusi Single Tap (Klik Kiri)
                lastTapTime = currentTime;
                tapTimeout = setTimeout(() => {
                    socket.emit('action', { command: 'left_click' });
                    showTouchpadFeedback("Klik Kiri");
                }, 300);
            }
        }
    }
});

touchpadArea.addEventListener('touchcancel', () => { isTouching = false; });

function showTouchpadFeedback(text) {
    const feedback = document.createElement('div');
    feedback.innerText = text;
    feedback.style.position = 'absolute';
    feedback.style.color = '#fff';
    feedback.style.background = 'rgba(59, 130, 246, 0.9)';
    feedback.style.padding = '6px 14px';
    feedback.style.borderRadius = '8px';
    feedback.style.fontSize = '12px';
    feedback.style.fontWeight = 'bold';
    feedback.style.pointerEvents = 'none';
    feedback.style.transition = 'opacity 0.8s ease';
    feedback.style.boxShadow = '0 4px 12px rgba(0,0,0,0.3)';
    feedback.style.zIndex = '100';
    
    touchpadArea.style.position = 'relative'; 
    touchpadArea.appendChild(feedback);
    
    setTimeout(() => {
        feedback.style.opacity = '0';
    }, 200);
    
    setTimeout(() => feedback.remove(), 1000);
}

// --- Gyroscope Logic ---
window.addEventListener('deviceorientation', (e) => {
    // MENCEGAH BUG "TOO MANY PACKETS" (CRASH SERVER):
    // Jangan kirim paket gyro jika browser/tab sedang diminimize atau HP dilock.
    if (document.hidden) return;
    
    if (currentMode !== 'gyro' || !isLaserActive) return;
    
    let alpha = e.alpha;
    let beta = e.beta;
    let gamma = e.gamma;
    
    if (prevBeta !== null && prevGamma !== null) {
        let dBeta = beta - prevBeta;
        let dGamma = gamma - prevGamma;
        
        // Fix 360 wrap-around
        if (dGamma > 180) dGamma -= 360;
        if (dGamma < -180) dGamma += 360;
        if (dBeta > 180) dBeta -= 360;
        if (dBeta < -180) dBeta += 360;
        
        // --- ANTI-GIMBAL-LOCK / JUMP FILTER ---
        // Jika perbedaan rotasi dalam hitungan milidetik sangat ekstrem (>30 derajat),
        // ini secara fisik mustahil untuk tangan manusia. Ini adalah efek 'Gimbal Lock'
        // saat HP berpindah kutub (vertikal ke horizontal). Abaikan frame ini.
        if (Math.abs(dGamma) > 30 || Math.abs(dBeta) > 30) {
            prevBeta = beta;
            prevGamma = gamma;
            return;
        }

        // Sensitivitas diturunkan agar tidak terlalu licin
        const gyroSensitivity = 7.0; 
        
        let rawDx = dGamma * gyroSensitivity;
        let rawDy = -dBeta * gyroSensitivity; // Invert Y
        
        // --- DEADZONE FILTER ---
        // Jika pergerakan sangat kecil (getaran tangan), abaikan untuk mencegah kursor jalan sendiri
        if (Math.abs(rawDx) < 0.8) rawDx = 0;
        if (Math.abs(rawDy) < 0.8) rawDy = 0;
        
        // --- EXPONENTIAL MOVING AVERAGE (EMA) ---
        // Menghilangkan getaran tremor tangan, membuat pergerakan mulus seperti mouse
        smoothedDx = (EMA_ALPHA * rawDx) + ((1 - EMA_ALPHA) * smoothedDx);
        smoothedDy = (EMA_ALPHA * rawDy) + ((1 - EMA_ALPHA) * smoothedDy);
        
        // Kirim data jika kursor benar-benar bergerak
        if (Math.abs(smoothedDx) > 0.02 || Math.abs(smoothedDy) > 0.02) {
            socket.emit('laser_move', { dx: smoothedDx, dy: smoothedDy });
        }
    }
    
    prevBeta = beta;
    prevGamma = gamma;
});

// Reset gyro prev variables ketika kembali ke layar
document.addEventListener("visibilitychange", () => {
    if (!document.hidden) {
        prevBeta = null;
        prevGamma = null;
        smoothedDx = 0;
        smoothedDy = 0;
    }
});
