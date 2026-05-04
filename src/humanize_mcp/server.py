"""humanize-mcp: MCP server entrypoint.

Exposes the heuristic detector, readability stats, optional Ollama deep scan,
the AI rewrite ("humanize") pipeline with pluggable provider, and CRUD over a
JSON-backed preset library.

Run with `python -m humanize_mcp.server` or the `humanize-mcp` console script.
Stdio transport is used by default — suitable for Claude Desktop, Claude Code,
Cursor, Cline, and any MCP client that spawns the server as a subprocess.

Made by Oliver Rochford · Aunoo AI.
"""

from __future__ import annotations

from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

from .config import Config, VALID_PROVIDERS
from .deep_scan import deep_scan as _deep_scan
from .deep_scan import render_verdict as _render_verdict
from .detection import compute_readability as _compute_readability
from .detection import detect_ai_tells as _detect_ai_tells
from .presets import PresetError, PresetStore
from .prompts import SYSTEM_PROMPT, build_user_prompt, normalize_quotes
from .providers import ProviderError, available_providers, get_provider


CONFIG = Config.from_env()
PRESETS = PresetStore(CONFIG.presets_path)
mcp = FastMCP("humanize")


# ── Pure tools (no LLM) ────────────────────────────────────────────────────


@mcp.tool()
def detect_ai_tells(text: str) -> dict:
    """Scan text for AI writing tells using 31 regex/heuristic detectors.

    Returns the matched tells (with offsets and suggestions) plus readability
    stats. Pure function — no LLM calls, no network.
    """
    return {
        "tells": _detect_ai_tells(text),
        "stats": _compute_readability(text),
    }


@mcp.tool()
def compute_readability(text: str) -> dict:
    """Return readability metrics for the given text.

    Includes word/sentence counts, Flesch reading ease, type-token vocabulary
    diversity, em-dash count, and markdown-bold count.
    """
    return _compute_readability(text)


# ── Optional SLM deep scan (Ollama) ────────────────────────────────────────


@mcp.tool()
def deep_scan(text: str) -> dict:
    """Run optional Ollama-backed scans for tells regex can't catch.

    Detects: inflated symbolism, faux-insightful (TED-talk) voice, and
    rhetorical escalation across consecutive sentence triples. Requires the
    HUMANIZE_OLLAMA_URL env var; returns {"available": false} cleanly when the
    server isn't reachable.
    """
    return _deep_scan(text, CONFIG.ollama_url, CONFIG.ollama_model)


@mcp.tool()
def classify_verdict(text: str) -> dict:
    """Run heuristic detection and ask the local SLM for an AI/human verdict.

    Returns {available, verdict, confidence, reason}. Requires Ollama; degrades
    cleanly to {"available": false} if not configured.
    """
    tells = _detect_ai_tells(text)
    stats = _compute_readability(text)
    return _render_verdict(text, tells, stats, CONFIG.ollama_url, CONFIG.ollama_model)


# ── Humanize rewrite pipeline ──────────────────────────────────────────────


def _resolve_preset(
    preset_id: Optional[str],
    tone: str,
    paragraph_style: str,
    length_mode: str,
    formality: str,
) -> tuple[str, str, str, str, str, str, str]:
    """Apply preset overrides for any per-call args left at their defaults.

    Returns (tone, paragraph_style, length_mode, formality, preset_instructions,
    preset_example_input, preset_example_output). Raises PresetError on miss.
    """
    if not preset_id:
        return tone, paragraph_style, length_mode, formality, "", "", ""
    preset = PRESETS.get(preset_id)
    if tone == "neutral" and preset.get("tone"):
        tone = preset["tone"]
    if paragraph_style == "preserve" and preset.get("paragraph_style"):
        paragraph_style = preset["paragraph_style"]
    if length_mode == "preserve" and preset.get("length_mode"):
        length_mode = preset["length_mode"]
    if formality == "preserve" and preset.get("formality"):
        formality = preset["formality"]
    return (
        tone,
        paragraph_style,
        length_mode,
        formality,
        preset.get("instructions", "") or "",
        preset.get("example_input", "") or "",
        preset.get("example_output", "") or "",
    )


@mcp.tool()
def build_humanize_prompt(
    text: str,
    tone: str = "neutral",
    instructions: str = "",
    preset_id: Optional[str] = None,
    pass_number: int = 1,
    paragraph_style: str = "preserve",
    length_mode: str = "preserve",
    formality: str = "preserve",
) -> dict:
    """Build the humanize prompt without calling any LLM.

    Use this when the calling agent IS the LLM that should do the rewrite — no
    second model, no API key needed. The agent reads {system_prompt, user_prompt}
    and produces the rewritten text itself in its next turn.

    Returns:
        {system_prompt, user_prompt, tells_before, stats_before, instructions_for_caller}
    """
    try:
        (
            tone,
            paragraph_style,
            length_mode,
            formality,
            preset_instructions,
            preset_example_input,
            preset_example_output,
        ) = _resolve_preset(preset_id, tone, paragraph_style, length_mode, formality)
    except PresetError as e:
        return {"error": str(e)}

    user_prompt = build_user_prompt(
        text=text,
        tone=tone,
        instructions=instructions,
        preset_instructions=preset_instructions,
        preset_example_input=preset_example_input,
        preset_example_output=preset_example_output,
        pass_number=pass_number,
        paragraph_style=paragraph_style,
        length_mode=length_mode,
        formality=formality,
    )
    return {
        "system_prompt": SYSTEM_PROMPT,
        "user_prompt": user_prompt,
        "tells_before": _detect_ai_tells(text),
        "stats_before": _compute_readability(text),
        "instructions_for_caller": (
            "You are the LLM. Apply system_prompt to user_prompt and produce the "
            "rewritten text yourself. Then call detect_ai_tells(rewritten) and "
            "compute_readability(rewritten) to compare before/after if you want stats."
        ),
    }


@mcp.tool()
def humanize_text(
    text: str,
    tone: str = "neutral",
    instructions: str = "",
    preset_id: Optional[str] = None,
    pass_number: int = 1,
    paragraph_style: str = "preserve",
    length_mode: str = "preserve",
    formality: str = "preserve",
    provider: Optional[str] = None,
    model: Optional[str] = None,
    temperature: float = 0.4,
    max_tokens: int = 4000,
    dry_run: bool = False,
) -> dict:
    """Rewrite text to remove AI writing tells while preserving meaning.

    Pipeline: build prompt → call configured LLM provider → normalize quotes →
    detect tells & compute readability for both original and rewritten text.

    Args:
        text: The input text to rewrite.
        tone: Target tone label (e.g. "neutral", "friendly", "skeptical").
        instructions: Free-form additional instructions for this call.
        preset_id: Optional saved preset to load tone/style/example from. Per-call
            arguments override the preset's values.
        pass_number: 1 = first pass, >1 hints "look harder".
        paragraph_style: "preserve" | "prose" | "short_lines".
        length_mode: "preserve" | "concise" | "expand".
        formality: "preserve" | "formal" | "casual".
        provider: "anthropic" | "openai" | "bedrock". Falls back to env default.
        model: Provider-specific model id. Falls back to provider's default.
        temperature: Sampling temperature (ignored for OpenAI o-series).
        max_tokens: Max output tokens.
        dry_run: If true, skip the LLM call and return {system_prompt, user_prompt}
            so the calling agent can do the rewrite itself. Equivalent to
            build_humanize_prompt — no provider credentials needed.

    Returns:
        {original, rewritten, model, provider, latency_ms, tokens,
         stats_before, stats_after, tells_before, tells_after} on success.
        {system_prompt, user_prompt, ...} if dry_run=True.
        {error: str} on any failure.
    """
    try:
        (
            tone,
            paragraph_style,
            length_mode,
            formality,
            preset_instructions,
            preset_example_input,
            preset_example_output,
        ) = _resolve_preset(preset_id, tone, paragraph_style, length_mode, formality)
    except PresetError as e:
        return {"error": str(e)}

    user_prompt = build_user_prompt(
        text=text,
        tone=tone,
        instructions=instructions,
        preset_instructions=preset_instructions,
        preset_example_input=preset_example_input,
        preset_example_output=preset_example_output,
        pass_number=pass_number,
        paragraph_style=paragraph_style,
        length_mode=length_mode,
        formality=formality,
    )

    if dry_run:
        return {
            "dry_run": True,
            "system_prompt": SYSTEM_PROMPT,
            "user_prompt": user_prompt,
            "tells_before": _detect_ai_tells(text),
            "stats_before": _compute_readability(text),
            "instructions_for_caller": (
                "dry_run=True. Apply system_prompt to user_prompt yourself and "
                "produce the rewritten text — no provider was called."
            ),
        }

    chosen_provider_name = (provider or CONFIG.default_provider).lower()
    if chosen_provider_name not in VALID_PROVIDERS:
        return {"error": f"unknown provider {chosen_provider_name!r}; valid: {VALID_PROVIDERS}"}

    try:
        backend = get_provider(chosen_provider_name)
    except ProviderError as e:
        return {"error": str(e)}

    if not backend.is_configured():
        return {"error": f"provider {chosen_provider_name!r} is not configured (missing credentials)"}

    chosen_model = model or CONFIG.default_model

    try:
        result = backend.rewrite(
            system_prompt=SYSTEM_PROMPT,
            user_text=user_prompt,
            model=chosen_model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    except ProviderError as e:
        return {"error": str(e)}

    rewritten = normalize_quotes(result.text)
    return {
        "original": text,
        "rewritten": rewritten,
        "provider": chosen_provider_name,
        "model": result.model,
        "latency_ms": result.latency_ms,
        "tokens": {"prompt": result.input_tokens, "completion": result.output_tokens},
        "stats_before": _compute_readability(text),
        "stats_after": _compute_readability(rewritten),
        "tells_before": _detect_ai_tells(text),
        "tells_after": _detect_ai_tells(rewritten),
    }


# ── Tone presets CRUD ──────────────────────────────────────────────────────


@mcp.tool()
def list_presets() -> dict:
    """List all saved tone presets."""
    return {"presets": PRESETS.list()}


@mcp.tool()
def get_preset(preset_id: str) -> dict:
    """Fetch a single preset by id."""
    try:
        return PRESETS.get(preset_id)
    except PresetError as e:
        return {"error": str(e)}


@mcp.tool()
def create_preset(
    name: str,
    tone: Optional[str] = None,
    paragraph_style: Optional[str] = None,
    length_mode: Optional[str] = None,
    formality: Optional[str] = None,
    instructions: Optional[str] = None,
    example_input: Optional[str] = None,
    example_output: Optional[str] = None,
) -> dict:
    """Create a new tone preset and return the stored record (with generated id)."""
    try:
        return PRESETS.create(
            name=name,
            tone=tone,
            paragraph_style=paragraph_style,
            length_mode=length_mode,
            formality=formality,
            instructions=instructions,
            example_input=example_input,
            example_output=example_output,
        )
    except PresetError as e:
        return {"error": str(e)}


@mcp.tool()
def update_preset(
    preset_id: str,
    name: Optional[str] = None,
    tone: Optional[str] = None,
    paragraph_style: Optional[str] = None,
    length_mode: Optional[str] = None,
    formality: Optional[str] = None,
    instructions: Optional[str] = None,
    example_input: Optional[str] = None,
    example_output: Optional[str] = None,
) -> dict:
    """Update fields on an existing preset. Pass only the fields you want to change."""
    try:
        return PRESETS.update(
            preset_id,
            name=name,
            tone=tone,
            paragraph_style=paragraph_style,
            length_mode=length_mode,
            formality=formality,
            instructions=instructions,
            example_input=example_input,
            example_output=example_output,
        )
    except PresetError as e:
        return {"error": str(e)}


@mcp.tool()
def delete_preset(preset_id: str) -> dict:
    """Delete a preset by id."""
    try:
        PRESETS.delete(preset_id)
        return {"deleted": preset_id}
    except PresetError as e:
        return {"error": str(e)}


# ── Introspection ──────────────────────────────────────────────────────────


@mcp.tool()
def server_info() -> dict:
    """Return server identity, version, and attribution."""
    from . import __author__, __organization__, __version__

    return {
        "name": "humanize-mcp",
        "version": __version__,
        "author": __author__,
        "organization": __organization__,
        "description": (
            "Heuristic AI-tells detection, optional SLM deep scan, and humanized "
            "rewrite via Anthropic / OpenAI / Bedrock."
        ),
    }


@mcp.tool()
def list_providers() -> dict:
    """Return available LLM providers and which are configured at the moment."""
    out: dict[str, Any] = {"default": CONFIG.default_provider, "providers": []}
    for name in available_providers():
        try:
            p = get_provider(name)
            out["providers"].append(
                {"name": name, "default_model": p.default_model, "configured": p.is_configured()}
            )
        except ProviderError as e:
            out["providers"].append({"name": name, "error": str(e), "configured": False})
    return out


def main() -> None:
    """Console-script entrypoint. Runs the MCP server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
