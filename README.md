# ABH-Assist

ABH-Assist is an offline-capable MVP for **goal-based chronology extraction** from large digital immigration case files.

The product focus is not a generic office assistant. The core workflow is:

1. Upload a large digital case file.
2. Enter a goal such as `Aufenthaltsbeendigung`.
3. Extract every dated event, decision, document reference, and surrounding circumstance that could matter for that goal.
4. Sort the results chronologically.
5. Review the evidence, weak spots, and coverage warnings before using the output in case work.

The system is intentionally **recall-first**:

- If a dated entry might be relevant, it should usually be included.
- False positives are preferable to missing a relevant event.
- Every entry should remain traceable to a source document and, where possible, a page reference.

## MVP Capabilities

- Local LLM execution via `llama.cpp` or `llama-cpp-python`
- PDF and image text extraction with OCR fallback
- Goal-based extraction of dated case events
- Chronological timeline generation across many documents
- Source evidence snippets and document/page references
- Coverage warnings for empty or weak documents
- Searchable review UI in Streamlit
- Export of JSON, TXT, and CSV outputs
- Saved case overview with per-case status and summary metrics

## Current MVP Workflow

### Main Page

- Upload PDFs or scanned image files
- Choose or write an analysis goal
- Run chronology extraction
- Review:
  - overview metrics
  - full chronology
  - document coverage
  - low-confidence hits
  - generated case note

### Case Overview

- Browse saved cases
- Search by applicant, case ID, or goal
- Filter by status
- See timeline size, covered date range, and document-hit counts

### Case Details

- Re-run analysis with a refined goal
- Add more documents
- Review the saved chronology
- Keep internal notes separate from exports

## Architecture

- `app.py`
  - upload and run a new chronology analysis
- `pages/1_📁_Akten.py`
  - saved case overview
- `pages/2_📄_Akte_Details.py`
  - saved case review and re-analysis
- `abh_assist/ingest/extract_text.py`
  - PDF/image text extraction and OCR fallback
- `abh_assist/case/timeline_analysis.py`
  - case-level orchestration
- `abh_assist/extract/timeline.py`
  - chunking, event extraction, date normalization, sorting, coverage summary
- `abh_assist/report/build_report.py`
  - case-note generation
- `abh_assist/report/export.py`
  - TXT and JSON export

## Setup

1. Install Python 3.11+.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Install Tesseract OCR if you want scanned PDFs and image files to work reliably.
4. Download a GGUF model into `models/` and update `config.yaml`.

## Run

```powershell
$env:PATH = "C:\Users\omidr\Feinprojekt\venv311\Lib\site-packages\llama_cpp\lib;C:\Users\omidr\Feinprojekt\venv311\Lib\site-packages\nvidia\cublas\bin;C:\Users\omidr\Feinprojekt\venv311\Lib\site-packages\nvidia\cuda_runtime\bin;C:\Users\omidr\Feinprojekt\venv311\Lib\site-packages\nvidia\cudnn\bin;" + $env:PATH
& "C:\Users\omidr\Feinprojekt\venv311\Scripts\python.exe" -m streamlit run "C:\Users\omidr\Feinprojekt\app.py"
```

## MVP Constraints

- Accuracy depends heavily on OCR quality and the local model.
- Page references are best-effort and depend on extractable page markers.
- The system is designed to over-include potentially relevant entries.
- Outputs should still be reviewed by a human case worker before operational use.

## Evaluation Direction

The right evaluation target for this MVP is not generic chat quality. It is:

- recall of relevant dated events
- quality of chronology ordering
- source traceability
- visibility of extraction gaps
- usefulness for a real case worker reviewing a large file quickly
