"""
persistence.py — Persistência local com backend JSON ou SQLite.

Substitui o armazenamento efêmero no st.session_state por dados persistentes
em disco, garantindo que métricas e histórico sobrevivam a reinicializações.
JSON continua sendo o padrão local. ``STORAGE_BACKEND=sqlite`` habilita o
backend SQLite e migra cada coleção JSON na primeira leitura.

Estrutura de arquivos:
    data/metricas.json          — histórico de métricas dos posts
    data/historico_geracoes.json — registro das gerações de conteúdo
    data/acervo/*.json          — carrosséis aprovados, com o DNA do que funciona
"""

import json
import os
from datetime import datetime
from typing import Any

from config import (
    BRIEF_FILE,
    DATA_DIR,
    HISTORICO_FILE,
    IDEIAS_ESTADO_FILE,
    METRICAS_FILE,
    SQLITE_FILE,
    STORYBOARD_FILE,
)
from sqlite_store import read_document, write_document

# Um registro por arquivo no backend JSON; um documento só no SQLite.
ACERVO_DIR = os.path.join(DATA_DIR, "acervo")

# ─── Setup ───────────────────────────────────────────────────────────────────

def ensure_data_dir() -> None:
    """Garante que o diretório de dados existe."""
    os.makedirs(DATA_DIR, exist_ok=True)


# ─── Operações genéricas ──────────────────────────────────────────────────────

def _use_sqlite() -> bool:
    """Retorna se o backend SQLite foi habilitado na configuração."""
    return os.getenv("STORAGE_BACKEND", "json").strip().lower() == "sqlite"


def _storage_key(filepath: str) -> str:
    """Usa o nome legado como chave estável no banco SQLite."""
    return os.path.basename(filepath)

def _read_json(filepath: str) -> Any:
    """Lê JSON ou documento SQLite, conforme ``STORAGE_BACKEND``."""
    if _use_sqlite():
        fallback = None
        if os.path.exists(filepath):
            try:
                with open(filepath, encoding="utf-8") as f:
                    fallback = json.load(f)
            except (json.JSONDecodeError, OSError):
                fallback = None
        return read_document(SQLITE_FILE, _storage_key(filepath), fallback)

    if not os.path.exists(filepath):
        return None
    try:
        with open(filepath, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _write_json(filepath: str, data: Any) -> bool:
    """
    Escreve dados em um arquivo JSON de forma atômica:
    escreve em .tmp primeiro, depois renomeia.
    Retorna True em caso de sucesso.
    """
    if _use_sqlite():
        return write_document(SQLITE_FILE, _storage_key(filepath), data)

    ensure_data_dir()
    tmp_path = filepath + ".tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, filepath)
        return True
    except OSError:
        # Remove o .tmp se a escrita falhou
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        return False


# ─── Métricas dos Posts ───────────────────────────────────────────────────────

def load_metricas() -> list[dict]:
    """Carrega o histórico de métricas do disco. Retorna lista vazia se não houver dados."""
    data = _read_json(METRICAS_FILE)
    if isinstance(data, list):
        return data
    return []


def _para_int(valor: Any, padrao: int = 0) -> int:
    """Converte valor de CSV/API para int (tolera '12', '12.0', '12,5')."""
    try:
        return int(float(str(valor).strip().replace(",", ".")))
    except (TypeError, ValueError):
        return padrao


def metrica_eh_valida(metrica: dict) -> bool:
    """
    Uma métrica só alimenta o feedback loop se tiver título e alcance > 0
    (entradas vazias deixam o loop morto em silêncio).
    """
    return bool(
        isinstance(metrica, dict)
        and str(metrica.get("titulo", "") or "").strip()
        and _para_int(metrica.get("alcance", 0)) > 0
    )


def normalizar_metrica(metrica: dict) -> dict:
    """
    Padroniza uma métrica crua (CSV/API/form): números como int,
    'envios' → 'envios_dm' e taxas calculadas quando ausentes
    (o feedback loop ranqueia por taxa_salvamentos/taxa_envios).
    """
    m = dict(metrica)
    for campo in ("alcance", "salvamentos", "envios", "envios_dm",
                  "nao_seguidores", "comentarios", "leads_whatsapp"):
        if campo in m:
            m[campo] = _para_int(m[campo])
    if "envios" in m:
        envios = m.pop("envios")
        m.setdefault("envios_dm", envios)
    alc = m.get("alcance", 0)
    if alc > 0:
        m.setdefault("taxa_salvamentos", round(m.get("salvamentos", 0) / alc * 100, 1))
        m.setdefault("taxa_envios", round((m.get("envios_dm", 0) or 0) / alc * 100, 1))
        m.setdefault("taxa_nao_seguidores", round((m.get("nao_seguidores", 0) or 0) / alc * 100, 1))
    else:
        for campo in ("taxa_salvamentos", "taxa_envios", "taxa_nao_seguidores"):
            m.setdefault(campo, 0.0)
    m.setdefault("data", "")
    m.setdefault("titulo", "")
    return m


def _chave_metrica(metrica: dict) -> tuple:
    """Identidade de uma métrica para deduplicar (reimportação de CSV/API)."""
    return (
        str(metrica.get("titulo", "")).strip().lower(),
        str(metrica.get("data", "")).strip(),
        metrica.get("alcance", 0),
        metrica.get("instagram_post_id"),
    )


def save_metrica(metrica: dict, permitir_duplicada: bool = False) -> bool:
    """
    Adiciona uma métrica ao histórico — com validação no gate:
    só entra linha com título E alcance > 0 (senão o feedback loop
    aprende com lixo). Duplicatas exatas (título+data+alcance+post_id)
    são ignoradas, salvo permitir_duplicada=True.

    Args:
        metrica: Dict cru (form/CSV/API) ou MetricaPost.to_dict()

    Returns:
        True se salvo com sucesso.
    """
    m = normalizar_metrica(metrica)
    if not metrica_eh_valida(m):
        return False
    historico = load_metricas()
    if not permitir_duplicada and any(_chave_metrica(h) == _chave_metrica(m) for h in historico):
        return False
    if "registrado_em" not in m:
        m["registrado_em"] = datetime.now().isoformat(timespec="seconds")
    historico.append(m)
    return _write_json(METRICAS_FILE, historico)


def importar_metricas(metricas: list[dict]) -> dict:
    """
    Importa um lote de métricas em UMA única escrita em disco
    (antes: uma reescrita do arquivo inteiro por linha do CSV).

    Valida cada linha (título + alcance > 0), normaliza e deduplica
    contra o histórico existente e dentro do próprio lote.

    Returns:
        {"importadas": int, "invalidas": int, "duplicadas": int}
    """
    historico = load_metricas()
    chaves = {_chave_metrica(h) for h in historico}
    importadas = invalidas = duplicadas = 0
    novas: list[dict] = []
    for bruta in metricas:
        m = normalizar_metrica(bruta)
        if not metrica_eh_valida(m):
            invalidas += 1
            continue
        chave = _chave_metrica(m)
        if chave in chaves:
            duplicadas += 1
            continue
        if "registrado_em" not in m:
            m["registrado_em"] = datetime.now().isoformat(timespec="seconds")
        chaves.add(chave)
        novas.append(m)
        importadas += 1
    if novas:
        historico.extend(novas)
        _write_json(METRICAS_FILE, historico)
    return {"importadas": importadas, "invalidas": invalidas, "duplicadas": duplicadas}


def limpar_metricas_vazias() -> int:
    """
    Remove do histórico as entradas que não alimentam o feedback loop
    (sem título ou com alcance 0). Retorna quantas foram removidas.
    """
    historico = load_metricas()
    uteis = [m for m in historico if metrica_eh_valida(m)]
    removidas = len(historico) - len(uteis)
    if removidas:
        _write_json(METRICAS_FILE, uteis)
    return removidas


def delete_metrica(index: int) -> bool:
    """Remove uma entrada do histórico pelo índice. Retorna True se bem-sucedido."""
    historico = load_metricas()
    if 0 <= index < len(historico):
        historico.pop(index)
        return _write_json(METRICAS_FILE, historico)
    return False


def clear_metricas() -> bool:
    """Apaga todo o histórico de métricas."""
    return _write_json(METRICAS_FILE, [])


# ─── Ciclo de Vida das Ideias ──────────────────────────────────────────────────


def load_ideias_estado() -> dict[str, dict]:
    """Carrega o estado de todas as ideias (status, legenda associada, etc.)."""
    data = _read_json(IDEIAS_ESTADO_FILE)
    if isinstance(data, dict):
        return data
    return {}


def update_idea_status(
    idea_id: str,
    status: str,
    legenda_texto: str | None = None,
    data_publicacao: str | None = None,
    titulo: str | None = None,
) -> bool:
    """
    Atualiza o status de uma ideia (rascunho → aprovado → agendado → publicado).
    Também pode associar a legenda usada e data de publicação.
    """
    if status not in {"rascunho", "aprovado", "agendado", "publicado"}:
        return False

    estados = load_ideias_estado()
    if idea_id not in estados:
        estados[idea_id] = {"id": idea_id, "titulo": titulo or ""}
    elif titulo:
        estados[idea_id]["titulo"] = titulo

    estados[idea_id]["status"] = status
    if legenda_texto is not None:
        estados[idea_id]["legenda_texto"] = legenda_texto
    if data_publicacao is not None:
        estados[idea_id]["data_publicacao"] = data_publicacao

    return _write_json(IDEIAS_ESTADO_FILE, estados)


# ─── Brief / Storyboard ──────────────────────────────────────────────────────
#
# O brief é a resposta às lacunas que o modelo deixaria em aberto (para quem,
# com que objetivo, em que voz, com que aparência). O storyboard é o mesmo
# contrato visto no tempo: cada slide com papel, duração e cue.
#
# Ambos são um por vez, sobrescritos — são estado de trabalho, não histórico.


def salvar_brief(brief: dict) -> bool:
    """Grava o brief atual em data/brief.json."""
    ensure_data_dir()
    brief = dict(brief)
    brief.setdefault("atualizado_em", datetime.now().isoformat(timespec="seconds"))
    return _write_json(BRIEF_FILE, brief)


def carregar_brief() -> dict | None:
    """Lê o brief atual, ou None se ainda não houver."""
    data = _read_json(BRIEF_FILE)
    return data if isinstance(data, dict) else None


def salvar_storyboard(storyboard: dict) -> bool:
    """Grava o storyboard atual em data/storyboard.json."""
    ensure_data_dir()
    storyboard = dict(storyboard)
    storyboard.setdefault("atualizado_em", datetime.now().isoformat(timespec="seconds"))
    return _write_json(STORYBOARD_FILE, storyboard)


def carregar_storyboard() -> dict | None:
    """Lê o storyboard atual, ou None se ainda não houver."""
    data = _read_json(STORYBOARD_FILE)
    return data if isinstance(data, dict) else None


# ─── Acervo (carrosséis aprovados) ────────────────────────────────────────────
#
# O acervo é o nível 7 do motor: o conjunto do que a unidade aprovou, destilado
# em DNA reaproveitável. Ele não guarda rascunho — guarda o padrão do que
# funcionou, para as próximas gerações nascerem parecidas.
#
# Regra dura: só entra por promoção explícita (status "publicado" + métrica no
# alvo do eixo). Acervo com rascunho ruim é pior que acervo vazio, porque o
# motor passa a copiar o erro com confiança.


def _acervo_path(slug: str) -> str:
    """Caminho do registro de um slug do acervo."""
    return os.path.join(ACERVO_DIR, f"{slug}.json")


def load_acervo() -> list[dict]:
    """
    Carrega todos os registros do acervo, do mais recente para o mais antigo.

    Um arquivo corrompido não derruba a leitura do acervo inteiro: ele é
    ignorado. Perder um registro é melhor do que perder o aprendizado todo.
    """
    if not os.path.isdir(ACERVO_DIR):
        return []

    registros: list[dict] = []
    for nome in os.listdir(ACERVO_DIR):
        if not nome.endswith(".json"):
            continue
        try:
            with open(os.path.join(ACERVO_DIR, nome), encoding="utf-8") as f:
                registro = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(registro, dict):
            registros.append(registro)

    registros.sort(key=lambda r: r.get("aprovado_em", ""), reverse=True)
    return registros


def get_acervo(slug: str) -> dict | None:
    """Lê um registro específico do acervo."""
    data = _read_json(_acervo_path(slug))
    return data if isinstance(data, dict) else None


def save_acervo(registro: dict) -> bool:
    """
    Salva (ou sobrescreve) um registro do acervo.

    O slug precisa existir no registro — sem ele não há como achar o arquivo
    depois.
    """
    slug = (registro.get("slug") or "").strip()
    if not slug:
        return False
    if _use_sqlite():
        # No backend SQLite o acervo é um documento só: chave estável, todos os
        # registros dentro. Mesmo formato de leitura para o chamador.
        todos = {r.get("slug"): r for r in load_acervo() if r.get("slug")}
        todos[slug] = registro
        return _write_json(os.path.join(DATA_DIR, "acervo.json"), list(todos.values()))
    # ensure_data_dir() cria data/ mas não data/acervo/: sem este makedirs a
    # primeira promoção falhava em silêncio e devolvia False.
    os.makedirs(ACERVO_DIR, exist_ok=True)
    return _write_json(_acervo_path(slug), registro)


def remover_acervo(slug: str) -> bool:
    """Remove um registro do acervo. Verdadeiro se havia algo para remover."""
    if _use_sqlite():
        restantes = [r for r in load_acervo() if r.get("slug") != slug]
        return _write_json(os.path.join(DATA_DIR, "acervo.json"), restantes)
    caminho = _acervo_path(slug)
    if not os.path.exists(caminho):
        return False
    try:
        os.remove(caminho)
        return True
    except OSError:
        return False


# ─── Histórico de Gerações ────────────────────────────────────────────────────

def load_historico_geracoes() -> list[dict]:
    """Carrega o histórico de gerações de conteúdo. Retorna lista vazia se não houver."""
    data = _read_json(HISTORICO_FILE)
    if isinstance(data, list):
        return data
    return []


def save_geracao(tipo: str, dados: dict) -> bool:
    """
    Registra uma geração de conteúdo (tendências, ideias, prompts, cronograma).

    Args:
        tipo:  "tendencias" | "ideias" | "prompts" | "cronograma" | "legendas"
        dados: O dict retornado pelo Gemini para aquela geração.

    Returns:
        True se salvo com sucesso.
    """
    historico = load_historico_geracoes()
    entrada = {
        "tipo": tipo,
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
        "dados": dados,
    }
    historico.append(entrada)
    # Mantém apenas as 50 gerações mais recentes para não crescer indefinidamente
    if len(historico) > 50:
        historico = historico[-50:]
    return _write_json(HISTORICO_FILE, historico)


def load_ultima_geracao(tipo: str) -> dict | None:
    """
    Retorna os dados da geração mais recente de um tipo específico,
    ou None se não houver nenhuma salva.
    """
    historico = load_historico_geracoes()
    for entrada in reversed(historico):
        if entrada.get("tipo") == tipo:
            return entrada.get("dados")
    return None


# ─── Sincronização com session_state ─────────────────────────────────────────

def sync_session_from_disk(session_state: dict) -> None:
    """
    Carrega dados do disco para o session_state no início da sessão,
    restaurando métricas e última geração de cada tipo.
    Chamado uma vez em app.py no startup.
    """
    # Métricas
    metricas = load_metricas()
    if metricas and "historico_metricas" not in session_state:
        session_state["historico_metricas"] = metricas

    # Última geração de cada tipo. Prompts e legendas são listas na UI, para
    # preservar mais de uma geração na mesma sessão.
    for tipo, session_key in (
        ("tendencias", "tendencias"),
        ("ideias", "ideias"),
        ("cronograma", "cronograma"),
        ("video_curto", "video_curto"),
    ):
        if session_key not in session_state:
            dados = load_ultima_geracao(tipo)
            if dados:
                session_state[session_key] = dados

    if "prompts_lote" not in session_state:
        dados = load_ultima_geracao("prompts")
        if dados:
            session_state["prompts_lote"] = [dados]

    if "legendas_lote" not in session_state:
        dados = load_ultima_geracao("legendas")
        if dados:
            session_state["legendas_lote"] = [dados]
