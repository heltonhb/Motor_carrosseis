"""notebooklm_client.py — Cliente para interagir com NotebookLM via CLI."""

import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from typing import Optional


# Prefixo de persona para nivelar qualidade dos prompts NLM com o Gemini direto
_PERSONA_PREFIX = (
    "Atue como a Carol, estrategista sênior de marketing digital "
    "da Ensina Mais Tatuapé (Rua Coelho Lisboa, 783). "
    "WhatsApp oficial: (11) 94475-0009. "
    "Público: pais de classes A/B do Tatuapé com filhos no Ensino Fundamental. "
    "NUNCA mencione personagens da Turma da Mônica.\n\n"
)


def _get_nlm_binary() -> Optional[str]:
    """
    Encontra o binário do notebooklm no sistema.
    Retorna None se não encontrado.
    """
    path = shutil.which("notebooklm")
    if path:
        return path
    for candidate in [
        "/home/helton/.local/bin/notebooklm",
        os.path.expanduser("~/.local/bin/notebooklm"),
        "/usr/local/bin/notebooklm",
        "/usr/bin/notebooklm",
    ]:
        if os.path.exists(candidate):
            return candidate
    return None  # binário não encontrado


def is_nlm_available() -> bool:
    """Retorna True se o CLI notebooklm estiver disponível no sistema."""
    return _get_nlm_binary() is not None


def check_auth() -> tuple[bool, str]:
    """
    Verifica se o CLI está autenticado com o NotebookLM.
    Retorna (autenticado, mensagem_de_status).
    """
    cmd = _nlm_cmd("auth", "check")
    stdout, stderr, code = _run_cmd(cmd)
    if code == 0:
        return True, stdout.strip() or "autenticado"
    return False, (stderr.strip() or "não autenticado")


def _nlm_cmd(*args, profile: str = "default") -> Optional[list]:
    """
    Monta comando notebooklm com profile e caminho absoluto.
    Retorna None se o binário não estiver disponível.
    """
    binary = _get_nlm_binary()
    if binary is None:
        return None
    cmd = [binary]
    if profile and profile != "default":
        cmd.extend(["--profile", profile])
    cmd.extend(args)
    return cmd


def _run_cmd(cmd: Optional[list], timeout: int = 120) -> tuple:
    """Executa comando e retorna (stdout, stderr, returncode)."""
    if cmd is None:
        return "", "notebooklm CLI não encontrado no sistema.", 1
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired:
        return "", "Timeout", 1
    except Exception as e:
        return "", str(e), 1


def list_notebooks(profile: str = "default") -> list:
    """Lista todos os notebooks disponíveis."""
    cmd = _nlm_cmd("list", "--json", profile=profile)
    stdout, stderr, code = _run_cmd(cmd)
    if code == 0:
        try:
            data = json.loads(stdout)
            return data.get("notebooks", [])
        except json.JSONDecodeError:
            pass
    return []


def _select_notebook(notebook_id: str, profile: str = "default") -> bool:
    """Seleciona o notebook via `use`. Retorna True em caso de sucesso."""
    cmd = _nlm_cmd("use", notebook_id, profile=profile)
    _, _, code = _run_cmd(cmd)
    return code == 0


def get_notebook_info(notebook_id: str, profile: str = "default") -> dict:
    """Retorna informações de um notebook específico."""
    if not _select_notebook(notebook_id, profile):
        return {}

    cmd = _nlm_cmd("status", "--json", profile=profile)
    stdout, stderr, code = _run_cmd(cmd)
    if code == 0:
        try:
            return json.loads(stdout)
        except json.JSONDecodeError:
            pass
    return {}


def ask_notebook(
    notebook_id: str,
    prompt: str,
    profile: str = "default",
    timeout: int = 300,
) -> Optional[str]:
    """
    Faz uma pergunta ao notebook e retorna a resposta.
    
    Args:
        notebook_id: ID do notebook
        prompt: Pergunta a ser feita
        profile: Perfil NotebookLM
        timeout: Timeout em segundos
    
    Returns:
        Resposta do notebook ou None em caso de erro
    """
    # Seleciona o notebook; se falhar, retorna None cedo
    if not _select_notebook(notebook_id, profile):
        return None

    # Cria arquivo temporário com o prompt
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    ) as f:
        f.write(prompt)
        prompt_file = f.name
    
    try:
        # Executa a pergunta
        cmd = _nlm_cmd(
            "ask",
            "--prompt-file", prompt_file,
            profile=profile,
        )
        stdout, stderr, code = _run_cmd(cmd, timeout=timeout)
        
        if code == 0 and stdout.strip():
            return stdout.strip()
        
        return None
    finally:
        # Remove arquivo temporário
        if os.path.exists(prompt_file):
            os.remove(prompt_file)


def ask_notebook_streaming(
    notebook_id: str,
    prompt: str,
    profile: str = "default",
    callback=None,
) -> Optional[str]:
    """
    Faz uma pergunta ao notebook com streaming de resposta.
    
    Args:
        notebook_id: ID do notebook
        prompt: Pergunta a ser feita
        profile: Perfil NotebookLM
        callback: Função chamada com cada chunk de texto
    
    Returns:
        Resposta completa do notebook ou None
    """
    # Seleciona o notebook; se falhar, retorna None cedo
    if not _select_notebook(notebook_id, profile):
        return None

    # Cria arquivo temporário com o prompt
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    ) as f:
        f.write(prompt)
        prompt_file = f.name
    
    try:
        # Executa a pergunta (sem flag --stream inválida)
        cmd = _nlm_cmd(
            "ask",
            "--prompt-file", prompt_file,
            profile=profile,
        )

        if cmd is None:
            return None

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        
        full_response = []
        for line in process.stdout:
            full_response.append(line)
            if callback and line.strip():
                callback(line)
        
        try:
            process.wait(timeout=300)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            return None
        
        if full_response:
            text = "".join(full_response).strip()
            # Remove ruídos do CLI do topo da resposta se presentes
            text = re.sub(r"^(?:Continuing|Resumed) conversation [a-f0-9-]+\.\.\.\s*", "", text, flags=re.MULTILINE)
            text = re.sub(r"^Answer:\s*", "", text, flags=re.MULTILINE)
            if text:
                return text.strip()
        
        stderr_output = process.stderr.read() if process.stderr else ""
        if stderr_output and stderr_output.strip():
            print("NLM stderr:", stderr_output.strip())
        
        return None
    finally:
        if os.path.exists(prompt_file):
            os.remove(prompt_file)


# ─── Prompt Builders (reutilizáveis por sync e streaming) ─────────────────────

def _build_search_prompt(query: str) -> str:
    """Prompt para busca livre no notebook."""
    return _PERSONA_PREFIX + f"""Baseado nas fontes deste notebook, responda sobre: {query}

Forneça uma resposta detalhada com:
1. Resumo do que foi encontrado
2. Dados específicos e estatísticas (se houver)
3. Tendências identificadas
4. Recomendações práticas

Seja específico e cite as fontes quando possível."""


def _build_trends_prompt(context: str = "educação infantil e reforço escolar") -> str:
    """Prompt para análise de tendências."""
    return _PERSONA_PREFIX + f"""Analise as fontes deste notebook e identifique TENDÊNCIAS atuais sobre {context}.

Foque em:
1. Tendências de conteúdo no Instagram para educação
2. Dores e necessidades de pais de alunos
3. Sazonalidade escolar e oportunidades
4. O que a concorrência está fazendo
5. Dados e estatísticas relevantes

Retorne um JSON com esta estrutura:
{{
  "tendencias": [
    {{"nome": "...", "descricao": "...", "potencial": "alto/médio/baixo"}}
  ],
  "dores_pais": [
    {{"dor": "...", "frequencia": "...", "oportunidade": "..."}}
  ],
  "oportunidades": [
    {{"oportunidade": "...", "acao_sugerida": "..."}}
  ],
  "dados_relevantes": [
    {{"dado": "...", "fonte": "..."}}
  ]
}}"""


def _build_ideas_prompt(trends: str = "") -> str:
    """Prompt para geração de ideias de carrossel."""
    context = f"\n\nTendências identificadas:\n{trends}" if trends else ""
    return _PERSONA_PREFIX + f"""Com base nas fontes deste notebook{context}, gere 6 IDEIAS DE CARROSSEL para o Instagram da Ensina Mais Tatuapé.
WhatsApp oficial da unidade: (11) 94475-0009

Cada ideia deve:
- Seguir um dos eixos: Didático (salvamentos), Comportamental (envios DM), Diagnóstico (leads)
- Incluir título chamativo, tema específico, público-alvo
- Sugerir 8 slides com textos curtos (30-50 palavras cada)
- O Slide 8 (CTA) DEVE conter a chamada com a palavra-chave e OBRIGATORIAMENTE o WhatsApp oficial da unidade: (11) 94475-0009
- Ter um CTA com palavra-chave para comentário
- Estar conectada com as fontes do notebook

Retorne JSON:
{{
  "ideias": [
    {{
      "titulo": "...",
      "eixo": "Didático/Comportamental/Diagnóstico",
      "tema": "...",
      "publico_alvo": "...",
      "cta": "PALAVRA_CHAVE",
      "slides_sugeridos": [
        {{"slide": 1, "tipo": "Capa", "texto": "..."}},
        ...
      ],
      "fonte_notebook": "Qual fonte do notebook inspirou esta ideia",
      "justificativa": "Por que esta ideia vai funcionar"
    }}
  ]
}}"""


def _build_competitor_prompt() -> str:
    """Prompt para análise de concorrentes."""
    return _PERSONA_PREFIX + """Analise as informações sobre concorrentes e mercado neste notebook.

Foque em:
1. O que outras escolas/institutos de reforço estão postando
2. Formatos de conteúdo que estão funcionando
3. Oportunidades que não estão sendo exploradas
4. Diferenciais da Ensina Mais Tatuapé vs concorrência

Retorne um JSON:
{
  "concorrentes": [
    {"nome": "...", "o_que_faz": "...", "pontos_fortes": "...", "pontos_fracos": "..."}
  ],
  "oportunidades_mercado": [
    {"oportunidade": "...", "acao_sugerida": "..."}
  ],
  "diferenciais_ensina_mais": [
    {"diferencial": "...", "como_explorar": "..."}
  ]
}"""


# ─── Funções de query (sync — compatibilidade com pipeline automático) ────────

def search_in_notebook(
    notebook_id: str,
    query: str,
    profile: str = "default",
) -> Optional[str]:
    """Busca informações no notebook sobre um tema específico."""
    return ask_notebook(notebook_id, _build_search_prompt(query), profile)


def get_trends(
    notebook_id: str,
    context: str = "educação infantil e reforço escolar",
    profile: str = "default",
) -> Optional[str]:
    """Busca tendências no notebook."""
    return ask_notebook(notebook_id, _build_trends_prompt(context), profile)


def generate_ideas(
    notebook_id: str,
    trends: str = "",
    profile: str = "default",
) -> Optional[str]:
    """Gera ideias de carrossel baseadas no conteúdo do notebook."""
    return ask_notebook(notebook_id, _build_ideas_prompt(trends), profile)


def get_competitor_analysis(
    notebook_id: str,
    profile: str = "default",
) -> Optional[str]:
    """Analisa concorrentes baseado no conteúdo do notebook."""
    return ask_notebook(notebook_id, _build_competitor_prompt(), profile)


# ─── Funções de query com streaming (para UI em tempo real) ───────────────────

def search_in_notebook_streaming(
    notebook_id: str,
    query: str,
    profile: str = "default",
    callback=None,
) -> Optional[str]:
    """Busca com streaming — callback recebe cada chunk de texto."""
    return ask_notebook_streaming(
        notebook_id, _build_search_prompt(query), profile, callback
    )


def get_trends_streaming(
    notebook_id: str,
    context: str = "educação infantil e reforço escolar",
    profile: str = "default",
    callback=None,
) -> Optional[str]:
    """Tendências com streaming — callback recebe cada chunk de texto."""
    return ask_notebook_streaming(
        notebook_id, _build_trends_prompt(context), profile, callback
    )


def generate_ideas_streaming(
    notebook_id: str,
    trends: str = "",
    profile: str = "default",
    callback=None,
) -> Optional[str]:
    """Ideias com streaming — callback recebe cada chunk de texto."""
    return ask_notebook_streaming(
        notebook_id, _build_ideas_prompt(trends), profile, callback
    )


def get_competitor_analysis_streaming(
    notebook_id: str,
    profile: str = "default",
    callback=None,
) -> Optional[str]:
    """Concorrência com streaming — callback recebe cada chunk de texto."""
    return ask_notebook_streaming(
        notebook_id, _build_competitor_prompt(), profile, callback
    )

