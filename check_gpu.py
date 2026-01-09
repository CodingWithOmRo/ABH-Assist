import os
import sys

# Add DLL paths for CUDA 12 runtime
base_dir = os.path.dirname(os.path.abspath(__file__))
venv_path = os.path.join(base_dir, "venv311")
dll_paths = [
    os.path.join(venv_path, "Lib", "site-packages", "nvidia", "cublas", "bin"),
    os.path.join(venv_path, "Lib", "site-packages", "nvidia", "cuda_runtime", "bin"),
]

print("Checking environment...")
for p in dll_paths:
    if os.path.exists(p):
        print(f"Adding DLL path: {p}")
        try:
            os.add_dll_directory(p)
        except AttributeError:
            # Python < 3.8 or non-Windows
            os.environ["PATH"] += os.pathsep + p
    else:
        print(f"Warning: DLL path not found: {p}")

try:
    from llama_cpp import Llama
    print("\nSUCCESS: llama_cpp module imported.")
except ImportError as e:
    print(f"\nERROR: Could not import llama_cpp. {e}")
    sys.exit(1)

model_path = os.path.join(base_dir, "models", "mistral-7b-instruct-v0.2.Q4_K_M.gguf")

if not os.path.exists(model_path):
    print(f"Model not found at {model_path}")
    sys.exit(1)

print(f"\nLoading model from {model_path} with n_gpu_layers=-1...")

try:
    llm = Llama(
        model_path=model_path,
        n_gpu_layers=-1, # Offload all layers
        verbose=True
    )
    print("\nModel loaded successfully!")
    print("Check the output above for 'BLAS = 1' to confirm GPU usage.")
    
except Exception as e:
    print(f"Failed to load model: {e}")
