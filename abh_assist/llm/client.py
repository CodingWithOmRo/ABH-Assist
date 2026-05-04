import requests
import json
import os
import sys
from abh_assist.config import config

# Fix for Windows: Add NVIDIA DLL paths from site-packages so llama-cpp-python can find them
if os.name == 'nt':
    try:
        # Attempt to find site-packages path
        site_packages = next((p for p in sys.path if 'site-packages' in p), None)
        if site_packages:
            cuda_dirs = [
                os.path.join(site_packages, 'nvidia', 'cuda_runtime', 'bin'),
                os.path.join(site_packages, 'nvidia', 'cublas', 'bin'),
                os.path.join(site_packages, 'nvidia', 'cudnn', 'bin')
            ]
            for d in cuda_dirs:
                if os.path.exists(d):
                    # Method 1: Python 3.8+ DLL directory
                    try:
                        os.add_dll_directory(d)
                    except Exception:
                        pass
                    # Method 2: Legacy PATH (crucial for some C++ loaders)
                    if d not in os.environ.get('PATH', ''):
                        os.environ['PATH'] = d + os.pathsep + os.environ.get('PATH', '')
    except Exception:
        pass

try:
    from llama_cpp import Llama
except ImportError:
    Llama = None

_model_instance = None

def get_model():
    global _model_instance
    if _model_instance:
        return _model_instance
        
    if config['mode'] == 'llama_cpp_python':
        if not Llama:
            raise ImportError("llama-cpp-python not installed.")
        try:
            _model_instance = Llama(
                model_path=config['model_path'],
                n_ctx=config['n_ctx'],
                n_gpu_layers=config.get('n_gpu_layers', 0),
                n_batch=config.get('n_batch', 512), # Pass batch size
                n_threads=config.get('n_threads', None),
                verbose=False
            )
        except Exception as e:
            print(f"Failed to load local model: {e}")
            return None
    return _model_instance

def run_llm(prompt, stop=None, max_tokens=1024):
    """
    Unified function to run LLM either via local library or server.
    """
    if config['mode'] == 'llama_cpp_python':
        llm = get_model()
        if not llm:
            return '{"error": "Model not loaded"}'
            
        output = llm(
            prompt,
            max_tokens=max_tokens,
            stop=stop or ["User:", "\n\n"],
            temperature=config['temperature'],
            top_p=config['top_p'],
            repeat_penalty=config['repeat_penalty'],
            echo=False
        )
        return output['choices'][0]['text']
        
    elif config['mode'] == 'llama_cpp_server':
        # OpenAI compatible endpoint
        url = f"{config['server_url']}/completions"
        payload = {
            "prompt": prompt,
            "max_tokens": max_tokens,
            "temperature": config['temperature'],
            "stop": stop or ["User:", "\n\n"]
        }
        try:
            resp = requests.post(url, json=payload)
            resp.raise_for_status()
            return resp.json()['choices'][0]['text']
        except Exception as e:
            return f'{{"error": "Server request failed: {e}"}}'
            
    return '{"error": "Invalid mode"}'
