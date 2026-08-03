# BibleAI

BibleAI is an AI-assisted Bible sermon processing system. very cool.

Completed through Phase 7D:

- Audio workflow: MP3/M4A -> Whisper transcription -> correction/review -> audio DOCX.
- Image workflow: image folder -> ordering -> OCR -> watermark cleaning -> correction/review -> image DOCX.
- Safety layers: Bible terminology suggestions, preservation validation, and review approval.

## Final Architecture

```text
INPUT
  -> Pipeline Controller
  -> Audio Workflow or Image Workflow
  -> Correction Pipeline
  -> Review System
  -> DOCX Renderer
  -> Final DOCX
```

## Audio Workflow

```text
MP3/M4A
  -> Whisper transcription
  -> Bible terminology checking
  -> Correction Agent
  -> Preservation Validator
  -> Review Agent
  -> Audio DOCX generation
```

Audio output uses `templates/audio_template.docx` through `audio_docx_formatter.py` and `paragraph_optimizer.py`.

## Image Workflow

```text
Image file/folder
  -> Image ordering
  -> Vision OCR
  -> Watermark cleaning
  -> Bible terminology checking
  -> Correction Agent
  -> Preservation Validator
  -> Review Agent
  -> Image DOCX generation
```

Image output uses `templates/image_template.docx`, `image_docx_renderer.py`, `style_mapper.py`, and `image_docx_analyzer.py`. Style data is extracted from the real template rather than hardcoded.

## Key Commands

Install dependencies:

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Configure `.env`:

```text
OPENAI_API_KEY=
DEEPSEEK_API_KEY=
AI_PROVIDER=deepseek
VISION_PROVIDER=deepseek
```

Run automatic processing:

```bash
python main.py --process input/audio/sermon.mp3
python main.py --process input/images/chapter24
```

## Desktop application

The local PySide6 desktop application lets users select audio files or image folders,
run the existing automatic pipeline in a background thread, follow progress and logs,
and open generated DOCX files. The GUI does not duplicate backend processing logic.

Install the GUI dependency and start it with:

```bash
pip install -r requirements_gui.txt
python frontend/app.py
```

For a Windows executable, install PyInstaller and package the entry point:

```bash
pyinstaller --name BibleAI --windowed frontend/app.py
```

GUI tests use mocked processing and do not require real API calls:

```bash
python -m unittest tests.test_gui
```

Run all tests:

```bash
python -m unittest discover
```

## Modules Added In Phase 7D

- `pipeline_controller.py`: routes input and runs audio/image workflows.
- `batch_processor.py`: prepares sequential folder processing for supported audio files and image folders.
- `document_structure_analyzer.py`: classifies title, headings, body, and scripture references without rewriting text.
- `image_docx_renderer.py`: now supports final image DOCX rendering using template-derived style mappings.

## Preservation Rules

- Existing Whisper, OCR, correction, review, Bible checker, and templates are reused.
- Templates are preserved and are never rewritten in place.
- Bible checker suggestions do not directly modify text.
- Validator and Review Agent preserve original text if correction is unsafe.

## Current Notes

This phase completes the automatic workflow wiring. Production use still depends on valid API keys and providers that support the required audio, text, and vision calls.
