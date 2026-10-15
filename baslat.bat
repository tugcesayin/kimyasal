@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not exist ".env" (
    copy ".env.ornek" ".env" >nul
    echo .env dosyasi olusturuldu. Not Defteri acilacak:
    echo GEMINI_API_KEY= satirina anahtarini yapistir, kaydet ve Not Defteri'ni kapat.
    notepad ".env"
)

if not exist ".venv\Scripts\python.exe" (
    echo Ilk kurulum yapiliyor, biraz surebilir...
    python -m venv .venv || py -m venv .venv
    if not exist ".venv\Scripts\python.exe" (
        echo Python bulunamadi. https://www.python.org/downloads/ adresinden kur,
        echo kurulumda "Add Python to PATH" kutucugunu isaretle.
        pause
        exit /b 1
    )
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
)

echo Site baslatiliyor: http://127.0.0.1:5000  (kapatmak icin bu pencereyi kapat)
start "" /min cmd /c "timeout /t 3 >nul & start http://127.0.0.1:5000"
".venv\Scripts\python.exe" app.py
pause
