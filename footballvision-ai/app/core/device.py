from __future__ import annotations


def resolve_device(requested: str = "auto") -> str:
    choice = (requested or "auto").strip().lower()
    if choice in {"cpu", "none"}:
        return "cpu"
    if choice not in {"auto", "cuda", "gpu", "0"}:
        return requested
    try:
        import torch

        if torch.cuda.is_available():
            return "0"
    except Exception:
        pass
    return "cpu"


def use_half(device: str) -> bool:
    """FP16 only where it is faster.

    GTX 16-series cards (no tensor cores) run FP16 about 2.5x slower than FP32,
    so the default enables it only for tensor-core GPUs. Set FOOTBALLVISION_HALF
    to 1/0 to force it.
    """
    import os

    if device in {"cpu", "none"}:
        return False
    forced = os.environ.get("FOOTBALLVISION_HALF", "").strip().lower()
    if forced in {"1", "true", "yes"}:
        return True
    if forced in {"0", "false", "no"}:
        return False
    try:
        import torch

        if not torch.cuda.is_available():
            return False
        index = int(device) if str(device).isdigit() else 0
        major, _minor = torch.cuda.get_device_capability(index)
        name = torch.cuda.get_device_name(index).upper()
        return major >= 7 and "GTX" not in name
    except Exception:
        return False
