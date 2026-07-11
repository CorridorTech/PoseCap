"""Behavior tests for the Body Models wizard, status, and its operators."""

from types import SimpleNamespace
from typing import Any

import posecap_addon.model_setup_panel as model_setup_panel
from posecap_addon.model_setup_panel import (
    MODEL_SIGNUP_URLS,
    build_model_setup_classes,
    draw_body_models_wizard,
    draw_model_setup_status,
)


class _FakeOperatorProps:
    def __init__(self) -> None:
        self.url = ""


class _FakeLayout:
    def __init__(self, sink: "dict[str, list] | None" = None) -> None:
        self._sink = sink if sink is not None else {"operators": [], "props": [], "labels": []}

    def row(self, **_kwargs: object) -> "_FakeLayout":
        return _FakeLayout(self._sink)

    def column(self, **_kwargs: object) -> "_FakeLayout":
        return _FakeLayout(self._sink)

    def box(self) -> "_FakeLayout":
        return _FakeLayout(self._sink)

    def label(self, *, text: str, icon: str = "NONE") -> None:
        self._sink["labels"].append(text)

    def prop(self, _data: object, name: str, **_kwargs: object) -> None:
        self._sink["props"].append(name)

    def operator(self, operator_id: str, **_kwargs: object) -> _FakeOperatorProps:
        props = _FakeOperatorProps()
        self._sink["operators"].append((operator_id, props))
        return props

    def progress(self, *, factor: float, type: str = "BAR", text: str = "") -> None:
        self._sink.setdefault("progress", []).append(factor)
        self._sink["labels"].append(text)

    @property
    def progress_factors(self) -> list[float]:
        return self._sink.get("progress", [])

    @property
    def operator_ids(self) -> list[str]:
        return [operator_id for operator_id, _props in self._sink["operators"]]

    @property
    def urls(self) -> list[str]:
        return [props.url for _id, props in self._sink["operators"] if props.url]

    @property
    def props_drawn(self) -> list[str]:
        return self._sink["props"]

    @property
    def labels(self) -> list[str]:
        return self._sink["labels"]


def _wm_group(email: str = "", password: str = "") -> SimpleNamespace:
    return SimpleNamespace(mpi_email=email, mpi_password=password, status="")


def test_wizard_form_offers_signup_credentials_and_manual_path() -> None:
    layout = _FakeLayout()

    draw_body_models_wizard(layout, _wm_group())

    signup_buttons = [url for url in layout.urls if url in set(MODEL_SIGNUP_URLS.values())]
    assert len(signup_buttons) == 3, "one sign-up button per MPI site"
    assert "mpi_email" in layout.props_drawn
    assert "mpi_password" in layout.props_drawn
    # The manual-download escape hatch survives the move into the wizard.
    assert "posecap.watch_model_downloads" in layout.operator_ids


def test_status_is_empty_when_no_session() -> None:
    layout = _FakeLayout()

    draw_model_setup_status(layout, None)

    assert layout.operator_ids == []
    assert layout.props_drawn == []
    assert layout.labels == []


def test_status_shows_running_session_progress() -> None:
    layout = _FakeLayout()
    session = SimpleNamespace(state="RUNNING", status_message="Downloading FLAME2020.zip…")

    draw_model_setup_status(layout, session)

    assert "Downloading FLAME2020.zip…" in layout.labels
    assert layout.props_drawn == []


def test_status_shows_a_finished_session_message() -> None:
    layout = _FakeLayout()
    session = SimpleNamespace(state="DONE", status_message="Models installed.")

    draw_model_setup_status(layout, session)

    assert "Models installed." in layout.labels


def test_status_wraps_a_long_failure_so_the_whole_message_is_readable() -> None:
    layout = _FakeLayout()
    message = (
        "The downloaded archive does not contain SMPL_NEUTRAL.pkl. "
        "Please retry, or download it manually from the official site."
    )
    session = SimpleNamespace(state="FAILED", status_message=message)

    draw_model_setup_status(layout, session, wrap_chars=28)

    # No single label carries the whole thing (it would truncate), but joined
    # across the wrapped labels the full message is present — nothing hidden.
    assert len(layout.labels) > 1, "a long failure must span several labels"
    joined = " ".join(layout.labels)
    assert "SMPL_NEUTRAL.pkl" in joined
    assert "official site" in joined


def test_status_shows_a_progress_bar_while_a_download_has_a_measurable_fraction() -> None:
    layout = _FakeLayout()
    session = SimpleNamespace(
        state="RUNNING",
        status_message="Downloading FLAME2020.zip — 45 / 167 MB",
        progress_fraction=0.27,
    )

    draw_model_setup_status(layout, session)

    assert layout.progress_factors == [0.27], "a measurable download draws a real bar"
    assert any("45 / 167 MB" in text for text in layout.labels)


class _FakeSession:
    def __init__(self, **_kwargs: object) -> None:
        self.state = "IDLE"
        self.status_message = ""
        self.credential_calls: list[tuple[object, object]] = []
        self.watch_calls: list[tuple[object, object]] = []

    def start_credential_install(self, pear_root, credentials) -> None:
        self.state = "RUNNING"
        self.credential_calls.append((pear_root, credentials))

    def start_watching(self, pear_root, downloads_dir) -> None:
        self.state = "WATCHING"
        self.watch_calls.append((pear_root, downloads_dir))

    def tick(self) -> None:
        return None


class _FakeTimers:
    def __init__(self) -> None:
        self.registered = []

    def register(self, function, *, first_interval: float = 0.0, persistent: bool = False):
        self.registered.append(function)

    def unregister(self, function) -> None:
        self.registered.remove(function)

    def is_registered(self, function) -> bool:
        return function in self.registered


class _FakeOperatorBase:
    def __init__(self) -> None:
        self.reported: list[tuple[set, str]] = []

    def report(self, level, message) -> None:
        self.reported.append((level, message))


def _fake_bpy_module(wm_group: SimpleNamespace) -> SimpleNamespace:
    context = SimpleNamespace(
        window_manager=SimpleNamespace(posecap_model_setup=wm_group, windows=[]),
    )
    return SimpleNamespace(
        app=SimpleNamespace(timers=_FakeTimers()),
        context=context,
        types=SimpleNamespace(Operator=_FakeOperatorBase),
    )


def _operator_context(wm_group: SimpleNamespace, *, pear_root: str = "C:/PEAR"):
    settings = SimpleNamespace(pear_root=pear_root)
    return SimpleNamespace(
        scene=SimpleNamespace(posecap=settings),
        window_manager=SimpleNamespace(posecap_model_setup=wm_group, windows=[]),
        preferences=SimpleNamespace(addons={}),
    )


def test_setup_operator_starts_a_session_and_clears_the_password(monkeypatch) -> None:
    wm_group = _wm_group(email="emmet@corridor.example", password="pw")
    bpy_module = _fake_bpy_module(wm_group)
    monkeypatch.setattr(model_setup_panel, "ModelSetupSession", _FakeSession)
    setup_cls, _watch_cls, _wizard_cls = build_model_setup_classes(bpy_module)

    result = setup_cls().execute(_operator_context(wm_group))

    assert result == {"FINISHED"}
    session: Any = model_setup_panel.active_model_setup_session()
    assert session is not None and session.credential_calls
    credentials = session.credential_calls[0][1]
    assert credentials.email == "emmet@corridor.example"
    assert credentials.password == "pw"
    assert wm_group.mpi_password == "", "password must not linger in the UI field"
    assert len(bpy_module.app.timers.registered) == 1


def test_setup_operator_asks_for_credentials_when_fields_are_empty(monkeypatch) -> None:
    wm_group = _wm_group()
    bpy_module = _fake_bpy_module(wm_group)
    monkeypatch.setattr(model_setup_panel, "ModelSetupSession", _FakeSession)
    setup_cls, _watch_cls, _wizard_cls = build_model_setup_classes(bpy_module)

    result = setup_cls().execute(_operator_context(wm_group))

    assert result == {"CANCELLED"}
    assert "email" in wm_group.status.lower() or "password" in wm_group.status.lower()


def test_setup_operator_asks_for_pear_root_when_unset(monkeypatch) -> None:
    # Hide any installed runtime so the installer fallback can't resolve a root
    # and this asserts the genuine "nothing configured" guidance.
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.delenv("POSECAP_PEAR_ROOT", raising=False)
    wm_group = _wm_group(email="a@b.c", password="pw")
    bpy_module = _fake_bpy_module(wm_group)
    monkeypatch.setattr(model_setup_panel, "ModelSetupSession", _FakeSession)
    setup_cls, _watch_cls, _wizard_cls = build_model_setup_classes(bpy_module)

    result = setup_cls().execute(_operator_context(wm_group, pear_root=""))

    assert result == {"CANCELLED"}
    assert "pear root" in wm_group.status.lower()


def test_setup_operator_resolves_installer_pear_root_on_a_fresh_install(
    monkeypatch, tmp_path
) -> None:
    # Clean install: nothing typed, but the installer laid down its pear dir.
    # The operator must find it (same fallback as the engine) instead of
    # stopping with "Set the PEAR Root first" — the wizard's clean-install bug.
    installer_pear = tmp_path / "PoseCap" / "pear"
    installer_pear.mkdir(parents=True)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.delenv("POSECAP_PEAR_ROOT", raising=False)
    wm_group = _wm_group(email="a@b.c", password="pw")
    bpy_module = _fake_bpy_module(wm_group)
    monkeypatch.setattr(model_setup_panel, "ModelSetupSession", _FakeSession)
    setup_cls, _watch_cls, _wizard_cls = build_model_setup_classes(bpy_module)

    result = setup_cls().execute(_operator_context(wm_group, pear_root=""))

    assert result == {"FINISHED"}
    session: Any = model_setup_panel.active_model_setup_session()
    assert session is not None and session.credential_calls
    assert session.credential_calls[0][0] == installer_pear


def test_wizard_cancel_reports_the_error_to_blender(monkeypatch) -> None:
    # The wizard is a popup that closes on execute(): a hidden status label is
    # invisible, so a validation failure must reach Blender's info log/report.
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.delenv("POSECAP_PEAR_ROOT", raising=False)
    wm_group = _wm_group(email="a@b.c", password="pw")
    bpy_module = _fake_bpy_module(wm_group)
    monkeypatch.setattr(model_setup_panel, "ModelSetupSession", _FakeSession)
    _setup_cls, _watch_cls, wizard_cls = build_model_setup_classes(bpy_module)
    operator = wizard_cls()

    result = operator.execute(_operator_context(wm_group, pear_root=""))

    assert result == {"CANCELLED"}
    assert operator.reported, (
        "cancel must report, not only set a label the closed dialog can't show"
    )
    level, message = operator.reported[0]
    assert level == {"ERROR"}
    assert "pear root" in message.lower()


def test_wizard_operator_opens_a_props_dialog() -> None:
    wm_group = _wm_group()
    bpy_module = _fake_bpy_module(wm_group)
    _setup_cls, _watch_cls, wizard_cls = build_model_setup_classes(bpy_module)
    calls: list[dict[str, object]] = []

    class _DialogWindowManager:
        def invoke_props_dialog(self, operator, *, width: int) -> set[str]:
            calls.append({"operator": operator, "width": width})
            return {"RUNNING_MODAL"}

    context = SimpleNamespace(window_manager=_DialogWindowManager())
    operator = wizard_cls()

    result = operator.invoke(context, None)

    assert result == {"RUNNING_MODAL"}
    assert calls and calls[0]["operator"] is operator
    assert calls[0]["width"] == 480


def test_wizard_operator_draws_the_guided_form() -> None:
    wm_group = _wm_group()
    bpy_module = _fake_bpy_module(wm_group)
    _setup_cls, _watch_cls, wizard_cls = build_model_setup_classes(bpy_module)
    operator = wizard_cls()
    operator.layout = _FakeLayout()
    context = SimpleNamespace(
        window_manager=SimpleNamespace(posecap_model_setup=wm_group, windows=[]),
    )

    operator.draw(context)

    assert "mpi_email" in operator.layout.props_drawn
    assert "mpi_password" in operator.layout.props_drawn
    signup_buttons = [url for url in operator.layout.urls if url in set(MODEL_SIGNUP_URLS.values())]
    assert len(signup_buttons) == 3


def test_wizard_operator_execute_starts_the_credential_install(monkeypatch) -> None:
    wm_group = _wm_group(email="a@b.c", password="pw")
    bpy_module = _fake_bpy_module(wm_group)
    monkeypatch.setattr(model_setup_panel, "ModelSetupSession", _FakeSession)
    _setup_cls, _watch_cls, wizard_cls = build_model_setup_classes(bpy_module)

    result = wizard_cls().execute(_operator_context(wm_group))

    assert result == {"FINISHED"}
    session: Any = model_setup_panel.active_model_setup_session()
    assert session is not None and session.credential_calls
    assert wm_group.mpi_password == ""
    assert len(bpy_module.app.timers.registered) == 1


def test_watch_operator_starts_the_downloads_watcher(monkeypatch) -> None:
    wm_group = _wm_group()
    bpy_module = _fake_bpy_module(wm_group)
    monkeypatch.setattr(model_setup_panel, "ModelSetupSession", _FakeSession)
    _setup_cls, watch_cls, _wizard_cls = build_model_setup_classes(bpy_module)

    result = watch_cls().execute(_operator_context(wm_group))

    assert result == {"FINISHED"}
    session: Any = model_setup_panel.active_model_setup_session()
    assert session is not None and session.watch_calls
    assert len(bpy_module.app.timers.registered) == 1


def test_poll_timer_stops_after_the_session_finishes(monkeypatch) -> None:
    wm_group = _wm_group(email="a@b.c", password="pw")
    bpy_module = _fake_bpy_module(wm_group)
    monkeypatch.setattr(model_setup_panel, "ModelSetupSession", _FakeSession)
    setup_cls, _watch_cls, _wizard_cls = build_model_setup_classes(bpy_module)
    setup_cls().execute(_operator_context(wm_group))
    session: Any = model_setup_panel.active_model_setup_session()
    poll = bpy_module.app.timers.registered[0]

    session.status_message = "Downloading…"
    assert poll() is not None
    assert wm_group.status == "Downloading…"

    session.state = "DONE"
    session.status_message = "Models installed."
    assert poll() is None
    assert wm_group.status == "Models installed."
