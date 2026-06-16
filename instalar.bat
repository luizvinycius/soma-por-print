@echo off
echo ============================================
echo  Soma por Print - Instalacao de dependencias
echo ============================================
echo.
echo Instalando pacotes Python...
pip install pytesseract Pillow pynput pystray mss
echo.
echo --------------------------------------------
echo IMPORTANTE: Instale tambem o Tesseract OCR
echo --------------------------------------------
echo Baixe em:
echo https://github.com/UB-Mannheim/tesseract/wiki
echo.
echo Caminho esperado apos instalacao:
echo C:\Program Files\Tesseract-OCR\tesseract.exe
echo.
echo Se instalar em outro caminho, edite a linha
echo "tesseract_cmd" no arquivo ocr.py
echo.
pause
