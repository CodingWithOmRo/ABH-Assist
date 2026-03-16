# ABH-Assist

Ein lokaler, offline-fähiger Assistent für Ausländerbehörden-Aufnahmeprozesse.

## Features
- **Lokales LLM**: Verwendet `llama.cpp` für Datenschutz und Offline-Fähigkeit.
- **Dokumentenanalyse**: Klassifiziert Dokumente, extrahiert Text und prüft fehlende Unterlagen.
- **Akten-Verwaltung**: Erstellt und verwaltet Akten für jeden Antragsteller.
- **Intelligente Datenextraktion**: Extrahiert automatisch Namen, Geburtsdaten, Passnummern etc.
- **Konsistenzprüfung**: Vergleicht Reisepass-Daten mit Antragsformulardaten.
- **Checklisten**: Konfigurierbare YAML-Checklisten für verschiedene Falltypen.
- **RAG**: Retrieval Augmented Generation für konsistente Beratung.

## Hauptfunktionen

### 🏛️ Neue Analyse (Hauptseite)
- PDF-Dokumente per Drag & Drop hochladen
- Automatische Klassifizierung (Reisepass, Antrag, Mietvertrag, etc.)
- Extrahiert Antragstellername und erstellt automatisch eine Akte
- Prüft auf existierende Akten und bietet Aktualisierung an
- Vollständige Analyse mit Übersicht, Dokumentendetails, Konsistenzprüfung

### 📁 Akten-Übersicht
- Listet alle Akten im System
- Suchfunktion nach Name oder Akte-ID
- Filter nach Status (Neu, Unvollständig, Vollständig, Abgeschlossen)
- Klicken auf Namen öffnet die vollständige Akte

### 📄 Akte Details
- Vollständige Ansicht aller hochgeladenen Dokumente
- Status-Tracking (Neu → Unvollständig → Vollständig → Abgeschlossen)
- Übersicht fehlender Dokumente
- Konsistenzprüfung zwischen Reisepass und Antrag
- Offene Fragen für Antragsteller
- Aktennotiz-Entwurf (herunterladbar)

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
    ```powershell
    # Use venv311 environment with GPU support
    $env:PATH = "C:\Users\omidr\Feinprojekt\venv311\Lib\site-packages\llama_cpp\lib;C:\Users\omidr\Feinprojekt\venv311\Lib\site-packages\nvidia\cublas\bin;C:\Users\omidr\Feinprojekt\venv311\Lib\site-packages\nvidia\cuda_runtime\bin;C:\Users\omidr\Feinprojekt\venv311\Lib\site-packages\nvidia\cudnn\bin;" + $env:PATH
    & "C:\Users\omidr\Feinprojekt\venv311\Scripts\python.exe" -m streamlit run "C:\Users\omidr\Feinprojekt\app.py"
    ```

## Configuration
Edit `config.yaml` to change model parameters or paths.

## Evaluation
Run synthetic data generation:
```bash
python -m abh_assist.eval.synth_data
```
