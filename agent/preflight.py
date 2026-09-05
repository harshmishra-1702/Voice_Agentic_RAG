"""
Rime Voice Preflight Validation Module.

Validates that the chosen Rime TTS model and speaker (default: coda / astra)
are available in Rime's live voice catalog before starting voice sessions.

Runs at agent startup BEFORE accepting any sessions.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

logger = logging.getLogger("voiceops.preflight")

RIME_VOICES_URL: str = "https://users.rime.ai/data/voices/all-v2.json"


def _extract_voices_from_node(node: Any) -> list[str]:
    """Extract voice/speaker names from a model's catalog sub-tree.

    Handles multiple possible schema variants:
      - dict of language -> list of voice names: {"eng": ["astra", "luna"]}
      - dict of voice_name -> voice metadata: {"astra": {...}}
      - list of voice names: ["astra", "luna"]
      - list of voice objects: [{"name": "astra"}, {"speaker": "luna"}]
      - single string: "astra"
    """
    voices: list[str] = []

    if isinstance(node, list):
        for item in node:
            if isinstance(item, str):
                cleaned = item.strip()
                if cleaned:
                    voices.append(cleaned)
            elif isinstance(item, dict):
                for key in (
                    "speaker",
                    "name",
                    "voice",
                    "voiceId",
                    "voice_id",
                    "id",
                    "speaker_name",
                ):
                    val = item.get(key)
                    if isinstance(val, str) and val.strip():
                        voices.append(val.strip())
                        break
    elif isinstance(node, dict):
        for key, val in node.items():
            if isinstance(val, list):
                for item in val:
                    if isinstance(item, str):
                        cleaned = item.strip()
                        if cleaned:
                            voices.append(cleaned)
                    elif isinstance(item, dict):
                        for k in (
                            "speaker",
                            "name",
                            "voice",
                            "voiceId",
                            "voice_id",
                            "id",
                            "speaker_name",
                        ):
                            v_str = item.get(k)
                            if isinstance(v_str, str) and v_str.strip():
                                voices.append(v_str.strip())
                                break
            elif isinstance(val, dict):
                # If value is a dictionary with metadata, either key is voice name or metadata contains it
                v_name = (
                    val.get("speaker")
                    or val.get("name")
                    or val.get("voice")
                    or val.get("voiceId")
                    or val.get("voice_id")
                    or str(key)
                )
                if isinstance(v_name, str) and v_name.strip():
                    voices.append(v_name.strip())
            elif isinstance(val, str):
                cleaned_key = str(key).strip()
                if cleaned_key:
                    voices.append(cleaned_key)
    elif isinstance(node, str):
        cleaned = node.strip()
        if cleaned:
            voices.append(cleaned)

    # Return unique items preserving insertion order
    return list(dict.fromkeys(voices))


def _extract_from_records_list(
    records: list[Any], target_model: str
) -> tuple[bool, list[str], list[str]]:
    """Extract voices from a flat list of voice records.

    Handles structures like:
      [{"model": "coda", "speaker": "astra"}, {"model": "mist", ...}]
    """
    target_lower = target_model.strip().lower()
    voices: list[str] = []
    models_seen: set[str] = set()
    model_found = False

    for item in records:
        if not isinstance(item, dict):
            continue

        item_models: list[str] = []
        for m_key in (
            "model",
            "modelId",
            "model_id",
            "model_name",
            "supported_models",
            "models",
        ):
            m_val = item.get(m_key)
            if isinstance(m_val, str) and m_val.strip():
                item_models.append(m_val.strip())
            elif isinstance(m_val, list):
                for sub in m_val:
                    if isinstance(sub, str) and sub.strip():
                        item_models.append(sub.strip())

        for m in item_models:
            models_seen.add(m)
            if m.lower() == target_lower:
                model_found = True

        if any(m.lower() == target_lower for m in item_models):
            for v_key in (
                "speaker",
                "name",
                "voice",
                "voiceId",
                "voice_id",
                "id",
                "speaker_name",
            ):
                v_val = item.get(v_key)
                if isinstance(v_val, str) and v_val.strip():
                    voices.append(v_val.strip())
                    break

    return model_found, list(dict.fromkeys(voices)), sorted(models_seen)


def _parse_catalog(
    data: Any, target_model: str
) -> tuple[bool, list[str], list[str]]:
    """Parse raw catalog JSON and return (model_found, available_voices, all_models).

    Employs defensive parsing to handle various JSON schema shapes:
      1. Model-keyed mapping: {"coda": {"eng": ["astra", ...]}}
      2. Nested models object: {"models": {"coda": ...}} or {"data": {"coda": ...}}
      3. List of voice records: [{"model": "coda", "speaker": "astra"}, ...]
      4. Dict with "voices" list: {"voices": [...]}
      5. Speaker-keyed mapping: {"astra": {"model": "coda"}}
    """
    target_lower = target_model.strip().lower()

    # Case 1: Top-level dict
    if isinstance(data, dict):
        # Direct check for model name among keys (case-insensitive)
        for key, val in data.items():
            if str(key).strip().lower() == target_lower:
                voices = _extract_voices_from_node(val)
                all_models = [str(k) for k in data.keys()]
                return True, voices, all_models

        # Check for wrapper dicts: 'models' or 'data'
        for wrapper_key in ("models", "data"):
            wrapper = data.get(wrapper_key)
            if isinstance(wrapper, dict):
                for key, val in wrapper.items():
                    if str(key).strip().lower() == target_lower:
                        voices = _extract_voices_from_node(val)
                        all_models = [str(k) for k in wrapper.keys()]
                        return True, voices, all_models

        # Check for list under 'voices', 'data', 'items', 'results'
        for list_key in ("voices", "data", "items", "results"):
            list_val = data.get(list_key)
            if isinstance(list_val, list):
                found, voices, all_models = _extract_from_records_list(
                    list_val, target_model
                )
                if found or voices or all_models:
                    return found, voices, all_models

        # Check if dict is keyed by speaker: {"astra": {"model": "coda"}}
        voices_by_speaker: list[str] = []
        models_seen: set[str] = set()
        for spk_key, spk_info in data.items():
            if isinstance(spk_info, dict):
                m = (
                    spk_info.get("model")
                    or spk_info.get("modelId")
                    or spk_info.get("model_id")
                )
                if isinstance(m, str) and m.strip():
                    models_seen.add(m.strip())
                    if m.strip().lower() == target_lower:
                        voices_by_speaker.append(str(spk_key).strip())

        if models_seen or voices_by_speaker:
            model_found = target_lower in {m.lower() for m in models_seen}
            return (
                model_found,
                list(dict.fromkeys(voices_by_speaker)),
                sorted(models_seen),
            )

        # If it's a dict with other keys, report those keys as models if plausible
        if data:
            return False, [], [str(k) for k in data.keys()]

    # Case 2: Top-level list
    elif isinstance(data, list):
        return _extract_from_records_list(data, target_model)

    return False, [], []


async def validate_rime_voice(
    model: str = "coda",
    speaker: str = "astra",
    *,
    url: str = RIME_VOICES_URL,
    timeout: float = 10.0,
) -> bool:
    """Validate that the specified Rime TTS model and speaker exist in the live catalog.

    Queries the Rime voice catalog endpoint asynchronously via httpx.

    Args:
        model: Target Rime model name (default: 'coda').
        speaker: Target speaker/voice name (default: 'astra').
        url: URL of the Rime voices JSON endpoint.
        timeout: HTTP request timeout in seconds.

    Returns:
        True if the voice is verified to be available.
        False if network error or unparseable catalog occurred (proceeds with warning).

    Raises:
        SystemExit(1): If the catalog is successfully checked and the speaker is missing
                       for the specified model.
    """
    logger.info(
        "Rime preflight: Validating voice '%s' on model '%s' via %s",
        speaker,
        model,
        url,
    )

    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
    except (httpx.HTTPError, OSError, TimeoutError) as exc:
        logger.warning(
            "Rime preflight WARNING: Unable to fetch voice catalog from %s: %s. "
            "Proceeding without voice verification.",
            url,
            exc,
        )
        return False
    except Exception as exc:
        logger.warning(
            "Rime preflight WARNING: Failed to retrieve or parse voice catalog from %s (%s). "
            "Proceeding without voice verification.",
            url,
            exc,
        )
        return False

    model_found, available_voices, all_models = _parse_catalog(data, model)

    # If structure could not be parsed into any recognized models or voices
    if not model_found and not available_voices and not all_models:
        logger.debug("Rime preflight: Raw voice catalog structure: %r", data)
        logger.warning(
            "Rime preflight WARNING: Unrecognized voice catalog structure from %s. "
            "Proceeding without voice verification.",
            url,
        )
        return False

    # If the model itself was not found in the catalog
    if not model_found:
        logger.critical(
            "Rime preflight CRITICAL: Model '%s' was not found in the Rime catalog. "
            "Available models: %s. Cannot verify speaker '%s'.",
            model,
            all_models,
            speaker,
        )
        raise SystemExit(1)

    # Check if speaker is present in available voices (case-insensitive)
    speaker_lower = speaker.strip().lower()
    matched = any(v.strip().lower() == speaker_lower for v in available_voices)

    if not matched:
        logger.critical(
            "Rime preflight CRITICAL: Speaker '%s' is not available for model '%s'. "
            "Available voices for %s: %s",
            speaker,
            model,
            model,
            sorted(available_voices),
        )
        raise SystemExit(1)

    logger.info(
        "Rime preflight OK: speaker %s confirmed on model %s",
        speaker,
        model,
    )
    return True


def run_preflight(model: str = "coda", speaker: str = "astra") -> bool:
    """Convenience synchronous function for startup or import-time preflight checks.

    Args:
        model: Target Rime model name (default: 'coda').
        speaker: Target speaker/voice name (default: 'astra').

    Returns:
        True if voice is confirmed, False if network was unreachable.

    Raises:
        SystemExit(1): If the voice is confirmed to be missing.
    """
    try:
        return asyncio.run(validate_rime_voice(model=model, speaker=speaker))
    except RuntimeError as exc:
        if "running event loop" in str(exc) or "already running" in str(exc):
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(
                    asyncio.run, validate_rime_voice(model=model, speaker=speaker)
                )
                return future.result()
        raise


__all__ = [
    "RIME_VOICES_URL",
    "validate_rime_voice",
    "run_preflight",
]
