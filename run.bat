@echo off
echo ===========================================
echo Menjalankan Pointer PPT Server...
echo ===========================================
call "d:\code\skripsi_spam\Code_Spam_Email\.venv\Scripts\activate.bat"
pip install Flask Flask-SocketIO pyautogui pygetwindow psutil qrcode[pil] eventlet pyopenssl
python app.py
pause
