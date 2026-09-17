"""Entry point for the BibleAI sermon processing system."""

import json
import sys
from pathlib import Path

from modules.ai_provider import AIProviderError, create_ai_provider
from modules.audio_docx_formatter import generate_audio_docx
from modules.audio_processor import analyze_audio
from modules.audio_transcriber import AudioTranscriptionError, transcribe_audio
from modules.batch_processor import process_folder
from modules.bible_checker import check_bible_terms, load_bible_database
from modules.config_loader import load_config
from modules.correction_engine import correct_long_text, correct_text, correct_with_bible_check
from modules.docx_generator import generate_docx
from modules.image_ocr import extract_text_from_image
from modules.image_docx_analyzer import analyze_image_template
from modules.image_sorter import sort_images
from modules.input_classifier import classify_input
from modules.pipeline_controller import process_input
from modules.template_manager import get_template_info, get_template_path, load_template, template_exists
from modules.text_cleaning_pipeline import clean_ocr_text
from modules.style_mapper import build_style_mapping, save_style_mapping


BASE_DIR = Path(__file__).resolve().parent
INPUT_DIR = BASE_DIR / "input"
INPUT_AUDIO_DIR = INPUT_DIR / "audio"
INPUT_IMAGES_DIR = INPUT_DIR / "images"
DEMO_CORRECTION_TEXT = "神带领以色列名出埃及"
DEMO_LONG_TEXT = (
    "第一段，神带领以色列名出埃及。我们继续思想神的话语。\n\n"
    "第二段，摩西带领百姓经过旷野。神仍然供应他们。\n\n"
    "第三段，我们学习信靠神。即使环境艰难，也要仰望主。"
)
DEMO_BIBLE_CHECK_TEXT = "创世纪中摩西带领以色列民出埃及。"
DEMO_WATERMARK_TEXT = "神与以色列民立约\n\n来自小米笔记"
DEMO_DOCX_TEXT = "这是 Phase 7A 的 DOCX 生成基础测试。\n\n模板结构应由原始 DOCX 文件保留。"
DEMO_AUDIO_DOCX_TEXT = (
    "弟兄姊妹平安。今天我们一同思想神的话语。\n"
    "神带领以色列民出埃及。祂在旷野中供应他们。\n"
    "我们也要学习信靠主。即使环境艰难，神仍然掌权。"
)


def scan_input_paths():
    """Collect supported scan locations for Phase 4B testing."""
    input_paths = []

    if INPUT_AUDIO_DIR.exists():
        input_paths.extend(item for item in INPUT_AUDIO_DIR.iterdir() if item.is_file())

    if INPUT_IMAGES_DIR.exists():
        input_paths.extend(INPUT_IMAGES_DIR.iterdir())

    return input_paths


def load_ai_provider_for_demo(config):
    """Load configured AI provider for manual tests without hiding errors."""
    print(f"\nConfiguration:\nAI Provider: {config['ai_provider']}")

    try:
        provider = create_ai_provider(config)
    except AIProviderError as error:
        print(f"Provider not loaded: {error}")
        return None

    print(f"Provider loaded successfully: {provider.provider_name}")
    return provider


def run_manual_correction_demo(provider):
    """Run a small manual correction demo when explicitly requested."""
    print("\nManual correction demo:")
    print(f"Input: {DEMO_CORRECTION_TEXT}")

    if provider is None:
        print("Status: Add DEEPSEEK_API_KEY to .env to run the DeepSeek correction demo.")
        return

    try:
        result = correct_text(DEMO_CORRECTION_TEXT, provider)
    except AIProviderError as error:
        print(f"Correction skipped: {error}")
        return

    if result["success"]:
        print("Correction completed.")
        print(f"Output: {result['corrected_text']}")
    else:
        print(f"Correction skipped: {result['error']}")


def run_manual_long_correction_demo(provider):
    """Run a manual long-text correction demo when explicitly requested."""
    print("\nManual long text correction demo:")

    if provider is None:
        print("Status: Add DEEPSEEK_API_KEY to .env to run the DeepSeek long text demo.")
        return

    try:
        result = correct_long_text(DEMO_LONG_TEXT, provider, max_length=35)
    except AIProviderError as error:
        print(f"Correction skipped: {error}")
        return

    print(f"Number of chunks: {result['chunks_processed']}")
    print("Correction completed.")

    if result["warnings"]:
        print("Warnings:")
        for warning in result["warnings"]:
            print(f"- {warning}")


def run_manual_bible_check_demo():
    """Run a manual Bible terminology verification demo."""
    print("\nManual Bible terminology check:")
    print(f"Input: {DEMO_BIBLE_CHECK_TEXT}")

    database = load_bible_database()
    result = check_bible_terms(DEMO_BIBLE_CHECK_TEXT, database)

    if not result["issues"]:
        print("No possible Bible terminology issues detected.")
        return

    print("Detected possible Bible terminology issues:")
    for issue in result["issues"]:
        print(f"- {issue['type']}: {issue['found']} -> {issue['suggestion']}")
    print("Text was not modified.")


def run_manual_bible_correction_demo(provider):
    """Run a manual Bible-check-aware correction workflow demo."""
    print("\nManual Bible-aware correction workflow:")
    print(f"Input: {DEMO_BIBLE_CHECK_TEXT}")

    database = load_bible_database()
    bible_result = check_bible_terms(DEMO_BIBLE_CHECK_TEXT, database)

    if bible_result["issues"]:
        print("Detected Bible issues:")
        for issue in bible_result["issues"]:
            print(f"- {issue['found']} -> {issue['suggestion']}")
    else:
        print("No possible Bible terminology issues detected.")

    if provider is None:
        print("Status: Add DEEPSEEK_API_KEY to .env to run the Bible-aware correction workflow.")
        print("Text was not modified.")
        return

    result = correct_with_bible_check(DEMO_BIBLE_CHECK_TEXT, provider)
    print("Correction workflow completed.")
    print(f"Approved: {result['approved']}")
    print("Bible checker did not directly modify text.")


def run_manual_image_ocr_demo(provider):
    """Run a manual OCR extraction demo for the first available image."""
    print("\nManual image OCR demo:")

    image_paths = [
        item
        for item in INPUT_IMAGES_DIR.iterdir()
        if item.is_file() and item.suffix.lower() in {".jpg", ".jpeg", ".png"}
    ] if INPUT_IMAGES_DIR.exists() else []

    if not image_paths:
        print("No image files found in input/images.")
        return

    if provider is None or not hasattr(provider, "generate_from_image"):
        print("Status: A vision-capable provider is required for OCR extraction.")
        return

    result = extract_text_from_image(image_paths[0], provider)
    if result["success"]:
        print("OCR extraction completed.")
        print(f"Characters: {len(result['text'])}")
    else:
        print(f"OCR extraction failed: {result['error']}")


def run_manual_image_sort_demo(provider):
    """Run a manual image ordering demo for files in input/images."""
    print("\nManual image sort demo:")

    image_paths = [
        item
        for item in INPUT_IMAGES_DIR.iterdir()
        if item.is_file() and item.suffix.lower() in {".jpg", ".jpeg", ".png"}
    ] if INPUT_IMAGES_DIR.exists() else []

    if not image_paths:
        print("No image files found in input/images.")
        return

    print("Original order:")
    for image_path in image_paths:
        print(image_path.name)

    result = sort_images(image_paths, provider)

    print("\nDetected order:")
    for image_path in result["ordered_images"]:
        print(Path(image_path).name)

    print(f"\nConfidence: {result['confidence']}")
    if "warning" in result:
        print(f"Warning: {result['warning']}")


def run_manual_watermark_clean_demo():
    """Run a manual OCR watermark cleaning demo."""
    print("\nManual watermark cleaning demo:")
    print("Input:")
    print(DEMO_WATERMARK_TEXT)

    result = clean_ocr_text(DEMO_WATERMARK_TEXT)

    print("\nRemoved:")
    if result["removed_watermarks"]:
        for watermark in result["removed_watermarks"]:
            print(watermark["text"])
    else:
        print("None")

    print("\nClean text:")
    print(result["cleaned_text"])


def run_manual_template_analysis_demo():
    """Print DOCX template analysis summary."""
    print("\nManual template analysis demo:")

    for template_type in ("audio", "image"):
        info = get_template_info(template_type)
        print(f"\n{template_type.capitalize()} template:")

        if not info["success"]:
            print(info["error"])
            continue

        print(f"Paragraphs: {info['paragraph_count']}")
        print(f"Styles: {info['style_count']}")
        print(f"Tables: {info['tables']}")
        print(f"Fonts detected: {len(info['fonts'])}")
        print(f"Colors detected: {len(info['colors'])}")


def run_manual_docx_generation_demo():
    """Generate a basic DOCX using the audio template."""
    print("\nManual DOCX generation demo:")
    output_path = BASE_DIR / "output" / "docx" / "phase7a_demo.docx"
    result = generate_docx(DEMO_DOCX_TEXT, get_template_path("audio"), output_path)
    print("DOCX generation completed.")
    print(f"Output: {result['output_path']}")
    print(f"Paragraphs inserted: {result['paragraphs_inserted']}")


def run_manual_image_template_analysis_demo():
    """Print image DOCX template analysis summary."""
    print("\nManual image template analysis demo:")
    analysis = analyze_image_template(get_template_path("image"))
    print("Image template:")
    print(f"Paragraphs: {analysis['paragraph_count']}")
    print(f"Colors: {len(analysis['colors'])}")
    print(f"Styles: {len(analysis['styles'])}")
    print(f"Runs: {len(analysis['runs'])}")
    print(f"Fonts: {len(analysis['fonts'])}")


def run_manual_style_mapping_demo():
    """Build and save image template style mapping."""
    print("\nManual style mapping demo:")
    mapping = build_style_mapping(get_template_path("image"))
    save_style_mapping("image_template", mapping)
    print("Generated style mapping successfully.")
    print(f"Styles: {len(mapping['styles'])}")
    print(f"Colors: {len(mapping['colors'])}")


def run_manual_audio_docx_demo():
    """Generate a paper-saving audio sermon DOCX demo."""
    print("\nManual audio DOCX generation demo:")
    output_path = BASE_DIR / "output" / "docx" / "audio_demo.docx"
    result = generate_audio_docx(DEMO_AUDIO_DOCX_TEXT, get_template_path("audio"), output_path)
    print("Audio DOCX generated successfully.")
    print(f"Output: {result['output_path']}")
    print(f"Paragraphs inserted: {result['paragraphs_inserted']}")


def print_batch_results(results):
    """Print a compact summary for folder batch processing."""
    if not results:
        print("No supported files found in this folder.")
        return

    succeeded = 0
    failed = 0

    for index, result in enumerate(results, start=1):
        status = result.get("status")
        if status == "success":
            succeeded += 1
            print(f"\nItem {index}: success")
            print(f"Input: {result.get('input')}")
            print(f"Output: {result.get('output')}")
        else:
            failed += 1
            print(f"\nItem {index}: failed")
            print(f"Input: {result.get('input')}")
            print(f"Error: {result.get('error')}")

    print(f"\nBatch completed. Success: {succeeded}, Failed: {failed}")


def print_classification_result(input_path, config):
    """Print readable classification and transcription status."""
    classification = classify_input(input_path)
    print(f"\nPath: {classification['path']}")
    print(f"Detected: {classification['type']}")

    if classification["type"] == "audio":
        audio_info = analyze_audio(classification["path"])
        print(f"File type: {audio_info['file_type']}")
        print(f"Size: {audio_info['size_mb']} MB")

        if audio_info["duration_minutes"] is not None:
            print(f"Duration: {audio_info['duration_minutes']} minutes")

        if not audio_info["within_limit"]:
            print(f"Status: {audio_info['warning']}")
            return

        if (
            config.get("audio_transcription_provider", "openai") == "openai"
            and not config["openai_api_key_configured"]
        ):
            print("Status: Ready for transcription. Add OPENAI_API_KEY to .env to run Whisper.")
            return

        try:
            transcription = transcribe_audio(classification["path"])
        except AudioTranscriptionError as error:
            print(f"Transcription skipped: {error}")
            return

        print("Transcription completed.")
        print(f"Characters: {len(transcription['text'])}")
    elif classification["type"] == "image":
        print("Status: Ready for future OCR")
    elif classification["type"] == "image_folder":
        print(f"Images found: {classification['image_count']}")
        print("Status: Ready for future OCR")
    else:
        print(f"Status: {classification.get('error', 'Unsupported input')}")


def main():
    """Run demos or the final automatic pipeline."""
    # Future workflow:
    # 1. Detect input type: audio file or printed text image.
    # 2. Convert audio/image content to raw text.
    # 3. Select AI provider through the abstraction layer.
    # 4. Correct transcription text with the long-text correction pipeline.
    # 5. Check Bible terminology and references.
    # 6. Apply the correct DOCX template.
    # 7. Generate a professionally formatted DOCX file.

    if "--watch-worker" in sys.argv:
        try:
            input_path = sys.argv[sys.argv.index("--watch-worker") + 1]
        except IndexError:
            result = {
                "success": False,
                "step": "input_detection",
                "error": "Missing input path after --watch-worker.",
            }
        else:
            result = process_input(input_path)
        print("__BIBLEAI_WATCH_RESULT__=" + json.dumps(result, ensure_ascii=False))
        return

    if "--process" in sys.argv:
        try:
            input_path = sys.argv[sys.argv.index("--process") + 1]
        except IndexError:
            print("Missing input path after --process.")
            return

        print("Processing started.")
        result = process_input(input_path)
        print(f"Input type: {result.get('input_type')}")

        if result.get("success"):
            for index, step in enumerate(result.get("steps", []), start=1):
                print(f"Step {index}: {step}")
            print("Output:")
            print(result.get("output"))
        else:
            print(f"Failed at step: {result.get('step')}")
            print(f"Error: {result.get('error')}")
        return

    if "--batch" in sys.argv:
        try:
            folder_path = sys.argv[sys.argv.index("--batch") + 1]
        except IndexError:
            print("Missing folder path after --batch.")
            return

        print("Batch processing started.")
        print(f"Folder: {folder_path}")
        results = process_folder(folder_path)
        print_batch_results(results)
        return

    config = load_config()
    print("Configuration loaded.")

    for template_type in ("audio", "image"):
        exists = template_exists(template_type)
        print(f"{template_type.capitalize()} template exists: {exists}")

        template = load_template(template_type)
        if isinstance(template, str):
            print(template)
        else:
            print(f"{template_type.capitalize()} template loaded successfully.")

    provider = load_ai_provider_for_demo(config)

    if "--demo-correction" in sys.argv:
        run_manual_correction_demo(provider)
    elif "--demo-long-correction" in sys.argv:
        run_manual_long_correction_demo(provider)
    elif "--demo-bible-check" in sys.argv:
        run_manual_bible_check_demo()
    elif "--demo-bible-correction" in sys.argv:
        run_manual_bible_correction_demo(provider)
    elif "--demo-image-ocr" in sys.argv:
        run_manual_image_ocr_demo(provider)
    elif "--demo-image-sort" in sys.argv:
        run_manual_image_sort_demo(provider)
    elif "--demo-watermark-clean" in sys.argv:
        run_manual_watermark_clean_demo()
    elif "--demo-template-analysis" in sys.argv:
        run_manual_template_analysis_demo()
    elif "--demo-docx-generation" in sys.argv:
        run_manual_docx_generation_demo()
    elif "--demo-image-template-analysis" in sys.argv:
        run_manual_image_template_analysis_demo()
    elif "--demo-style-mapping" in sys.argv:
        run_manual_style_mapping_demo()
    elif "--demo-audio-docx" in sys.argv:
        run_manual_audio_docx_demo()
    else:
        print(
            "Manual correction demos skipped. Run python main.py --process <input_path>, --demo-correction "
            "or --demo-long-correction, --demo-bible-check, --demo-bible-correction, "
            "--demo-image-ocr, --demo-image-sort, --demo-watermark-clean, "
            "--demo-template-analysis, --demo-docx-generation, --demo-image-template-analysis, "
            "--demo-style-mapping, --demo-audio-docx, or --batch <folder_path>."
        )

    print("\nInput scan results:")
    input_paths = scan_input_paths()

    if not input_paths:
        print("No input files found. Add MP3/M4A files to input/audio or JPG/PNG files to input/images.")

    for input_path in input_paths:
        print_classification_result(input_path, config)

    print("\nPhase 7D final automatic pipeline setup completed successfully.")


if __name__ == "__main__":
    main()
