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
