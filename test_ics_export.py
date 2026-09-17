"""
test_ics_export.py — Testes do exportador .ics (M5).

Cobre: datas ISO/pt-BR, horários com "h", dia da semana isolado,
escape de caracteres especiais, eventos sem data (pulados).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from ics_export import _escape_ics, _fold_line, _parse_data_hora, cronograma_para_ics

CRON = {
    "semana_1": [
        {"dia": "segunda", "data": "2026-09-21", "horario": "19:30",
         "conteudo_resumo": "Carrossel: 5 sinais de dificuldade em matemática",
         "canal": "Feed (Carrossel)", "cta": "DESAFIO"},
        {"dia": "quarta", "data": "23/09/2026", "horario": "às 18h",
         "conteudo_resumo": "Stories: bastidores da aula de robótica",
         "canal": "Stories", "cta": ""},
    ],
    "semana_2": [
        {"dia": "sexta", "data": "25/09/2026", "horario": "12h30",
         "conteudo_resumo": "Reel: transformação do aluno em 30 dias",
         "canal": "Reels", "cta": "DIAGNOSTICO"},
        {"dia": "sábado", "data": "sem data", "horario": "10:00",
         "conteudo_resumo": "Item inválido que deve ser pulado",
         "canal": "Stories", "cta": ""},
    ],
}


def test_parse_data_iso_com_horario():
    dt = _parse_data_hora("2026-09-21", "19:30")
    assert dt is not None
    assert (dt.year, dt.month, dt.day) == (2026, 9, 21)
    assert (dt.hour, dt.minute) == (19, 30)


def test_parse_data_ptbr_com_h():
    dt = _parse_data_hora("23/09/2026", "às 18h")
    assert dt is not None
    assert (dt.day, dt.month) == (23, 9)
    assert (dt.hour, dt.minute) == (18, 0)


def test_parse_hora_minuto_em_texto():
    dt = _parse_data_hora("25/09/2026", "12h30")
    assert dt is not None
    assert (dt.hour, dt.minute) == (12, 30)


def test_parse_dia_da_semana_isolado():
    dt = _parse_data_hora("segunda", "")
    assert dt is not None
    assert dt.weekday() == 0  # segunda


def test_parse_data_invalida():
    assert _parse_data_hora("sem data", "10:00") is None
    assert _parse_data_hora("", "") is None


def test_escape_ics():
    assert _escape_ics("a, b; c\nd") == "a\\, b\\; c\\nd"
    assert _escape_ics("bar\\") == "bar\\\\"


def test_fold_linha_longa():
    linha = "SUMMARY:" + "x" * 200
    dobrada = _fold_line(linha)
    linhas = dobrada.split("\r\n")
    assert len(linhas) > 1
    assert all(len(parte.encode("utf-8")) <= 75 for parte in linhas)
    # continuação começa com espaço
    assert linhas[1].startswith(" ")


def test_cronograma_para_ics_estrutura():
    ics, n = cronograma_para_ics(CRON)
    assert n == 3  # o 4º item ("sem data") é pulado
    assert ics.startswith("BEGIN:VCALENDAR")
    assert ics.endswith("END:VCALENDAR")
    assert ics.count("BEGIN:VEVENT") == 3
    assert "DTSTART:20260921T193000-03:00" in ics
    assert "DTSTART:20260923T180000-03:00" in ics
    # lembrete presente
    assert "TRIGGER:-PT30M" in ics
    # escape aplicado no resumo com vírgula
    assert "5 sinais de dificuldade" in ics


def test_cronograma_vazio():
    ics, n = cronograma_para_ics({})
    assert n == 0
    assert "BEGIN:VCALENDAR" in ics
    assert "BEGIN:VEVENT" not in ics
