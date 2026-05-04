"""Spot-checks for the heuristic detector. Not exhaustive — one example per
category to confirm the rules fire and to flag accidental regressions if the
vendored detection.py drifts from upstream."""

from humanize_mcp.detection import compute_readability, detect_ai_tells


def _types(text: str) -> set[str]:
    return {t["tell_type"] for t in detect_ai_tells(text)}


def test_ai_vocabulary_fires():
    assert "ai_vocabulary" in _types("We delve into this intricate tapestry.")


def test_red_flag_phrase_fires():
    assert "red_flag_phrase" in _types("It's worth noting that this matters.")


def test_connective_overuse_fires():
    assert "connective_overuse" in _types("Moreover, we acted. Furthermore, we won.")


def test_negative_parallelism_fires():
    assert "negative_parallelism" in _types("It's not a problem, it's an opportunity.")


def test_em_dash_overuse_fires():
    # Multiple em-dashes triggers the rule.
    assert "em_dash_overuse" in _types("First — second — third — fourth.")


def test_copula_avoidance_fires():
    assert "copula_avoidance" in _types("This serves as a reminder.")


def test_chatbot_artefact_fires():
    assert "chatbot_artefact" in _types("Great question! As an AI, I cannot say.")


def test_foreign_script_artefact_fires_arabic():
    """The original motivating case: a stray Arabic word in English prose."""
    text = (
        "The crisis collapsed the فاصلة between events and awareness, "
        "leaving readers exhausted and detached from the news cycle."
    )
    tells = detect_ai_tells(text)
    foreign = [t for t in tells if t["tell_type"] == "foreign_script_artefact"]
    assert len(foreign) == 1
    assert foreign[0]["text"] == "فاصلة"
    assert "Arabic" in foreign[0]["label"]


def test_foreign_script_artefact_fires_cjk():
    text = (
        "We deployed the new build on Tuesday, and the 漢字 token snuck "
        "into the English copy somewhere in the translation pipeline."
    )
    types = _types(text)
    assert "foreign_script_artefact" in types


def test_foreign_script_artefact_skips_diacritics_and_greek():
    """Latin diacritics and isolated Greek letters should NOT fire."""
    text = (
        "The café in São Paulo serves crème brûlée. The α-helix and π-bond "
        "are standard chemistry notation that any textbook will cover."
    )
    types = _types(text)
    assert "foreign_script_artefact" not in types


def test_foreign_script_artefact_skips_multilingual_doc():
    """When the doc is mostly non-Latin, don't flag the foreign chars."""
    # Mostly Arabic text with one English phrase quoted inside.
    text = (
        "هذا نص عربي طويل يحتوي على كلمات كثيرة جدا "
        "وأيضا بعض الجمل الإضافية لإثبات أن النص "
        "بالعربية بشكل أساسي ولا يجب الإبلاغ عنه. "
        'And a brief English aside: "hello world".'
    )
    types = _types(text)
    assert "foreign_script_artefact" not in types


def test_clean_text_has_few_tells():
    text = "We shipped on Tuesday. The build broke twice. Both times because of the same flag."
    tells = detect_ai_tells(text)
    # Allow up to 1 incidental match — the goal is "no obvious LLM scent".
    assert len(tells) <= 1, f"unexpected tells: {tells}"


def test_compute_readability_basic():
    text = "The cat sat on the mat. The dog watched from the porch."
    stats = compute_readability(text)
    assert stats["word_count"] == 12
    assert stats["sentence_count"] == 2
    assert stats["flesch_reading_ease"] > 0


def test_compute_readability_empty():
    stats = compute_readability("   ")
    assert stats["word_count"] == 0
    assert stats["sentence_count"] == 0
