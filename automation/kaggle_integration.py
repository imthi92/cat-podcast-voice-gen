"""Kaggle GPU integration for CatHub Podcast.

Wraps the shared kaggle_gpu module with CatHub specific tasks.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_kaggle_gpu = None


def _get_gpu():
    """Lazy-load KaggleGPU instance."""
    global _kaggle_gpu
    if _kaggle_gpu is None:
        try:
            from kaggle_gpu import KaggleGPU
            _kaggle_gpu = KaggleGPU(project_name="cat-podcast-voice-gen")
        except Exception as e:
            logger.warning(f"Kaggle GPU init failed: {e}")
            _kaggle_gpu = False
    return _kaggle_gpu if _kaggle_gpu is not False else None


def kaggle_generate_vibevoice(
    text: str,
    model: str = "microsoft/VibeVoice-1.5B",
) -> str:
    """Generate voice via Kaggle GPU (VibeVoice).

    Returns: path to generated audio, or empty string if Kaggle unavailable.
    """
    gpu = _get_gpu()
    if not gpu:
        return ""

    try:
        from kaggle_gpu import GPUTask
        result = gpu.run_task(
            task=GPUTask.VIBEVOICE,
            payload={
                "text": text,
                "model": model,
            },
            estimated_hours=0.20,
        )
        if result and result.get("output_files"):
            return result["output_files"][0]
        return ""
    except Exception as e:
        logger.warning(f"Kaggle VibeVoice failed: {e}")
        return ""


def kaggle_animate_face(
    source_image: str,
    driven_audio: str,
) -> str:
    """Animate face via Kaggle GPU (SadTalker).

    Returns: path to generated video, or empty string if Kaggle unavailable.
    """
    gpu = _get_gpu()
    if not gpu:
        return ""

    try:
        from kaggle_gpu import GPUTask
        result = gpu.run_task(
            task=GPUTask.SADTALKER,
            payload={
                "source_image": source_image,
                "driven_audio": driven_audio,
            },
            estimated_hours=0.25,
        )
        if result and result.get("output_files"):
            return result["output_files"][0]
        return ""
    except Exception as e:
        logger.warning(f"Kaggle face animation failed: {e}")
        return ""


def kaggle_generate_image(
    prompt: str,
    negative_prompt: str = "",
    width: int = 1024,
    height: int = 1024,
) -> str:
    """Generate image via Kaggle GPU (SDXL).

    Returns: path to generated image, or empty string if Kaggle unavailable.
    """
    gpu = _get_gpu()
    if not gpu:
        return ""

    try:
        from kaggle_gpu import GPUTask
        result = gpu.run_task(
            task=GPUTask.SDXL_IMAGE,
            payload={
                "prompt": prompt,
                "negative_prompt": negative_prompt,
                "width": width,
                "height": height,
            },
            estimated_hours=0.15,
        )
        if result and result.get("output_files"):
            return result["output_files"][0]
        return ""
    except Exception as e:
        logger.warning(f"Kaggle image generation failed: {e}")
        return ""


def kaggle_status() -> dict:
    """Get Kaggle GPU integration status."""
    gpu = _get_gpu()
    if not gpu:
        return {"enabled": False, "reason": "Not configured or init failed"}
    return gpu.get_status()
