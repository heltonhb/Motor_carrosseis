"""
ics_export.py — Exporta cronograma para o formato .ics (Google Calendar/Apple/Outlook).

M5 do MELHORIAS.md: cronograma gerado pelo Gemini (semana_1/semana_2 com
dia, data, horario, conteudo_resumo, canal, cta) vira eventos de calendário
que podem ser importados com um clique.
"""

import re
from datetime import datetime, timedelta

# Fuso de São Paulo (UTC-3) fixo — o app é da unidade Tatuapé/SP.
# .ics exige offset explícito; -03:00 cobre o horário padrão de Brasília
# (o Brasil não tem mais horário de verão).
_OFFSET_SP = "-03:00"

_TIMESTAMP_FMT = "%Y%m%dT%H%M%S"


def _parse_data_hora(data_str: str, horario_str: str) -> datetime | None:
    """Tenta montar um datetime a partir dos campos do cronograma."""
    if not data_str:
        return None
    data_str = str(data_str).strip()
    horario_str = str(horario_str or "").strip()

    # Normaliza horário: "19:30", "19h30", "às 18h" → hora e minuto
    hor = None
    m = re.search(r"(\d{1,2})[:h](\d{2})", horario_str)
    if not m:
        m = re.search(r"(\d{1,2})h\b", horario_str)  # "18h" sem minutos
    if m:
        hh = int(m.group(1))
        mm = int(m.group(2)) if m.lastindex == 2 else 0
        if 0 <= hh <= 23 and 0 <= mm <= 59:
            hor = datetime(1900, 1, 1, hh, mm)

    # Datas: ISO primeiro, depois formatos comuns pt-BR (com ano explícito)
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            d = datetime.strptime(data_str, fmt)
            if hor:
                d = d.replace(hour=hor.hour, minute=hor.minute)
            return d
        except ValueError:
            continue

    # Dia da semana isolado ("segunda", "seg", "segunda-feira") → próxima ocorrência
    dias = {
        "seg": 0, "ter": 1, "qua": 2, "qui": 3,
        "sex": 4, "sab": 5, "dom": 6,
    }
    chave = data_str.lower()[:3]
    if chave in dias:
        hoje = datetime.now()
        alvo = dias[chave]
        delta = (alvo - hoje.weekday()) % 7 or 7
        d = hoje + timedelta(days=delta)
        if hor:
            d = d.replace(hour=hor.hour, minute=hor.minute)
        return d
    return None


def _escape_ics(texto: str) -> str:
    """Escapa caracteres especiais do formato .ics."""
    texto = str(texto or "")
    return (
        texto.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def _fold_line(linha: str) -> str:
    """Quebra linhas .ics em até 75 octets (RFC 5545), com continuação por espaço."""
    if len(linha.encode("utf-8")) <= 75:
        return linha
    parts = []
    atual = ""
    for ch in linha:
        if len((atual + ch).encode("utf-8")) > 74:
            parts.append(atual)
            atual = " " + ch  # continuação começa com espaço
        else:
            atual += ch
    parts.append(atual)
    return "\r\n".join(parts)


def cronograma_para_ics(cron: dict, titulo_base: str = "Post Instagram") -> tuple[str, int]:
    """
    Converte o cronograma (semana_1 + semana_2) em texto .ics.

    Campos usados por item: dia, data, horario, conteudo_resumo, canal, cta.
    Eventos com data irparseável são pulados (não entram no .ics).

    Retorna (texto_ics, nº_de_eventos_gerados).
    """
    now = datetime.now()
    stamp = now.strftime(_TIMESTAMP_FMT)

    linhas = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Ensina Mais Tatuape//Motor de Carrosseis//PT-BR",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        _fold_line(f"X-WR-CALNAME:{_escape_ics('Cronograma Instagram — Ensina Mais Tatuapé')}"),
    ]

    all_days = list(cron.get("semana_1", [])) + list(cron.get("semana_2", []))
    gerados = 0
    uid_n = 0

    for day in all_days:
        dt = _parse_data_hora(day.get("data", ""), day.get("horario", ""))
        if dt is None:
            continue
        uid_n += 1
        dtfim = dt + timedelta(hours=1)

        resumo = day.get("conteudo_resumo", "") or titulo_base
        canal = day.get("canal", "")
        cta = day.get("cta", "")
        descricao = f"Canal: {canal}" + (f"\nCTA: {cta}" if cta else "")

        linhas += [
            "BEGIN:VEVENT",
            _fold_line(f"UID:{_escape_ics(f'carrosseis-{stamp}-{uid_n}@ensinamais')}"),
            f"DTSTAMP:{now.strftime(_TIMESTAMP_FMT)}",
            f"DTSTART:{dt.strftime(_TIMESTAMP_FMT)}{_OFFSET_SP}",
            f"DTEND:{dtfim.strftime(_TIMESTAMP_FMT)}{_OFFSET_SP}",
            _fold_line(f"SUMMARY:{_escape_ics(resumo[:120])}"),
            _fold_line(f"DESCRIPTION:{_escape_ics(descricao)}"),
            "BEGIN:VALARM",
            "TRIGGER:-PT30M",
            "ACTION:DISPLAY",
            _fold_line(f"DESCRIPTION:{_escape_ics('Lembrete: publicar post Instagram')}"),
            "END:VALARM",
            "END:VEVENT",
        ]
        gerados += 1

    linhas.append("END:VCALENDAR")
    return "\r\n".join(linhas), gerados
