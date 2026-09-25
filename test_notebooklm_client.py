"""Testes do notebooklm_client: limpeza de ruído do CLI e motivo de falha."""

import subprocess

import pytest

import notebooklm_client as nlm


@pytest.fixture(autouse=True)
def _reset_last_error(monkeypatch):
    monkeypatch.setattr(nlm, "last_error", "")


def test_limpar_resposta_remove_answer_e_new_conversation():
    raw = "Answer:\nPONG\n\nNew conversation: 5a60a124-b85d-4e61-978a-304d0f112686\n"
    assert nlm._limpar_resposta(raw) == "PONG"


def test_limpar_resposta_remove_continuing_conversation():
    raw = "Continuing conversation 5a60a124-b85d-4e61-978a-304d0f112686...\nAnswer:\nOi tudo bem\n"
    assert nlm._limpar_resposta(raw) == "Oi tudo bem"


def test_limpar_resposta_preserva_conteudo_multilinha():
    raw = "Answer:\nlinha1\nlinha2\n\nNew conversation: 5a60a124-b85d-4e61-978a-304d0f112686\n"
    assert nlm._limpar_resposta(raw) == "linha1\nlinha2"


def test_limpar_resposta_idempotente():
    raw = "Answer:\nPONG\n\nNew conversation: 5a60a124-b85d-4e61-978a-304d0f112686\n"
    limpa = nlm._limpar_resposta(raw)
    assert nlm._limpar_resposta(limpa) == limpa


def test_ask_notebook_sucesso_limpa_ruído(monkeypatch):
    monkeypatch.setattr(nlm, "_select_notebook", lambda *a, **k: True)
    stdout = "Answer:\nOK\n\nNew conversation: 5a60a124-b85d-4e61-978a-304d0f112686\n"
    monkeypatch.setattr(nlm, "_run_cmd", lambda *a, **k: (stdout, "", 0))
    assert nlm.ask_notebook("nb", "p") == "OK"
    assert nlm.last_error == ""


def test_ask_notebook_timeout_define_motivo(monkeypatch):
    monkeypatch.setattr(nlm, "_select_notebook", lambda *a, **k: True)
    monkeypatch.setattr(nlm, "_run_cmd", lambda *a, **k: ("", "Timeout", 1))
    assert nlm.ask_notebook("nb", "p", timeout=7) is None
    assert nlm.last_error == "timeout após 7s"


def test_ask_notebook_erro_cli_carrega_stderr(monkeypatch):
    monkeypatch.setattr(nlm, "_select_notebook", lambda *a, **k: True)
    monkeypatch.setattr(nlm, "_run_cmd", lambda *a, **k: ("", "erro de rede", 1))
    assert nlm.ask_notebook("nb", "p") is None
    assert "erro do CLI (exit 1)" in nlm.last_error
    assert "erro de rede" in nlm.last_error


def test_ask_notebook_resposta_vazia_define_motivo(monkeypatch):
    monkeypatch.setattr(nlm, "_select_notebook", lambda *a, **k: True)
    monkeypatch.setattr(nlm, "_run_cmd", lambda *a, **k: ("   ", "", 0))
    assert nlm.ask_notebook("nb", "p") is None
    assert nlm.last_error == "resposta vazia do CLI"


def test_select_notebook_falha_define_motivo(monkeypatch):
    monkeypatch.setattr(nlm, "_run_cmd", lambda *a, **k: ("", "notebook inexistente", 1))
    assert nlm._select_notebook("nb") is False
    assert "notebook inexistente" in nlm.last_error


def test_select_notebook_sucesso_limpa_erro(monkeypatch):
    monkeypatch.setattr(nlm, "_run_cmd", lambda *a, **k: ("", "", 0))
    assert nlm._select_notebook("nb") is True
    assert nlm.last_error == ""


class _FakePopen:
    def __init__(self, lines, returncode=0, stderr="", timeout_on_wait=False):
        self.stdout = iter(lines)
        self.stderr = _FakeStream(stderr)
        self.returncode = returncode
        self._timeout_on_wait = timeout_on_wait
        self._waits = 0

    def wait(self, timeout=None):
        self._waits += 1
        if self._timeout_on_wait and self._waits == 1:
            raise subprocess.TimeoutExpired(cmd="ask", timeout=timeout)
        return self.returncode

    def kill(self):
        pass


class _FakeStream:
    def __init__(self, data):
        self._data = data

    def read(self):
        return self._data


def test_streaming_sucesso_limpa_ruído(monkeypatch):
    monkeypatch.setattr(nlm, "_select_notebook", lambda *a, **k: True)
    monkeypatch.setattr(nlm, "_nlm_cmd", lambda *a, **k: ["notebooklm"])
    lines = ["Answer:\n", "OK\n", "\n", "New conversation: 5a60a124-b85d-4e61-978a-304d0f112686\n"]
    monkeypatch.setattr(
        nlm.subprocess, "Popen", lambda *a, **k: _FakePopen(lines, returncode=0)
    )
    assert nlm.ask_notebook_streaming("nb", "p") == "OK"
    assert nlm.last_error == ""


def test_streaming_falha_define_motivo(monkeypatch):
    monkeypatch.setattr(nlm, "_select_notebook", lambda *a, **k: True)
    monkeypatch.setattr(nlm, "_nlm_cmd", lambda *a, **k: ["notebooklm"])
    monkeypatch.setattr(
        nlm.subprocess,
        "Popen",
        lambda *a, **k: _FakePopen([], returncode=1, stderr="quota excedida"),
    )
    assert nlm.ask_notebook_streaming("nb", "p") is None
    assert "erro do CLI (exit 1)" in nlm.last_error
    assert "quota excedida" in nlm.last_error


def test_streaming_timeout_define_motivo(monkeypatch):
    monkeypatch.setattr(nlm, "_select_notebook", lambda *a, **k: True)
    monkeypatch.setattr(nlm, "_nlm_cmd", lambda *a, **k: ["notebooklm"])
    monkeypatch.setattr(
        nlm.subprocess,
        "Popen",
        lambda *a, **k: _FakePopen(["Answer:\n"], timeout_on_wait=True),
    )
    assert nlm.ask_notebook_streaming("nb", "p") is None
    assert nlm.last_error == "timeout após 300s"


def test_streaming_falha_selecao_retorna_none(monkeypatch):
    def _falha(*a, **k):
        nlm._set_error("falha ao selecionar o notebook")
        return False

    monkeypatch.setattr(nlm, "_select_notebook", _falha)
    assert nlm.ask_notebook_streaming("nb", "p") is None
    assert nlm.last_error == "falha ao selecionar o notebook"
