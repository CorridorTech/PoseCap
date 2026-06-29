import posecap_addon
import posecap_addon.panels


def test_addon_register_and_unregister_delegate_to_ui_panels(monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(posecap_addon.panels, "register", lambda: calls.append("register"))
    monkeypatch.setattr(posecap_addon.panels, "unregister", lambda: calls.append("unregister"))

    posecap_addon.register()
    posecap_addon.unregister()

    assert calls == ["register", "unregister"]
