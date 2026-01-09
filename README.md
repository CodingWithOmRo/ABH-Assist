# ABH-Assist (PoC)

A local, offline-first assistant for Ausländerbehörde intake processes.

## Features
- **Local LLM**: Uses `llama.cpp` for privacy and offline capability.
- **Document Analysis**: Classifies documents, extracts text, and checks for missing items.
- **Checklists**: Configurable YAML checklists for different case types.
- **RAG**: Retrieval Augmented Generation for consistent guidance.

## Setup

1.  **Install Python 3.11+**
2.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```
    *Note: For OCR support, install Tesseract and add it to your PATH.*

3.  **Download Model**:
    Download a GGUF model (e.g., Mistral-7B-Instruct or Llama-3-8B-Instruct) and place it in `models/`.
    Update `config.yaml` with the filename.

4.  **Run Application**:
    ```bash
    streamlit run app.py
    ```

## Configuration
Edit `config.yaml` to change model parameters or paths.

## Evaluation
Run synthetic data generation:
```bash
python -m abh_assist.eval.synth_data
```
