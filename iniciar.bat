@echo off
cd /d "%~dp0"
echo Iniciando Soma por Print...
echo O icone aparecera na bandeja do sistema (canto inferior direito).
echo Se nao aparecer, clique na seta "^" ao lado do relogio.
echo.
start "" pythonw main.py
timeout /t 3 /nobreak >nul
