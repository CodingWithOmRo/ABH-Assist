import os
import sys
import ctypes

print(f"Python Executable: {sys.executable}")
print(f"Python Version: {sys.version}")

# 1. Find site-packages
site_packages = next((p for p in sys.path if 'site-packages' in p), None)
print(f"Found site-packages: {site_packages}")

if site_packages:
    # 2. Check for NVIDIA DLLs
    cuda_dirs = [
        os.path.join(site_packages, 'nvidia', 'cuda_runtime', 'bin'),
        os.path.join(site_packages, 'nvidia', 'cublas', 'bin'),
        os.path.join(site_packages, 'nvidia', 'cudnn', 'bin')
    ]
    
    found_dlls = []
    for d in cuda_dirs:
        if os.path.exists(d):
            print(f"Found directory: {d}")
            # List DLLs
            dlls = [f for f in os.listdir(d) if f.endswith('.dll')]
            print(f"  DLLs: {dlls}")
            
            # Try adding to DLL directory
            try:
                os.add_dll_directory(d)
                print(f"  Successfully added to DLL directory")
            except Exception as e:
                print(f"  Failed to add DLL directory: {e}")
            
            # Also add to PATH for good measure (legacy support)
            os.environ['PATH'] = d + os.pathsep + os.environ['PATH']
            
            found_dlls.extend([os.path.join(d, f) for f in dlls])
        else:
            print(f"Directory not found: {d}")

    # 3. Try to load cudart explicitly
    cudart = next((f for f in found_dlls if 'cudart64' in f), None)
    if cudart:
        print(f"Attempting to load: {cudart}")
        try:
            ctypes.CDLL(cudart)
            print("  Successfully loaded cudart64")
        except Exception as e:
            print(f"  Failed to load cudart64: {e}")

# 4. Try importing llama_cpp
print("\nAttempting to import llama_cpp...")
try:
    from llama_cpp import Llama
    print("SUCCESS: llama_cpp imported!")
except Exception as e:
    print(f"FAILURE: {e}")
