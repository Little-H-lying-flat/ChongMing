from types import SimpleNamespace

from app.utils import autogen_runtime


def test_autogen_runtime_reports_legacy_openai_incompatibility(monkeypatch):
    class DummyGroupChat:
        def __init__(self, agents=None, messages=None, max_round=None):
            pass

    class DummyUserProxyAgent:
        pass

    dummy_autogen = SimpleNamespace(
        __version__="0.1.14",
        GroupChat=DummyGroupChat,
        UserProxyAgent=DummyUserProxyAgent,
        agentchat=SimpleNamespace(),
    )
    dummy_completion = SimpleNamespace(
        ERROR=ImportError("please install openai and diskcache to use the autogen.oai subpackage.")
    )

    def fake_import_module(name):
        if name == "autogen":
            return dummy_autogen
        if name == "autogen.oai.completion":
            return dummy_completion
        raise ModuleNotFoundError(name)

    monkeypatch.setattr(autogen_runtime.importlib, "import_module", fake_import_module)
    autogen_runtime.clear_autogen_runtime_status_cache()

    status = autogen_runtime.get_autogen_runtime_status()

    assert status.available is False
    assert "diskcache" in status.reason


def test_autogen_runtime_accepts_modern_groupchat_capabilities(monkeypatch):
    class DummyGroupChat:
        def __init__(self, agents=None, messages=None, max_round=None, speaker_selection_method=None):
            pass

    class DummyUserProxyAgent:
        async def a_initiate_chat(self, *args, **kwargs):
            return None

    dummy_autogen = SimpleNamespace(
        __version__="0.2.26",
        GroupChat=DummyGroupChat,
        UserProxyAgent=DummyUserProxyAgent,
        agentchat=SimpleNamespace(register_function=lambda *args, **kwargs: None),
    )

    def fake_import_module(name):
        if name == "autogen":
            return dummy_autogen
        raise ModuleNotFoundError(name)

    monkeypatch.setattr(autogen_runtime.importlib, "import_module", fake_import_module)
    autogen_runtime.clear_autogen_runtime_status_cache()

    status = autogen_runtime.get_autogen_runtime_status()

    assert status.available is True
    assert status.supports_register_function is True
    assert status.supports_speaker_selection is True
    assert status.supports_async_chat is True
