@echo off
set PATH=%PATH%;%~dp0venv311\Lib\site-packages\nvidia\cublas\bin;%~dp0venv311\Lib\site-packages\nvidia\cuda_runtime\bin
"%~dp0venv311\Scripts\python.exe" "%~dp0check_gpu.py"
pause
