"""notebooklm_client.py — Cliente para interagir com NotebookLM via CLI."""

import json
import os
import re
import subprocess
import tempfile
import time
from typing import Optional


def _nlm_cmd(*args, profile: str = "default") -> list:
    """Monta comando notebooklm com profile."""
    cmd = ["notebooklm"]
    if profile and profile != "default":
        cmd.extend(["--profile", profile])
    cmd.extend(args)
    return cmd


def _run_cmd(cmd: list, timeout: int = 120) -> tuple:
    """Executa comando e retorna (stdout, stderr, returncode)."""
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


def get_notebook_info(notebook_id: str, profile: str = "default") -> dict:
    """Retorna informações de um notebook específico."""
    cmd = _nlm_cmd("use", notebook_id, profile=profile)
    _run_cmd(cmd)
    
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
    # Seleciona o notebook
    cmd_use = _nlm_cmd("use", notebook_id, profile=profile)
    _run_cmd(cmd_use)
    
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
    # Seleciona o notebook
    cmd_use = _nlm_cmd("use", notebook_id, profile=profile)
    _run_cmd(cmd_use)
    
    # Cria arquivo temporário com o prompt
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    ) as f:
        f.write(prompt)
        prompt_file = f.name
    
    try:
        # Executa a pergunta com streaming
        cmd = _nlm_cmd(
            "ask",
            "--prompt-file", prompt_file,
            "--stream",
            profile=profile,
        )
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        
        full_response = []
        for line in process.stdout:
            if line.strip():
                full_response.append(line.strip())
                if callback:
                    callback(line.strip())
        
        process.wait(timeout=300)
        
        if full_response:
            return "\n".join(full_response)
        
        return None
    finally:
        if os.path.exists(prompt_file):
            os.remove(prompt_file)


def search_in_notebook(
    notebook_id: str,
    query: str,
    profile: str = "default",
) -> Optional[str]:
    """
    Busca informações no notebook sobre um tema específico.
    
    Args:
        notebook_id: ID do notebook
        query: Termo ou frase para buscar
        profile: Perfil NotebookLM
    
    Returns:
        Resultados da busca ou None
    """
    prompt = f"""Baseado nas fontes deste notebook, responda sobre: {query}

Forneça uma resposta detalhada com:
1. Resumo do que foi encontrado
2. Dados específicos e estatísticas (se houver)
3. Tendências identificadas
4. Recomendações práticas

Seja específico e cite as fontes quando possível."""

    return ask_notebook(notebook_id, prompt, profile)


def get_trends(
    notebook_id: str,
    context: str = "educação infantil e reforço escolar",
    profile: str = "default",
) -> Optional[str]:
    """
    Busca tendências no notebook.
    
    Args:
        notebook_id: ID do notebook
        context: Contexto para busca de tendências
        profile: Perfil NotebookLM
    
    Returns:
        Tendências encontradas ou None
    """
    prompt = f"""Analise as fontes deste notebook e identifique TENDÊNCIAS atuais sobre {context}.

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

    return ask_notebook(notebook_id, prompt, profile)


def generate_ideas(
    notebook_id: str,
    trends: str = "",
    profile: str = "default",
) -> Optional[str]:
    """
    Gera ideias de carrossel baseadas no conteúdo do notebook.
    
    Args:
        notebook_id: ID do notebook
        trends: Tendências identificadas (opcional)
        profile: Perfil NotebookLM
    
    Returns:
        Ideias geradas ou None
    """
    context = f"\n\nTendências identificadas:\n{trends}" if trends else ""
    
    prompt = f"""Com base nas fontes deste notebook{context}, gere 6 IDEIAS DE CARROSSEL para o Instagram da Ensina Mais Tatuapé.

Cada ideia deve:
- Seguir um dos eixos: Didático (salvamentos), Comportamental (envios DM), Diagnóstico (leads)
- Incluir título chamativo, tema específico, público-alvo
- Sugerir 8 slides com textos curtos (30-50 palavras cada)
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

    return ask_notebook(notebook_id, prompt, profile)


def get_competitor_analysis(
    notebook_id: str,
    profile: str = "default",
) -> Optional[str]:
    """
    Analisa concorrentes baseado no conteúdo do notebook.
    
    Args:
        notebook_id: ID do notebook
        profile: Perfil NotebookLM
    
    Returns:
        Análise dos concorrentes ou None
    """
    prompt = """Analise as informações sobre concorrentes e mercado neste notebook.

Foque em:
1. O que outras escolas/institutos de reforço estão postando
2. Formatos de conteúdo que estão funcionando
3. Oportunidades que não estão sendo exploradas
4. Diferenciais da Ensina Mais Tatuapé vs concorrência

Retorne um JSON:
{{
  "concorrentes": [
    {{"nome": "...", "o_que_faz": "...", "pontos_fortes": "...", "pontos_fracos": "..."}}
  ],
  "oportunidades_mercado": [
    {{"oportunidade": "...", "acao_sugerida": "..."}}
  ],
  "diferenciais_ensina_mais": [
    {{"diferencial": "...", "como_explorar": "..."}}
  ]
}}"""

    return ask_notebook(notebook_id, prompt, profile)
