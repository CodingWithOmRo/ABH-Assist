$env:PATH += ";$PSScriptRoot\venv311\Lib\site-packages\nvidia\cublas\bin;$PSScriptRoot\venv311\Lib\site-packages\nvidia\cuda_runtime\bin"
& "$PSScriptRoot\venv311\Scripts\python.exe" -m streamlit run "$PSScriptRoot\app.py"
