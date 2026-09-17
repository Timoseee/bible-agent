# BibleAI

BibleAI is an AI-assisted Bible sermon pipeline for local audio transcription,
image OCR, correction, review, and DOCX export.

Completed through Phase 7D:

- Audio workflow: MP3/M4A -> local faster-whisper or OpenAI Whisper -> correction/review -> audio DOCX.
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
  -> Text cleaning
  -> Bible Checker
  -> DeepSeek/OpenAI Correction
  -> Review Agent
  -> Audio DOCX Generator
  -> Final DOCX
```

Audio output uses `templates/audio_template.docx` through `audio_docx_formatter.py` and `paragraph_optimizer.py`.

Audio transcripts and Word output are normalized to Simplified Chinese with OpenCC.
If correction, review, or editorial polish fails, processing reports the failed
stage and does not export an uncorrected transcript as a finished document.
Leave `API_PROXY` empty for direct API access; set it only when that proxy is running.

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
  -> Two-round Full-text Audit
  -> Candidate Review and Deterministic Edits
  -> Image DOCX generation
```

Image output uses `templates/image_template.docx`, `image_docx_renderer.py`, `style_mapper.py`, and `image_docx_analyzer.py`. Style data is extracted from the real template rather than hardcoded.

### One-click image-to-Word

1. Run `setup_image_to_doc.bat` once to install RapidOCR, ONNX Runtime, and Recycle Bin support.
2. Put one batch of JPG/JPEG/PNG files directly in `input/images`.
3. Double-click `start_image_to_doc.bat`.

Images are naturally ordered by filename, read locally, corrected and reviewed with
DeepSeek V4 Flash, and merged into `output/docx/图片文本_YYYYMMDD_HHMMSS.docx`.
Only after the DOCX is successfully generated and reopened are source images moved
to the Windows Recycle Bin. Any OCR, correction, review, or document failure leaves
the full source batch in place.

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
LOCAL_OCR_PROVIDER=rapidocr
DEEPSEEK_MODEL=deepseek-v4-flash
DEEPSEEK_API_TIMEOUT_SECONDS=600
DEEPSEEK_API_MAX_RETRIES=3
OCR_MIN_CHARACTERS_PER_PAGE=5
OCR_MIN_AVERAGE_CONFIDENCE=0.55
FULL_AUDIT_MIN_CONFIDENCE=0.92
FULL_AUDIT_WINDOW_CHARACTERS=6000
FULL_AUDIT_OVERLAP_CHARACTERS=600
AUDIO_TRANSCRIPTION_PROVIDER=local
LOCAL_WHISPER_MODEL=small
LOCAL_WHISPER_DEVICE=cpu
LOCAL_WHISPER_COMPUTE_TYPE=int8
```

Run automatic processing:

```bash
python main.py --process input/audio/sermon.mp3
python main.py --process input/images/chapter24
```

With `AUDIO_TRANSCRIPTION_PROVIDER=local`, audio stays on this computer during
transcription. The local model is downloaded on first use. Text correction and
review continue to use the independently selected `AI_PROVIDER`.

## Automatic audio monitoring

Double-click `start_auto_watch.bat` to run a minimized background watcher. New
MP3/M4A files placed in `input/audio` are processed one at a time after copying
finishes, the computer has been idle for two minutes, and AC power is connected.
Double-click `stop_auto_watch.bat` to stop it cleanly.

The watcher runs below normal process priority, remembers completed files in
`output/audio_watcher_state.json`, retries failures after ten minutes, and logs
activity to `logs/audio_watcher.log`. Optional `.env` settings:

```text
WATCH_SCAN_INTERVAL_SECONDS=3
WATCH_FILE_STABLE_SECONDS=15
WATCH_IDLE_SECONDS=120
WATCH_RETRY_SECONDS=600
WATCH_REQUIRE_AC_POWER=true
WATCH_NOTIFY_ON_SUCCESS=true
```

Run this once before first use if files already in the input folder have already
been processed and should not run again:

```bash
python watch_audio.py --mark-existing
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
