@echo off
set PYTHONPATH=%~dp0;%~dp0container
set PATH=%~dp0python312;%~dp0python312\Library\bin;%PATH%
%~dp0python312\python.exe %~dp0__main__.py
