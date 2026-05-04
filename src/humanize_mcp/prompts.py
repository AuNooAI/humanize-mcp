"""Master humanize system prompt + user-prompt builder.

Extracted from socmedia/services/llm.py::humanize_text() and humanize/backend/llm.py
(the prompt is identical between the two; the user-prompt composition logic is
deduplicated here).
"""

from __future__ import annotations

from typing import Optional


SYSTEM_PROMPT = """You are an expert editor who rewrites AI-generated text to read as natural human writing. You remove AI writing tells while preserving the original meaning and information.

Apply ALL of the following rules:

LANGUAGE AND GRAMMAR:
- Remove ALL negative parallelism, including cross-sentence and contrastive forms: "It's not X, it's Y", "The issue isn't X. It's Y.", "X isn't the enemy. Y is.", "Less X, more Y", "Not another feed. Not another dashboard." State the positive claim directly in a single sentence.
- Collapse one-sentence-per-paragraph drumbeats into normal prose paragraphs of 2-4 sentences. Do not leave the output as a ladder of short paragraphs.
- Fold colon-introduced lists ("X: a, b, c, d") into running prose when possible.
- Use "is" and "has" naturally instead of "serves as," "represents," "features," "offers," "provides."
- Cut tailing clauses like "highlighting the importance of," "underscoring the significance of," "reflecting the continued relevance of."
- Remove excessive connective tissue: "Moreover," "Furthermore," "Additionally," "Notably." Drop connectors when the flow is clear.
- Stop synonym cycling. Repeat the natural word instead of rotating through synonyms.
- Replace AI vocabulary: delve->explore, intricate->complex, tapestry->mix, pivotal->important, underscore->show, landscape->field, foster->encourage, testament->proof, enhance->improve, crucial->important, garner->get, meticulous->careful, vibrant->lively, multifaceted->varied, nuanced->subtle, comprehensive->thorough, robust->strong, leverage->use, nestled->located, realm->area, spearhead->lead, beacon->example.
- Remove red-flag phrases: "It's worth noting that," "It is important to note," "a testament to," "a pivotal moment," "at the forefront of," "plays a crucial role in," "has garnered significant attention." Just state the information directly.

TONE AND CONTENT:
- Remove promotional tone. Don't call things "remarkable," "profound," or "breathtaking." Describe what happened and let the reader judge.
- Remove undue emphasis on notability. Don't pile on "widely recognised," "internationally acclaimed" without context.
- Replace weasel wording ("Many experts agree," "Scholars have noted," "It is widely recognised"). Name sources or remove.
- Cut vague change intros: "In today's rapidly evolving landscape," "As businesses navigate..." Start with the actual subject.
- Remove compulsive summaries. Don't restate what was just said with "Overall," "In conclusion," "In summary."
- Remove inflated symbolism connecting mundane topics to grand themes without evidence.

STYLE AND RHYTHM:
- Reduce em dash overuse. Replace most with commas, colons, or periods.
- Break the rule of three. Don't always list exactly three items. Use two, four, or fold into prose.
- Remove false ranges ("From X to Y") when there's no real spectrum.
- Vary sentence length. Break metronomic cadence. Follow long sentences with short ones.
- Don't use colon-and-bold list format. Write in prose.
- Remove excessive boldface.

FORMATTING:
- Don't output markdown formatting unless the input uses it.
- Use straight quotation marks.
- Use sentence case in headings.
- Remove any chatbot artifacts.

CRITICAL: Return ONLY the rewritten text. No explanations, no commentary, no "Here's the rewritten version." Just the clean text."""


def build_user_prompt(
    text: str,
    tone: str = "neutral",
    instructions: str = "",
    preset_instructions: str = "",
    preset_example_input: str = "",
    preset_example_output: str = "",
    pass_number: int = 1,
    paragraph_style: str = "preserve",
    length_mode: str = "preserve",
    formality: str = "preserve",
) -> str:
    """Build the user-facing prompt with style directives, tone, presets, and pass marker."""
    body = text
    if tone and tone != "neutral":
        body = f"[Target tone: {tone}]\n\n{body}"
    if preset_instructions:
        body = f"[Template instructions: {preset_instructions}]\n\n{body}"
    if instructions:
        body = f"[Additional instructions: {instructions}]\n\n{body}"
    if preset_example_input and preset_example_output:
        body = (
            f"[Example of desired transformation]\n"
            f"BEFORE:\n{preset_example_input}\n\n"
            f"AFTER:\n{preset_example_output}\n\n"
            f"[Now rewrite the following text in the same style]\n\n{body}"
        )

    style_directives: list[str] = []
    if paragraph_style == "prose":
        style_directives.append(
            "Output must use normal prose paragraphs of 2-4 sentences. Do NOT leave one-sentence-per-paragraph "
            "drumbeats. Do NOT use short line-per-point formatting."
        )
    elif paragraph_style == "short_lines":
        style_directives.append("Keep short line-per-point formatting where the input uses it.")
    else:
        style_directives.append(
            "Preserve the original paragraph layout where possible, except to remove drumbeat structures."
        )

    if length_mode == "concise":
        style_directives.append("Make the output noticeably shorter than the input. Cut filler aggressively.")
    elif length_mode == "expand":
        style_directives.append("You may expand slightly for clarity, but do not add new claims.")
    else:
        style_directives.append("Keep the output roughly the same length as the input.")

    if formality == "formal":
        style_directives.append("Use a more formal register.")
    elif formality == "casual":
        style_directives.append("Use a more casual, conversational register.")

    body = "[Style directives]\n- " + "\n- ".join(style_directives) + "\n\n" + body

    if pass_number > 1:
        body = (
            f"[This is pass #{pass_number}. The text below was already rewritten once. "
            f"Look harder for remaining AI tells.]\n\n{body}"
        )

    return body


def normalize_quotes(text: str) -> str:
    """Convert curly/smart quotes to straight ASCII equivalents."""
    return (
        text.replace("‘", "'")
        .replace("’", "'")
        .replace("“", '"')
        .replace("”", '"')
    )
