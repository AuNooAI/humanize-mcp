"""Readability stats and AI tells detection — no LLM calls, pure regex/heuristics.

Vendored from /home/orochford/humanize/backend/readability.py. Keep in sync with
that source if the heuristic rules change upstream.
"""

import re


# ── AI vocabulary (words that appear far more in LLM output) ──────────────

AI_VOCABULARY = [
    "delve", "intricate", "tapestry", "pivotal", "underscore", "underscores",
    "landscape", "foster", "fosters", "testament", "enhance", "enhances",
    "crucial", "emphasize", "emphasise", "enduring", "garner", "garners",
    "interplay", "meticulous", "vibrant", "multifaceted", "nuanced",
    "comprehensive", "robust", "leverage", "leverages", "nestled", "showcasing",
    "highlighting", "realm", "spearhead", "beacon", "navigate", "navigating",
    "streamline", "streamlines", "empower", "empowers", "unlock", "unlocks",
    "unveil", "unveils", "harness", "harnesses", "embark", "embarking",
    "embrace", "embraces", "bolster", "bolsters", "elevate", "elevates",
    "cultivate", "cultivates", "propel", "propels", "revolutionize",
    "revolutionise", "reimagine", "reimagines", "redefine", "redefines",
    "seamlessly", "seamless", "holistic", "holistically", "dynamic",
    "innovative", "cutting-edge", "state-of-the-art", "bespoke", "curated",
    "synergy", "synergies", "ecosystem", "paradigm", "wheelhouse",
    "touchpoint", "touchpoints", "actionable", "deliverable", "deliverables",
    "stakeholder", "stakeholders", "journey", "mission-critical",
    "best-in-class", "value-add", "next-generation", "transformative",
]

# ── Red-flag phrases ──────────────────────────────────────────────────────

RED_FLAG_PHRASES = [
    "it's worth noting that",
    "it is important to note",
    "it is worth mentioning",
    "it bears mentioning",
    "it should be noted",
    "a testament to",
    "a pivotal moment",
    "at the forefront of",
    "on the cutting edge of",
    "a broader movement toward",
    "plays a crucial role in",
    "plays a key role in",
    "plays a vital role in",
    "plays an important role in",
    "has garnered significant attention",
    "in today's rapidly evolving",
    "in today's fast-paced",
    "as businesses navigate",
    "in an era of unprecedented",
    "with the rise of",
    "in the world of",
    "when it comes to",
    "at the end of the day",
    "the fact of the matter is",
    "needless to say",
    "that being said",
    "with that said",
    "the advantage comes from",
    "the key lies in",
    "the secret lies in",
    "more than just",
    "not just a",
    "lies at the heart of",
    "sits at the intersection of",
    "the power of",
    "unlock the power of",
    "the future of",
    "reshaping the",
    "redefining the",
    "a game-changer",
    "a must-have",
]

# ── Connective tissue ────────────────────────────────────────────────────

CONNECTIVES = [
    "moreover", "furthermore", "additionally", "notably",
    "consequently", "subsequently",
]

# ── Tailing clause patterns ──────────────────────────────────────────────

TAILING_PATTERNS = [
    r",\s+(highlighting|emphasising|emphasizing|underscoring|showcasing|"
    r"reflecting|signaling|signalling|demonstrating|illustrating|cementing|"
    r"reaffirming|marking|proving|representing|solidifying|establishing)"
    r"\s+(the|its|their|a|an|his|her)\s+\w+",
    # Em-dash tail: "— a sign that…", "— proof of…", "— a reminder that…"
    r"\u2014\s*(?:a|an|the)\s+(sign|signal|reminder|testament|proof|mark|symbol|hallmark)\s+(?:of|that)\s+",
    r"--\s*(?:a|an|the)\s+(sign|signal|reminder|testament|proof|mark|symbol|hallmark)\s+(?:of|that)\s+",
]

# ── Negative parallelism ─────────────────────────────────────────────────

NEGATIVE_PARALLELISM = [
    # Single-sentence "It's not X, it's Y"
    r"(?:it'?s|this is|that is|there'?s)\s+not\s+(?:just\s+)?(?:a|an|the)?\s*\w+[\w\s]*,\s*(?:it'?s|but)\s+",
    r"not\s+just\s+(?:a|an|the)?\s*\w+[\w\s]*,\s*but\s+",
    # Cross-sentence "This is not X.\n\nIt's Y."
    r"(?:it'?s|this is|that is)\s+not\s+(?:just\s+)?(?:a|an|the)?\s*[\w\s]+?[.!]\s*\n*\s*(?:it'?s|that'?s)\s+(?:a|an|the)?\s*\w+",
    # "don't have X problem. They have Y problem."
    r"(?:don'?t|do not|doesn'?t|does not)\s+have\s+(?:a|an|the)?\s*[\w\s-]+?\s+problem[.!]\s*\n*\s*(?:they|it|we)\s+have\s+(?:a|an|the)?\s*[\w\s-]+?\s+problem",
    # "The issue isn't X. It's Y."
    r"(?:the\s+(?:issue|problem|point|question|answer|advantage|difference|key)\s+(?:isn'?t|is not))\s+[\w\s]+?[.!]\s*\n*\s*it'?s\s+",
    # "X isn't the enemy. Y is."
    r"\b\w+\s+(?:isn'?t|is not)\s+the\s+\w+[.!]\s*\n*\s*\w+\s+is[.!]",
    # "Less X, more Y." / "More X, less Y."
    r"\b(?:less|more)\s+\w+,\s*(?:more|less)\s+\w+",
    # "X, not Y" trailing contrast
    r",\s*not\s+\w+[.!]",
]


# ── Weasel wording / vague attribution ────────────────────────────────

WEASEL_PHRASES = [
    "many experts agree",
    "scholars have noted",
    "it is widely recognised",
    "it is widely recognized",
    "critics have praised",
    "many believe",
    "some argue",
    "it is generally accepted",
    "research suggests",
    "studies show",
    "experts say",
]

# ── Compulsive summaries ──────────────────────────────────────────────

SUMMARY_STARTERS = [
    r"^(?:overall|in conclusion|in summary|to summarize|to sum up|in short|ultimately)[,.]?\s",
]

# ── False ranges ──────────────────────────────────────────────────────

FALSE_RANGE_PATTERNS = [
    r"from\s+[\w\s]+?\s+to\s+[\w\s]+?(?:operations|movements|expertise|vision|gatherings|insights)",
]

# ── Promotional tone words ────────────────────────────────────────────

PROMOTIONAL_WORDS = [
    "remarkable", "groundbreaking", "revolutionary", "game-changing",
    "unprecedented", "transformative", "cutting-edge", "world-class",
    "breathtaking", "trailblazing", "visionary", "paradigm-shifting",
]

# ── Undue notability emphasis ─────────────────────────────────────────

NOTABILITY_PHRASES = [
    "widely recognised", "widely recognized", "internationally acclaimed",
    "globally renowned", "cementing its place", "cementing their place",
    "has been featured in", "has been covered by",
]

# ── Chatbot artefacts ─────────────────────────────────────────────────

CHATBOT_ARTEFACTS = [
    "great question",
    "as an ai language model",
    "as an ai,",
    "as of my last training",
    "as of my knowledge cutoff",
    "i don't have access to real-time",
    "i hope this helps",
    "let me know if you",
    "feel free to ask",
]

# ── Promotional/LinkedIn AI patterns ──────────────────────────────────

PROMOTIONAL_PATTERNS = [
    # One-word or two-word "sentence" lines used as dramatic list items
    (r'(?:^|\n)\s*\w+(?:\s+\w+){0,4}\s*\n\s*\n\s*\w+(?:\s+\w+){0,4}\s*\n\s*\n\s*\w+(?:\s+\w+){0,4}\s*\n',
     "staccato_list", "Staccato line-per-point list", "Write in prose or use a proper bulleted list."),
]

# ── Excessive bold ────────────────────────────────────────────────────

# Markdown bold used for emphasis throughout (textbook/sales-deck feel)
BOLD_THRESHOLD = 2  # flag if more than this many bold spans

# ── Foreign-script artefacts ─────────────────────────────────────────
#
# Non-Latin script chunks embedded in primarily-English text are almost
# always draft/translation residue from an LLM step. Greek and the Latin
# Extended diacritics blocks are deliberately excluded:
#   - Greek letters (α, β, π) are routinely used as math/science notation
#   - Latin Extended (é, ñ, ü, ø, …) is normal in English loanwords/names
NON_LATIN_SCRIPT_RANGES: list[tuple[int, int, str]] = [
    (0x0400, 0x04FF, "Cyrillic"),
    (0x0500, 0x052F, "Cyrillic Supplement"),
    (0x0531, 0x058F, "Armenian"),
    (0x0590, 0x05FF, "Hebrew"),
    (0x0600, 0x06FF, "Arabic"),
    (0x0700, 0x074F, "Syriac"),
    (0x0750, 0x077F, "Arabic Supplement"),
    (0x0780, 0x07BF, "Thaana"),
    (0x0900, 0x097F, "Devanagari"),
    (0x0980, 0x09FF, "Bengali"),
    (0x0A00, 0x0A7F, "Gurmukhi"),
    (0x0A80, 0x0AFF, "Gujarati"),
    (0x0B00, 0x0B7F, "Oriya"),
    (0x0B80, 0x0BFF, "Tamil"),
    (0x0C00, 0x0C7F, "Telugu"),
    (0x0C80, 0x0CFF, "Kannada"),
    (0x0D00, 0x0D7F, "Malayalam"),
    (0x0D80, 0x0DFF, "Sinhala"),
    (0x0E00, 0x0E7F, "Thai"),
    (0x0E80, 0x0EFF, "Lao"),
    (0x0F00, 0x0FFF, "Tibetan"),
    (0x1000, 0x109F, "Burmese"),
    (0x10A0, 0x10FF, "Georgian"),
    (0x1100, 0x11FF, "Hangul Jamo"),
    (0x1780, 0x17FF, "Khmer"),
    (0x3040, 0x309F, "Hiragana"),
    (0x30A0, 0x30FF, "Katakana"),
    (0x3400, 0x4DBF, "CJK Extension A"),
    (0x4E00, 0x9FFF, "Han (CJK)"),
    (0xAC00, 0xD7AF, "Hangul"),
    (0xF900, 0xFAFF, "CJK Compatibility"),
    (0xFB1D, 0xFB4F, "Hebrew Presentation Forms"),
    (0xFB50, 0xFDFF, "Arabic Presentation Forms-A"),
    (0xFE70, 0xFEFF, "Arabic Presentation Forms-B"),
]

# Single regex character class covering every foreign-script range above.
_FOREIGN_SCRIPT_CHARCLASS = "".join(
    f"\\u{lo:04x}-\\u{hi:04x}" for lo, hi, _ in NON_LATIN_SCRIPT_RANGES
)
FOREIGN_SCRIPT_RUN_RE = re.compile(f"[{_FOREIGN_SCRIPT_CHARCLASS}]+")

# How dominant Latin must be before we treat foreign chars as "stray".
# Anything below this and we assume the document is genuinely multilingual
# (e.g. a Russian essay with one English quote) and skip the check.
LATIN_DOMINANCE_THRESHOLD = 0.7
LATIN_DOMINANCE_MIN_CHARS = 20  # below this, can't make a determination


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r'(?<=[.!?])\s+', text.strip())
    return [s for s in parts if len(s.split()) >= 2]


def compute_readability(text: str) -> dict:
    """Compute readability metrics for a piece of text."""
    if not text.strip():
        return {
            "word_count": 0,
            "sentence_count": 0,
            "avg_sentence_length": 0,
            "flesch_reading_ease": 0,
            "vocabulary_diversity": 0,
            "em_dash_count": 0,
            "bold_count": 0,
        }

    words = text.split()
    word_count = len(words)
    sentences = _split_sentences(text)
    sentence_count = max(len(sentences), 1)
    avg_sentence_length = round(word_count / sentence_count, 1)

    # Syllable count (rough English heuristic)
    def _syllables(word: str) -> int:
        w = re.sub(r'[^a-z]', '', word.lower())
        if len(w) <= 2:
            return 1
        count = len(re.findall(r'[aeiouy]+', w))
        if w.endswith('e') and not w.endswith('le'):
            count -= 1
        return max(count, 1)

    total_syllables = sum(_syllables(w) for w in words)
    avg_syllables = total_syllables / max(word_count, 1)

    # Flesch Reading Ease
    flesch = 206.835 - 1.015 * avg_sentence_length - 84.6 * avg_syllables
    flesch = round(max(0, min(100, flesch)), 1)

    # Vocabulary diversity (type-token ratio)
    unique_words = set(re.sub(r'[^a-z\s]', '', w.lower()) for w in words)
    unique_words.discard('')
    vocab_diversity = round(len(unique_words) / max(word_count, 1), 3)

    # Em dash count
    em_dash_count = text.count('\u2014') + text.count('--')

    # Bold markers (markdown)
    bold_count = len(re.findall(r'\*\*[^*]+\*\*', text))

    return {
        "word_count": word_count,
        "sentence_count": sentence_count,
        "avg_sentence_length": avg_sentence_length,
        "flesch_reading_ease": flesch,
        "vocabulary_diversity": vocab_diversity,
        "em_dash_count": em_dash_count,
        "bold_count": bold_count,
    }


def _normalize_quotes(text: str) -> str:
    """Normalize smart/curly quotes to ASCII equivalents for regex matching."""
    text = text.replace('\u2018', "'").replace('\u2019', "'")  # ' '
    text = text.replace('\u201c', '"').replace('\u201d', '"')  # " "
    return text


def _script_for_codepoint(cp: int) -> str | None:
    """Return the script name for cp if it falls in a tracked non-Latin range."""
    for lo, hi, name in NON_LATIN_SCRIPT_RANGES:
        if lo <= cp <= hi:
            return name
    return None


def _is_primarily_latin(text: str) -> bool:
    """True if the alphabetic content is overwhelmingly Latin script.

    Used to gate the foreign-script-artefact detector so it doesn't fire on
    documents that are *meant* to be in another script.
    """
    latin = 0
    non_latin = 0
    for ch in text:
        if not ch.isalpha():
            continue
        cp = ord(ch)
        # Basic Latin + Latin-1 Supplement + Latin Extended-A/B
        # (covers ASCII letters plus diacritics like \u00e9, \u00f1, \u00fc, \u00f8)
        if (0x0041 <= cp <= 0x007A) or (0x00C0 <= cp <= 0x024F):
            latin += 1
        elif _script_for_codepoint(cp):
            non_latin += 1
    total = latin + non_latin
    if total < LATIN_DOMINANCE_MIN_CHARS:
        return True  # too short to judge \u2014 assume Latin so we still flag obvious tells
    return latin / total >= LATIN_DOMINANCE_THRESHOLD


def detect_ai_tells(text: str) -> list[dict]:
    """Scan text for AI writing tells. Returns list of {tell_type, text, start, end, suggestion}."""
    tells: list[dict] = []
    normalized = _normalize_quotes(text)
    lower = normalized.lower()

    # 1. AI vocabulary
    for word in AI_VOCABULARY:
        for m in re.finditer(r'\b' + re.escape(word) + r'\b', lower):
            original = text[m.start():m.end()]
            tells.append({
                "tell_type": "ai_vocabulary",
                "label": f"AI vocabulary: \"{original}\"",
                "text": original,
                "start": m.start(),
                "end": m.end(),
                "suggestion": _vocabulary_suggestion(word),
            })

    # 2. Red-flag phrases
    for phrase in RED_FLAG_PHRASES:
        for m in re.finditer(re.escape(phrase), lower):
            original = text[m.start():m.end()]
            tells.append({
                "tell_type": "red_flag_phrase",
                "label": f"Red-flag phrase",
                "text": original,
                "start": m.start(),
                "end": m.end(),
                "suggestion": "Remove this phrase and state the information directly.",
            })

    # 3. Connective tissue
    for conn in CONNECTIVES:
        for m in re.finditer(r'\b' + re.escape(conn) + r'\b', lower):
            original = text[m.start():m.end()]
            tells.append({
                "tell_type": "connective_overuse",
                "label": f"Connective tissue: \"{original}\"",
                "text": original,
                "start": m.start(),
                "end": m.end(),
                "suggestion": "Drop the connector. If the flow is clear, the reader doesn't need a signpost.",
            })

    # 4. Tailing clauses
    for pattern in TAILING_PATTERNS:
        for m in re.finditer(pattern, lower):
            original = text[m.start():m.end()]
            tells.append({
                "tell_type": "tailing_clause",
                "label": "Tailing clause",
                "text": original,
                "start": m.start(),
                "end": m.end(),
                "suggestion": "Cut this clause. If the significance isn't obvious, explain why concretely.",
            })

    # 5. Negative parallelism
    for pattern in NEGATIVE_PARALLELISM:
        for m in re.finditer(pattern, lower):
            original = text[m.start():m.end()]
            tells.append({
                "tell_type": "negative_parallelism",
                "label": "Negative parallelism",
                "text": original,
                "start": m.start(),
                "end": m.end(),
                "suggestion": "State the positive claim directly.",
            })

    # Extra: Anaphoric "Not X.\nNot Y." negation list
    for m in re.finditer(r'(?:^|\n)\s*not\s+\w[\w\s]*?[.!]\s*\n\s*not\s+\w', normalized, re.IGNORECASE):
        tells.append({
            "tell_type": "negative_parallelism",
            "label": "Anaphoric negation list",
            "text": text[m.start():m.end()].strip()[:80],
            "start": m.start(),
            "end": m.end(),
            "suggestion": "State what it IS directly, instead of stacking what it isn't.",
        })

    # 6. Em dash overuse
    em_dashes = list(re.finditer(r'\u2014|--', text))
    if len(em_dashes) > 1:
        for m in em_dashes:
            tells.append({
                "tell_type": "em_dash_overuse",
                "label": "Em dash",
                "text": text[m.start():m.end()],
                "start": m.start(),
                "end": m.end(),
                "suggestion": "Replace with comma, colon, period, or restructure.",
            })

    # 7. Copula avoidance (tightened: only the unambiguous "serves as / functions as / stands as")
    copula_patterns = [
        r'\b(serves as|functions as|operates as|stands as|acts as)\b',
    ]
    for pattern in copula_patterns:
        for m in re.finditer(pattern, lower):
            original = text[m.start():m.end()]
            tells.append({
                "tell_type": "copula_avoidance",
                "label": f"Copula avoidance: \"{original}\"",
                "text": original,
                "start": m.start(),
                "end": m.end(),
                "suggestion": "Use 'is' instead.",
            })

    # 8. Vague change intros
    vague_intros = [
        r"in today'?s rapidly evolving[\w\s]*",
        r"as businesses navigate[\w\s]*",
        r"in an era of unprecedented[\w\s]*",
        r"with the rise of[\w\s]*",
        r"in the ever-?changing[\w\s]*",
    ]
    for pattern in vague_intros:
        for m in re.finditer(pattern, lower):
            original = text[m.start():m.end()]
            tells.append({
                "tell_type": "vague_intro",
                "label": "Vague change intro",
                "text": original,
                "start": m.start(),
                "end": m.end(),
                "suggestion": "Delete and start with the actual subject.",
            })

    # 9. Weasel wording
    for phrase in WEASEL_PHRASES:
        for m in re.finditer(re.escape(phrase), lower):
            original = normalized[m.start():m.end()]
            tells.append({
                "tell_type": "weasel_wording",
                "label": "Weasel wording",
                "text": original,
                "start": m.start(),
                "end": m.end(),
                "suggestion": "Name the source. If you can't, question whether the claim is supportable.",
            })

    # 10. Compulsive summaries
    for pattern in SUMMARY_STARTERS:
        for m in re.finditer(pattern, lower, re.MULTILINE):
            original = normalized[m.start():m.end()]
            tells.append({
                "tell_type": "compulsive_summary",
                "label": "Compulsive summary",
                "text": original,
                "start": m.start(),
                "end": m.end(),
                "suggestion": "Cut the summary. If the argument is clear, it doesn't need restating.",
            })

    # 11. False ranges
    for pattern in FALSE_RANGE_PATTERNS:
        for m in re.finditer(pattern, lower):
            original = normalized[m.start():m.end()]
            tells.append({
                "tell_type": "false_range",
                "label": "False range",
                "text": original,
                "start": m.start(),
                "end": m.end(),
                "suggestion": "If there's a real range, describe it concretely. Otherwise just list the things.",
            })

    # 12. Promotional tone
    for word in PROMOTIONAL_WORDS:
        for m in re.finditer(r'\b' + re.escape(word) + r'\b', lower):
            original = normalized[m.start():m.end()]
            tells.append({
                "tell_type": "promotional_tone",
                "label": f"Promotional tone: \"{original}\"",
                "text": original,
                "start": m.start(),
                "end": m.end(),
                "suggestion": "Describe what happened. Let the reader decide whether it's remarkable.",
            })

    # 13. Undue notability emphasis
    for phrase in NOTABILITY_PHRASES:
        for m in re.finditer(re.escape(phrase), lower):
            original = normalized[m.start():m.end()]
            tells.append({
                "tell_type": "undue_notability",
                "label": "Undue notability emphasis",
                "text": original,
                "start": m.start(),
                "end": m.end(),
                "suggestion": "If a source is cited, say what it reported. Don't assume the mention proves significance.",
            })

    # 14. Chatbot artefacts
    for phrase in CHATBOT_ARTEFACTS:
        for m in re.finditer(re.escape(phrase), lower):
            original = normalized[m.start():m.end()]
            tells.append({
                "tell_type": "chatbot_artefact",
                "label": "Chatbot artefact",
                "text": original,
                "start": m.start(),
                "end": m.end(),
                "suggestion": "Remove. This is a chatbot talking to you, not writing for a reader.",
            })

    # 15. Curly/smart quotes (as co-occurring signal)
    curly_count = sum(1 for ch in text if ch in '\u201c\u201d\u2018\u2019')
    if curly_count > 6:
        tells.append({
            "tell_type": "curly_quotes",
            "label": f"Curly quotation marks ({curly_count} found)",
            "text": f"{curly_count} curly quotes",
            "start": 0,
            "end": 0,
            "suggestion": "Curly quotes are a co-occurring AI signal. Convert to straight quotes if appropriate.",
        })

    # 16. Title case headings (markdown headings with Title Case)
    for m in re.finditer(r'^#{1,6}\s+(.+)$', normalized, re.MULTILINE):
        heading = m.group(1).strip()
        words = heading.split()
        if len(words) >= 3:
            capitalized = sum(1 for w in words if w[0:1].isupper() and w.lower() not in ('a', 'an', 'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'is'))
            if capitalized >= len(words) * 0.7:
                tells.append({
                    "tell_type": "title_case_heading",
                    "label": "Title case heading",
                    "text": heading,
                    "start": m.start(),
                    "end": m.end(),
                    "suggestion": "Use sentence case. Title case in headings is an AI formatting tell.",
                })

    # 17. Metronomic cadence (low sentence length variance)
    sentences = _split_sentences(normalized)
    if len(sentences) >= 5:
        lengths = [len(s.split()) for s in sentences]
        avg = sum(lengths) / len(lengths)
        variance = sum((l - avg) ** 2 for l in lengths) / len(lengths)
        std_dev = variance ** 0.5
        if std_dev < 3.0 and avg > 8:
            tells.append({
                "tell_type": "metronomic_cadence",
                "label": f"Metronomic cadence (std dev: {std_dev:.1f})",
                "text": f"Avg {avg:.0f} words/sentence, std dev {std_dev:.1f}",
                "start": 0,
                "end": 0,
                "suggestion": "Vary sentence length. Follow long sentences with short ones.",
            })

    # 18. Markdown in non-markdown contexts
    markdown_markers = len(re.findall(r'(?:^|\n)#{1,6}\s', text)) + len(re.findall(r'\*\*[^*]+\*\*', text))
    if markdown_markers >= 3:
        tells.append({
            "tell_type": "markdown_formatting",
            "label": f"Markdown formatting ({markdown_markers} markers)",
            "text": f"{markdown_markers} markdown markers found",
            "start": 0,
            "end": 0,
            "suggestion": "Convert formatting to match the target medium. Markdown in non-markdown contexts is an AI tell.",
        })

    # 19. Excessive bold (markdown)
    bold_spans = list(re.finditer(r'\*\*[^*]+\*\*', text))
    if len(bold_spans) > BOLD_THRESHOLD:
        for m in bold_spans:
            tells.append({
                "tell_type": "excessive_bold",
                "label": "Excessive boldface",
                "text": text[m.start():m.end()],
                "start": m.start(),
                "end": m.end(),
                "suggestion": "Bold sparingly. If everything is emphasised, nothing is.",
            })

    # 10. Colon-and-bold list format ("**Header**: description")
    for m in re.finditer(r'\*\*[^*]+\*\*\s*:', text):
        original = text[m.start():m.end()]
        tells.append({
            "tell_type": "colon_bold_list",
            "label": "Colon-and-bold list format",
            "text": original,
            "start": m.start(),
            "end": m.end(),
            "suggestion": "Write in prose instead of bolded header + colon format.",
        })

    # 11. Promotional staccato lists (multiple short lines as pseudo-bullets)
    for pattern, tell_type, label, suggestion in PROMOTIONAL_PATTERNS:
        for m in re.finditer(pattern, text):
            tells.append({
                "tell_type": tell_type,
                "label": label,
                "text": text[m.start():m.end()].strip()[:80] + "...",
                "start": m.start(),
                "end": m.end(),
                "suggestion": suggestion,
            })

    # 12. Rule of three — only flag when ≥2 tricolons appear (single triples are normal English)
    tricolons = list(re.finditer(
        r'\b(\w+(?:\s+\w+){0,3}),\s+(\w+(?:\s+\w+){0,3}),\s+and\s+(\w+(?:\s+\w+){0,3})\b', text))
    if len(tricolons) >= 2:
        for m in tricolons:
            tells.append({
                "tell_type": "rule_of_three",
                "label": "Rule of three (repeated)",
                "text": text[m.start():m.end()],
                "start": m.start(),
                "end": m.end(),
                "suggestion": "Multiple tricolons in one piece is a rhythm tell. Break one.",
            })

    # 20. One-sentence-paragraph drumbeat (≥4 blank-line-separated one-sentence paragraphs)
    paragraphs = [p.strip() for p in re.split(r'\n\s*\n', normalized) if p.strip()]
    one_sent_paras = [p for p in paragraphs if len(_split_sentences(p)) <= 1 and len(p.split()) >= 3]
    if len(paragraphs) >= 5 and len(one_sent_paras) / len(paragraphs) >= 0.6:
        tells.append({
            "tell_type": "drumbeat_paragraphs",
            "label": f"One-sentence-paragraph drumbeat ({len(one_sent_paras)}/{len(paragraphs)})",
            "text": f"{len(one_sent_paras)} one-sentence paragraphs",
            "start": 0,
            "end": 0,
            "suggestion": "Combine related sentences into prose paragraphs.",
        })

    # 21. Tricolon anaphora ("We've built… We've seen… We've learned…" / "It's… It's… It's…")
    anaphora_pattern = re.compile(
        r'(?:^|\n)\s*(\b\w+(?:\'\w+)?\s+\w+)[^\n.!?]*[.!?]\s*\n+\s*\1[^\n.!?]*[.!?]\s*\n+\s*\1',
        re.IGNORECASE,
    )
    for m in anaphora_pattern.finditer(normalized):
        tells.append({
            "tell_type": "tricolon_anaphora",
            "label": f"Tricolon anaphora: \"{m.group(1)}…\"",
            "text": text[m.start():m.end()][:80],
            "start": m.start(),
            "end": m.end(),
            "suggestion": "Break the parallel structure. Vary the openings.",
        })

    # 22. Sentence-initial And/But/So overuse
    initial_conj = re.findall(r'(?:^|\n)\s*(?:and|but|so|yet)\b', normalized, re.IGNORECASE)
    if len(initial_conj) >= 3:
        tells.append({
            "tell_type": "initial_conjunction",
            "label": f"Sentence-initial And/But/So ({len(initial_conj)}x)",
            "text": f"{len(initial_conj)} sentence-initial conjunctions",
            "start": 0,
            "end": 0,
            "suggestion": "Used sparingly this is fine; repeated it's a faux-conversational tell.",
        })

    # 23. Trailing rhetorical questions ("So what does that mean?" "What does this tell us?")
    rhet_patterns = [
        r"\bso what does (?:that|this) mean\b",
        r"\bwhat does (?:that|this) tell us\b",
        r"\bwhat'?s the (?:point|takeaway|lesson)\b",
        r"\bso what'?s next\b",
        r"\bwhere do we go from here\b",
        r"\bsound familiar\?",
    ]
    for pattern in rhet_patterns:
        for m in re.finditer(pattern, lower):
            tells.append({
                "tell_type": "rhetorical_question",
                "label": "Rhetorical question",
                "text": text[m.start():m.end()],
                "start": m.start(),
                "end": m.end(),
                "suggestion": "Cut. Just state the answer.",
            })

    # 24. Colon-intro lists ("X: feeds, alerts, dashboards, reports.")
    colon_lists = list(re.finditer(r':\s*\w+(?:,\s*\w+){2,}', text))
    if len(colon_lists) >= 2:
        for m in colon_lists:
            tells.append({
                "tell_type": "colon_list",
                "label": "Colon-introduced list",
                "text": text[m.start():m.end()][:80],
                "start": m.start(),
                "end": m.end(),
                "suggestion": "Repeated colon-lists are a slide-deck rhythm. Use prose.",
            })

    # 25. Bold pseudo-headings ("**Heading**" alone on a line)
    for m in re.finditer(r'(?:^|\n)\*\*[^*\n]+\*\*\s*(?:\n|$)', text):
        tells.append({
            "tell_type": "title_case_heading",
            "label": "Bold pseudo-heading",
            "text": text[m.start():m.end()].strip(),
            "start": m.start(),
            "end": m.end(),
            "suggestion": "Write in prose or use a real heading.",
        })

    # 26. Foreign-script artefacts (non-Latin chars stranded in English text)
    # Catches translation/draft residue like the Arabic "فاصلة" inside an
    # otherwise English paragraph. Skipped when the document is genuinely
    # multilingual to avoid flagging legitimate non-Latin text.
    if _is_primarily_latin(text):
        for m in FOREIGN_SCRIPT_RUN_RE.finditer(text):
            run = m.group(0)
            script = _script_for_codepoint(ord(run[0])) or "non-Latin"
            tells.append({
                "tell_type": "foreign_script_artefact",
                "label": f"Stray {script}: \"{run}\"",
                "text": run,
                "start": m.start(),
                "end": m.end(),
                "suggestion": (
                    f"This {script} fragment is almost certainly a draft or "
                    "translation artefact. Replace with the English equivalent, "
                    "or wrap in quotes if the foreign term is intentional."
                ),
            })

    # Deduplicate overlapping tells (keep the more specific one)
    tells.sort(key=lambda t: (t["start"], -t["end"]))
    deduped: list[dict] = []
    for tell in tells:
        if deduped and tell["start"] < deduped[-1]["end"] and tell["tell_type"] == deduped[-1]["tell_type"]:
            continue
        deduped.append(tell)

    return deduped


def _vocabulary_suggestion(word: str) -> str:
    replacements = {
        "delve": "explore or examine",
        "intricate": "complex",
        "tapestry": "mix or combination",
        "pivotal": "important or key",
        "underscore": "show or emphasize",
        "landscape": "field or area",
        "foster": "encourage or support",
        "testament": "proof or sign",
        "enhance": "improve",
        "crucial": "important",
        "emphasize": "stress or point out",
        "enduring": "lasting",
        "garner": "get or attract",
        "interplay": "interaction",
        "meticulous": "careful or thorough",
        "vibrant": "lively or active",
        "multifaceted": "varied or complex",
        "nuanced": "subtle",
        "comprehensive": "thorough or full",
        "robust": "strong or solid",
        "leverage": "use",
        "nestled": "located or set",
        "showcasing": "showing",
        "highlighting": "showing or pointing out",
        "realm": "area or field",
        "spearhead": "lead",
        "beacon": "example or model",
    }
    replacement = replacements.get(word, "a simpler word")
    return f"Replace with {replacement}."
