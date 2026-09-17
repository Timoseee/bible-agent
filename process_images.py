"""One-click entry point for converting input/images into one reviewed DOCX."""

import sys
from pathlib import Path

from modules.pipeline_controller import process_image_input


BASE_DIR = Path(__file__).resolve().parent
INPUT_DIR = BASE_DIR / "input" / "images"


def _progress(percent, message):
    print(f"[{percent:>3}%] {message}", flush=True)


def main():
    print("BibleAI 图片转 Word", flush=True)
    print(f"输入目录：{INPUT_DIR}", flush=True)
    result = process_image_input(INPUT_DIR, progress_callback=_progress)

    print("\n处理结果：")
    if result.get("success"):
        print(f"成功生成：{result.get('output')}")
        print(f"图片总数：{result.get('images_total', 0)}")
        preserved_chunks = result.get("preserved_chunks", [])
        if preserved_chunks:
            print(
                "为避免改变原意，以下分段保留了 OCR 原文："
                + "、".join(str(index) for index in preserved_chunks)
            )
        print(
            "全文查漏：发现候选 {0} 项，采用 {1} 项，拒绝 {2} 项（{3} 轮）".format(
                result.get("full_audit_candidates", 0),
                result.get("full_audit_applied", 0),
                result.get("full_audit_rejected", 0),
                result.get("full_audit_rounds", 0),
            )
        )
        for warning in result.get("audit_warnings", []):
            if "自动拆分重试" in str(warning):
                print(f"全文查漏提示：{warning}")
        cleanup_errors = result.get("cleanup_errors", [])
        if cleanup_errors:
            print("以下原图未能移入回收站：")
            for error in cleanup_errors:
                print(f"  - {error}")
        return 0

    print(f"失败阶段：{result.get('step', 'unknown')}")
    print(f"失败原因：{result.get('error', 'unknown error')}")
    failed_images = result.get("failed_images", [])
    if failed_images:
        print("需要检查的图片：")
        for item in failed_images:
            print(f"  - {item.get('filename')}: {item.get('reason')}")
    print("原图已保留，修正问题后可重新运行。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
