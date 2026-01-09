import yaml
import os

CONFIG_PATH = "config.yaml"

def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r") as f:
            return yaml.safe_load(f)
    return {
        "model_path": "./models/model.gguf",
        "n_ctx": 2048,
        "n_gpu_layers": 0,
        "n_threads": None,
        "temperature": 0.1,
        "mode": "llama_cpp_python",
        "embedding_model": "intfloat/multilingual-e5-small",
        "chroma_db_path": "./chroma_db"
    }

config = load_config()
