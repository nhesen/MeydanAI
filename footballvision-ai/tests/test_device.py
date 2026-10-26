from app.core.device import use_half


def test_half_never_used_on_cpu(monkeypatch):
    monkeypatch.setenv("FOOTBALLVISION_HALF", "1")
    assert use_half("cpu") is False


def test_half_can_be_forced_or_disabled(monkeypatch):
    monkeypatch.setenv("FOOTBALLVISION_HALF", "1")
    assert use_half("0") is True
    monkeypatch.setenv("FOOTBALLVISION_HALF", "0")
    assert use_half("0") is False
