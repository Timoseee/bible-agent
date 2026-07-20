"""Paragraph optimization for audio sermon DOCX output."""

import re


SENTENCE_PATTERN = re.compile(r"[^。！？!?]+[。！？!?]?")
MAX_SENTENCES_PER_PARAGRAPH = 4
SOFT_MIN_CHARS = 50
SOFT_TARGET_CHARS = 180
SOFT_MAX_CHARS = 280

CHAPTER_TITLE_PATTERN = re.compile(
    r"("
    r"创世[纪记]|出埃及记|利未记|民数记|申命记|约书亚记|士师记|路得记|"
    r"撒母耳记[上下]|列王纪[上下]|历代志[上下]|以斯拉记|尼希米记|以斯帖记|"
    r"约伯记|诗篇|箴言|传道书|雅歌|以赛亚书|耶利米书|耶利米哀歌|以西结书|但以理书|"
    r"何西阿书|约珥书|阿摩司书|俄巴底亚书|约拿书|弥迦书|那鸿书|哈巴谷书|西番雅书|"
    r"哈该书|撒迦利亚书|玛拉基书|"
    r"马太福音|马可福音|路加福音|约翰福音|使徒行传|"
    r"罗马书|哥林多前书|哥林多后书|加拉太书|以弗所书|腓立比书|歌罗西书|"
    r"帖撒罗尼迦前书|帖撒罗尼迦后书|提摩太前书|提摩太后书|提多书|腓利门书|"
    r"希伯来书|雅各书|彼得前书|彼得后书|约翰[一二三]书|犹大书|启示录"
    r")"
    r"(?:的)?第?([一二三四五六七八九十百千零〇O0-9]+)章"
)

SOFT_BREAK_PREFIXES = (
    "那么",
    "然后",
    "接着",
    "最后",
    "所以",
    "因此",
    "各位",
    "弟兄",
    "姐妹",
    "接下来",
    "那接下来",
    "我们再看",
    "我们先看",
    "再看",
    "先看",
    "那关于",
    "第一段",
    "第二段",
    "第三段",
    "这是第一",
    "这是第二",
    "这是第三",
    "这是一节",
    "这是啊",
)


def _split_sentences(text):
    return [match.group(0).strip() for match in SENTENCE_PATTERN.finditer(text) if match.group(0).strip()]


def _is_boundary(paragraph):
    stripped = paragraph.strip()
    if not stripped:
        return False

    return (
        stripped.endswith(":")
        or stripped.endswith("：")
        or stripped.startswith(("经文", "读经", "祷告", "一、", "二、", "三、", "四、", "五、"))
        or len(stripped) <= 12 and not re.search(r"[。！？!?]", stripped)
    )


def extract_audio_title(text):
    """Extract a short chapter title from sermon text when possible."""
    if not text or not text.strip():
        return None

    lines = [line.strip() for line in re.split(r"\n+", text) if line.strip()]
    if lines and _is_boundary(lines[0]) and CHAPTER_TITLE_PATTERN.fullmatch(lines[0].replace(" ", "")):
        return re.sub(r"\s+", "", lines[0])

    compact = re.sub(r"\s+", "", text)
    match = CHAPTER_TITLE_PATTERN.search(compact)
    if not match:
        return None

    book = match.group(1)
    if book == "创世纪":
        book = "创世记"
    return f"{book}第{match.group(2)}章"


def _needs_soft_segmentation(text):
    chars = len(text.strip())
    if chars < 80:
        return False
    punct = len(re.findall(r"[。！？!?]", text))
    spaces = len(re.findall(r"\s+", text))
    if punct >= 3:
        return False
    if spaces >= 5 and punct <= 1:
        return True
    return chars > 300 and punct < max(3, chars // 250)


def _is_soft_break_token(token):
    stripped = token.strip()
    if not stripped:
        return False
    return any(stripped.startswith(prefix) for prefix in SOFT_BREAK_PREFIXES)


def _soft_segment_spaced_text(text):
    """Split space-heavy ASR text into template-like paragraph lengths."""
    tokens = [token for token in re.split(r"(\s+)", text) if token != ""]
    if len(tokens) == 1:
        return [text.strip()] if text.strip() else []

    paragraphs = []
    current = []
    current_chars = 0

    def flush():
        nonlocal current, current_chars
        if not current:
            return
        paragraph = "".join(current).strip()
        if paragraph:
            paragraphs.append(paragraph)
        current = []
        current_chars = 0

    for token in tokens:
        if token.isspace():
            if current:
                current.append(token)
            continue

        token_len = len(token)
        tentative = current_chars + token_len
        should_break = current and (
            (current_chars >= SOFT_MIN_CHARS and _is_soft_break_token(token))
            or (current_chars >= SOFT_TARGET_CHARS and _is_soft_break_token(token))
            or tentative > SOFT_MAX_CHARS
        )
        if should_break:
            flush()
        current.append(token)
        current_chars += token_len

    flush()
    return paragraphs


def optimize_audio_paragraphs(text):
    """Return readable, paper-saving paragraphs without changing wording."""
    if not text or not text.strip():
        return []

    source_paragraphs = [part.strip() for part in re.split(r"\n\s*\n|\n", text) if part.strip()]

    if len(source_paragraphs) == 1 and _needs_soft_segmentation(source_paragraphs[0]):
        return _soft_segment_spaced_text(source_paragraphs[0])

    optimized = []
    sentence_buffer = []

    def flush_buffer():
        while sentence_buffer:
            group = sentence_buffer[:MAX_SENTENCES_PER_PARAGRAPH]
            del sentence_buffer[:MAX_SENTENCES_PER_PARAGRAPH]
            optimized.append("".join(group))

    for paragraph in source_paragraphs:
        if _is_boundary(paragraph):
            flush_buffer()
            optimized.append(paragraph)
            continue

        if _needs_soft_segmentation(paragraph):
            flush_buffer()
            optimized.extend(_soft_segment_spaced_text(paragraph))
            continue

        sentences = _split_sentences(paragraph)
        if not sentences:
            sentence_buffer.append(paragraph)
        else:
            sentence_buffer.extend(sentences)

        if len(sentence_buffer) >= MAX_SENTENCES_PER_PARAGRAPH:
            flush_buffer()

    flush_buffer()
    return optimized


def structure_audio_paragraphs(text):
    """Return title + body paragraphs ready for template-styled DOCX output."""
    title = extract_audio_title(text)
    body_paragraphs = optimize_audio_paragraphs(text)

    structured = []
    if title:
        structured.append({"role": "title", "text": title})

    for paragraph in body_paragraphs:
        cleaned = paragraph.strip()
        if not cleaned:
            continue
        if title and re.sub(r"\s+", "", cleaned) == re.sub(r"\s+", "", title):
            continue
        role = "title" if _is_boundary(cleaned) and not title else "body"
        if role == "title" and title:
            role = "body"
        structured.append({"role": role, "text": cleaned})

    return structured
