"""
tabs/tab_notebooklm.py — Aba NotebookLM.

Mudanças P1-3: Pipeline paralelizado (prompts + legendas em paralelo).
"""

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import streamlit as st

import notebooklm_client as nlm
from batch_engine import gerar_cronograma, gerar_legendas_ideia, gerar_prompts_ideia
from config import NOTEBOOK_ID_PADRAO, NOTEBOOK_TITULO_PADRAO
from gemini import call_gemini, call_gemini_json
from parser_nlm import extract_ideas_from_text, extract_json
from persistence import save_geracao
from prompts import PROMPT_TENDENCIAS, TEMPERATURAS, get_prompt_ideias
from tabs._ui import api_key_ok


def _format_ideia(ideia: dict) -> dict:
    """Normaliza uma ideia para o schema único compartilhado entre abas."""
    return {
        "id": ideia.get("id", ""),
        "titulo": ideia.get("titulo", ""),
        "eixo": ideia.get("eixo", "Didático"),
        "curso": ideia.get("curso", ""),
        "persona_alvo": ideia.get("persona_alvo", ""),
        "tipo_hook": ideia.get("tipo_hook", ""),
        "tema": ideia.get("tema", ""),
        "publico_alvo": ideia.get("publico_alvo", "Pais de classes A/B do Tatuapé"),
        "palavras_chave_seo": ideia.get("palavras_chave_seo", ["apoio escolar Tatuapé", "reforço escolar Tatuapé"]),
        "cta": ideia.get("cta", "DESAFIO"),
        "slides_sugeridos": ideia.get("slides_sugeridos", []),
        "kpi_alvo": ideia.get("kpi_alvo", ""),
        "justificativa": ideia.get("justificativa", ideia.get("fonte_notebook", "")),
        "fonte_notebook": ideia.get("fonte_notebook", ""),
        "score": ideia.get("score", 0),
        "score_justificativa": ideia.get("score_justificativa", ""),
    }


def render():
    """Renderiza a aba NotebookLM."""
    st.markdown("## 🔬 NotebookLM — Motor de Tendências e Ideias")
    st.markdown("Consulte notebooks existentes no NotebookLM para buscar tendências e gerar ideias baseadas em fontes reais.")

    if not nlm.is_nlm_available():
        st.error(
            "❌ CLI `notebooklm` não encontrado no sistema. \n"
            "Instale com: `pip install google-notebooklm-cli`\n"
            "Ou siga o guia em: https://github.com/googlegoogle/notebooklm-cli\n"
            "As outras abas do app funcionam normalmente via Gemini."
        )
        authenticated = False
    else:
        notebooks = []
        authenticated, auth_msg = nlm.check_auth()
        if authenticated:
            try:
                notebooks = nlm.list_notebooks()
            except Exception as exc:
                st.exception(exc)
                notebooks = []
        else:
            st.error(f"❌ NotebookLM não autenticado ({auth_msg}). Execute: `notebooklm login`")

    if not authenticated:
        return

    # Seletor de notebook
    notebook_options = {}
    for nb in notebooks:
        nb_id = nb.get("id") or nb.get("notebook_id")
        nb_title = nb.get("title") or nb.get("name") or nb_id
        if nb_id:
            notebook_options[str(nb_id)] = nb_title

    if notebook_options:
        if NOTEBOOK_ID_PADRAO not in notebook_options:
            notebook_options[NOTEBOOK_ID_PADRAO] = NOTEBOOK_TITULO_PADRAO
        selected_nb_id = st.selectbox(
            "📚 Notebook de origem:",
            options=list(notebook_options.keys()),
            format_func=lambda x: notebook_options[x],
            index=list(notebook_options.keys()).index(NOTEBOOK_ID_PADRAO)
            if NOTEBOOK_ID_PADRAO in notebook_options
            else 0,
        )
        notebook_titulo = notebook_options[selected_nb_id]
    else:
        selected_nb_id = NOTEBOOK_ID_PADRAO
        notebook_titulo = NOTEBOOK_TITULO_PADRAO
        st.warning(
            "⚠️ Nenhum notebook foi listado. Usando o notebook padrão configurado. "
            "Verifique se há notebooks disponíveis na sua conta."
        )

    st.session_state["_nb_active_id"] = selected_nb_id

    with st.sidebar:
        st.markdown("---")
        st.markdown("## 🔬 NotebookLM")
        st.markdown("**Notebook ativo:**")
        st.info(f"📚 {notebook_titulo}")
        st.caption(f"ID: {selected_nb_id[:12]}...")

    # ══════════════════════════════════════════════════════════════════════
    # PIPELINE AUTOMÁTICO (P1-3: paralelizado)
    # ══════════════════════════════════════════════════════════════════════
    st.markdown("### 🚀 Pipeline Automático")
    st.markdown(
        "Executa todo o fluxo de uma vez: **NotebookLM pesquisa** → "
        "**Gemini estrutura** → Tendências + Ideias + Prompts + Legendas + Cronograma"
    )

    pip_col1, pip_col2, pip_col3 = st.columns(3)
    with pip_col1:
        pip_prompts = st.checkbox("🎨 Gerar Prompts de Imagem", value=True, key="pip_prompts")
    with pip_col2:
        pip_legendas = st.checkbox("📝 Gerar Legendas", value=True, key="pip_legendas")
    with pip_col3:
        pip_cronograma = st.checkbox("📅 Gerar Cronograma", value=True, key="pip_cron")

    if st.button("🚀 Executar Pipeline Completo", type="primary", width="stretch", key="btn_pipeline"):
        if not api_key_ok():
            st.warning("⚠️ Configure a chave API Gemini na barra lateral.")
        else:
            total_steps = 2
            if pip_cronograma:
                total_steps += 1
            if pip_prompts or pip_legendas:
                total_steps += 1  # paralelo conta como 1

            progress = st.progress(0)
            status = st.empty()
            step = 0
            pipeline_ok = True

            # ── Etapa 1: Pesquisa no NotebookLM ──────────────────────────
            status.info(f"📚 **[1/{total_steps}]** Pesquisando tendências no NotebookLM…")
            nlm_context = ""
            try:
                nlm_trends = nlm.get_trends(selected_nb_id)
                nlm_competitor = nlm.get_competitor_analysis(selected_nb_id)
                nlm_context_parts = []
                if nlm_trends:
                    nlm_context_parts.append(f"=== TENDÊNCIAS (fonte: NotebookLM) ===\n{nlm_trends}")
                if nlm_competitor:
                    nlm_context_parts.append(f"=== CONCORRÊNCIA (fonte: NotebookLM) ===\n{nlm_competitor}")
                nlm_context = "\n\n".join(nlm_context_parts)
            except Exception as e:
                st.warning(f"⚠️ NotebookLM indisponível ({str(e)[:80]}). Continuando com Gemini…")

            if nlm_context:
                trends_data = call_gemini_json(
                    PROMPT_TENDENCIAS,
                    f"Contexto pesquisado em fontes reais (NotebookLM):\n{nlm_context}",
                    temperature=TEMPERATURAS["tendencias"],
                )
            else:
                trends_data = call_gemini_json(PROMPT_TENDENCIAS, temperature=TEMPERATURAS["tendencias"])

            from tabs.tab_tendencias import _normalizar_tendencias
            trends_data = _normalizar_tendencias(trends_data)

            if trends_data:
                st.session_state["tendencias"] = trends_data
                st.session_state["tendencias_texto"] = json.dumps(trends_data, ensure_ascii=False)
                save_geracao("tendencias", trends_data)
            else:
                pipeline_ok = False

            step += 1
            progress.progress(step / total_steps)

            # ── Etapa 2: Gerar Ideias via Gemini ─────────────────────────
            ideias_formatadas = []
            if pipeline_ok:
                status.info(f"💡 **[{step + 1}/{total_steps}]** Gerando 6 ideias estratégicas…")
                ideas_context = f"Tendências:\n{json.dumps(trends_data, ensure_ascii=False)}"
                if nlm_context:
                    ideas_context += f"\n\nPesquisa NotebookLM:\n{nlm_context[:3000]}"

                ideas_data = call_gemini_json(get_prompt_ideias(), ideas_context, temperature=TEMPERATURAS["ideias"])

                if ideas_data and isinstance(ideas_data.get("ideias"), list) and ideas_data["ideias"]:
                    st.session_state["ideias"] = ideas_data
                    save_geracao("ideias", ideas_data)

                    ideias_formatadas = [_format_ideia(i) for i in ideas_data["ideias"]]
                    # P0-2: auto-selecionar
                    st.session_state["ideias_selecionadas"] = ideias_formatadas
                    total_steps = 2 + int(pip_cronograma) + 1  # +1 para paralelo
                else:
                    pipeline_ok = False

            step += 1
            progress.progress(step / total_steps)

            pipeline_warnings = []

            # ── P1-3: Prompts + Legendas em PARALELO ─────────────────────
            if pipeline_ok and (pip_prompts or pip_legendas):
                status.info(f"🎨📝 **[{step + 1}/{total_steps}]** Gerando prompts e legendas em paralelo…")

                def _gen_prompts(ideia):
                    avisos_pip: list = []
                    corrigidos_pip: list = []
                    dados = gerar_prompts_ideia(ideia, forcar=True, avisos=avisos_pip, corrigidos=corrigidos_pip)
                    titulo = ideia.get("titulo", "Ideia")
                    if dados:
                        return {"tipo": "prompts", "titulo": titulo, "dados": dados, "ideia": ideia, "avisos": avisos_pip, "corrigidos": corrigidos_pip}
                    return {"tipo": "prompts", "titulo": titulo, "erro": True}

                def _gen_legendas(ideia):
                    dados = gerar_legendas_ideia(ideia, forcar=True)
                    titulo = ideia.get("titulo", "Ideia")
                    if dados:
                        return {"tipo": "legendas", "titulo": titulo, "dados": dados, "ideia": ideia}
                    return {"tipo": "legendas", "titulo": titulo, "erro": True}

                tarefas = []
                if pip_prompts:
                    tarefas.extend([(_gen_prompts, i) for i in ideias_formatadas])
                if pip_legendas:
                    tarefas.extend([(_gen_legendas, i) for i in ideias_formatadas])

                with ThreadPoolExecutor(max_workers=min(len(tarefas), 4)) as executor:
                    futures = {executor.submit(fn, ideia): (fn, ideia) for fn, ideia in tarefas}
                    for future in as_completed(futures):
                        resultado = future.result()
                        if resultado["erro"]:
                            pipeline_warnings.append(f"{resultado['titulo']}: {resultado['tipo']} não gerados")
                            continue
                        if resultado["tipo"] == "prompts":
                            item = {
                                "titulo": resultado["titulo"],
                                "prompts": resultado["dados"],
                                "ideia": resultado["ideia"],
                                "avisos": resultado["avisos"],
                                "corrigidos": resultado["corrigidos"],
                            }
                            st.session_state.setdefault("prompts_lote", []).append(item)
                            save_geracao("prompts", item)
                            if resultado["avisos"]:
                                pipeline_warnings.append(
                                    f"{resultado['titulo']}: {len(resultado['avisos'])} aviso(s) nos prompts"
                                )
                        elif resultado["tipo"] == "legendas":
                            item = {
                                **resultado["dados"],
                                "titulo": resultado["titulo"],
                                "ideia": resultado["ideia"],
                            }
                            st.session_state.setdefault("legendas_lote", []).append(item)
                            save_geracao("legendas", item)

                step += 1
                progress.progress(step / total_steps)

            # ── Etapa: Cronograma ────────────────────────────────────────
            if pipeline_ok and pip_cronograma:
                status.info(f"📅 **[{step + 1}/{total_steps}]** Montando cronograma de 2 semanas…")
                cron_data = gerar_cronograma(ideias_formatadas, forcar=True)
                if cron_data:
                    st.session_state["cronograma"] = cron_data
                    save_geracao("cronograma", cron_data)

                step += 1
                progress.progress(step / total_steps)

            # ── Resultado Final ──────────────────────────────────────────
            progress.progress(1.0)
            if pipeline_ok:
                status.empty()
                st.success("✅ **Pipeline concluído!** Todas as ideias foram processadas:")
                for warning in pipeline_warnings:
                    st.warning(f"⚠️ {warning}")
                result_cols = st.columns(5)
                tabs_populated = ["📈 Tendências", "💡 Ideias"]
                if pip_prompts:
                    tabs_populated.append("🎨 Prompts")
                if pip_legendas:
                    tabs_populated.append("📝 Legendas")
                if pip_cronograma:
                    tabs_populated.append("📅 Cronograma")
                for i, tab_name in enumerate(tabs_populated):
                    with result_cols[i % 5]:
                        st.info(f"✅ {tab_name}")

                n_ideias = len(ideias_formatadas)
                st.markdown(
                    f"**{n_ideias} ideias** geradas e selecionadas. "
                    f"Navegue pelas tabs acima para ver os detalhes."
                )
                if nlm_context:
                    with st.expander("📚 Contexto usado do NotebookLM"):
                        st.markdown(nlm_context[:2000])
                        if len(nlm_context) > 2000:
                            st.caption(f"… {len(nlm_context) - 2000} caracteres adicionais omitidos")
            else:
                status.empty()
                st.error("❌ Pipeline interrompido. Verifique a chave API e tente novamente.")

    st.divider()

    # ══════════════════════════════════════════════════════════════════════
    # CONSULTA MANUAL
    # ══════════════════════════════════════════════════════════════════════
    st.markdown("### 🔍 Consulta Manual")

    col1, col2 = st.columns(2)
    with col1:
        consulta_tipo = st.radio(
            "O que deseja buscar:",
            ["📈 Tendências do Setor", "💡 Ideias de Carrossel", "🏢 Análise de Concorrência", "❓ Pergunta Livre"],
            key="nb_consulta_tipo"
        )

    with col2:
        if consulta_tipo == "❓ Pergunta Livre":
            pergunta_livre = st.text_area(
                "Digite sua pergunta:",
                placeholder="Ex: Quais são as maiores dúvidas de pais sobre frações?",
                key="nb_pergunta_livre"
            )

    if st.button("🔍 Buscar no NotebookLM", type="primary", width="stretch"):
        if not selected_nb_id:
            st.warning("⚠️ Selecione um notebook primeiro.")
        else:
            response_container = st.empty()
            streaming_chunks = []
            _last_render = [0.0]

            def on_chunk(chunk):
                streaming_chunks.append(chunk)
                now = time.time()
                if now - _last_render[0] >= 0.33:
                    _last_render[0] = now
                    partial = "".join(streaming_chunks)
                    response_container.markdown(partial + " ▌")

            consulta_config = {
                "📈 Tendências do Setor": {
                    "prompt_builder": nlm._build_trends_prompt,
                    "args": {"context": "educação infantil e reforço escolar"},
                    "result_key": "tendencias",
                    "tab_name": "📈 Tendências"
                },
                "💡 Ideias de Carrossel": {
                    "prompt_builder": nlm._build_ideas_prompt,
                    "args": {},
                    "result_key": "ideias",
                    "tab_name": "💡 Ideias"
                },
                "🏢 Análise de Concorrência": {
                    "prompt_builder": nlm._build_competitor_prompt,
                    "args": {},
                    "result_key": "concorrentes",
                    "tab_name": "🏢 Análise de Concorrência"
                },
                "❓ Pergunta Livre": {
                    "prompt_builder": nlm._build_search_prompt,
                    "args": {},
                    "result_key": None,
                    "tab_name": "🔍 Consulta Livre"
                }
            }

            with st.status("🔍 Consultando NotebookLM…", expanded=True) as status_ctx:
                config = consulta_config[consulta_tipo]
                prompt_args = config["args"].copy()
                if consulta_tipo == "❓ Pergunta Livre":
                    pergunta_texto = st.session_state.get("nb_pergunta_livre", "").strip()
                    if not pergunta_texto:
                        st.warning("⚠️ Digite uma pergunta para consultar o notebook.")
                        result = None
                    else:
                        prompt_args["query"] = pergunta_texto
                        result = None
                else:
                    result = None

                if result is None:
                    prompt = config["prompt_builder"](**prompt_args)
                    result = nlm.ask_notebook_streaming(selected_nb_id, prompt, callback=on_chunk)
                    if not result:
                        result = nlm.ask_notebook(selected_nb_id, prompt)

                if not result:
                    motivo = (getattr(nlm, "last_error", "") or "sem resposta").strip()
                    if api_key_ok() and consulta_tipo in ("📈 Tendências do Setor", "💡 Ideias de Carrossel"):
                        tb = {
                            "📈 Tendências do Setor": PROMPT_TENDENCIAS,
                            "💡 Ideias de Carrossel": get_prompt_ideias(),
                        }
                        status_ctx.write(f"⚠️ NotebookLM indisponível ({motivo}). Usando Gemini como fallback…")
                        result = call_gemini(tb[consulta_tipo])
                    else:
                        status_ctx.update(label=f"❌ Falha na consulta: {motivo}", state="error")

                if result:
                    status_ctx.update(label="✅ Consulta concluída", state="complete")

            response_container.empty()

            if result:
                st.session_state["nb_result"] = result
                data_parsed = extract_json(result)
                if not data_parsed:
                    try:
                        data_parsed = json.loads(result)
                    except Exception:
                        data_parsed = {}

                if config.get("result_key") == "ideias" or consulta_tipo == "💡 Ideias de Carrossel":
                    if "ideias" not in data_parsed:
                        ideias_extraidas = extract_ideas_from_text(result)
                        if ideias_extraidas:
                            data_parsed["ideias"] = ideias_extraidas

                if config["result_key"] and isinstance(data_parsed, dict) and config["result_key"] in data_parsed:
                    key_data = data_parsed[config["result_key"]]

                    if config["result_key"] == "ideias":
                        ideias_list = key_data
                        ideias_formatadas = [_format_ideia(i) for i in ideias_list]
                        from tabs.tab_ideias import _ensure_idea_ids
                        _ensure_idea_ids(ideias_formatadas, "notebooklm")
                        st.session_state["ideias"] = {"ideias": ideias_formatadas}
                        # P0-2: auto-selecionar
                        st.session_state["ideias_selecionadas"] = ideias_formatadas
                        save_geracao("ideias", {"ideias": ideias_formatadas})
                        st.success(f"✅ Consulta concluída! {len(ideias_formatadas)} ideias enviadas para a aba '{config['tab_name']}'.")

                    elif config["result_key"] == "tendencias":
                        from tabs.tab_tendencias import _normalizar_tendencias
                        st.session_state["tendencias"] = _normalizar_tendencias(key_data)
                        st.session_state["tendencias_texto"] = json.dumps(key_data, ensure_ascii=False)
                        save_geracao("tendencias", key_data)
                        st.success(f"✅ Consulta concluída! Dados enviados para a aba '{config['tab_name']}'.")
                    else:
                        st.session_state[config["result_key"]] = key_data
                        save_geracao(config["result_key"], key_data)
                        st.success(f"✅ Consulta concluída! Dados enviados para a aba '{config['tab_name']}'.")
                else:
                    st.success("✅ Consulta concluída!")
            elif consulta_tipo != "❓ Pergunta Livre" or st.session_state.get("nb_pergunta_livre", "").strip():
                st.error("❌ Não foi possível obter resposta do notebook.")
                st.info("💡 Dica: Verifique se a sua sessão do NotebookLM precisa ser renovada executando `notebooklm login` no terminal, ou tente a opção '📈 Tendências do Setor'.")

    # Exibir resultado
    if "nb_result" in st.session_state and st.session_state["nb_result"]:
        result = st.session_state["nb_result"]
        data = extract_json(result)
        if not data:
            try:
                data = json.loads(result)
            except Exception:
                data = {}

        if "ideias" not in data:
            ideias_extraidas = extract_ideas_from_text(result)
            if ideias_extraidas:
                data["ideias"] = ideias_extraidas

        if data:
            if "tendencias" in data:
                from tabs.tab_tendencias import _normalizar_tendencias
                st.markdown("### 📈 Tendências Identificadas")
                for t in data["tendencias"]:
                    potencial = t.get("potencial", "médio")
                    from config import CORES
                    cor = CORES["secundaria"] if potencial == "alto" else CORES["destaque"] if potencial == "médio" else CORES["texto_sec"]
                    from tabs._ui import esc
                    st.markdown(f"""
                    <div class="metric-box">
                        <strong style="color:{cor};">{esc(t.get('nome', ''))}</strong>
                        <span style="color:{CORES['texto_sec']}; font-size:0.82em;">[{esc(potencial)}]</span>
                        <br><span style="color:{CORES['texto']}; font-size:0.88em;">{esc(t.get('descricao', ''))}</span>
                    </div>
                    """, unsafe_allow_html=True)

            if "dores_pais" in data:
                st.markdown("### 😰 Dores dos Pais")
                for d in data["dores_pais"]:
                    with st.expander(f"💔 {d.get('dor', '')}"):
                        st.markdown(f"**Frequência:** {d.get('frequencia', '')}")
                        st.markdown(f"**Oportunidade:** {d.get('oportunidade', '')}")

            if "oportunidades" in data:
                st.markdown("### 🎯 Oportunidades")
                for o in data["oportunidades"]:
                    st.success(f"**{o.get('oportunidade', '')}** → {o.get('acao_sugerida', '')}")

            if "ideias" in data:
                st.markdown("### 💡 Ideias Geradas")

                col_act1, col_act2 = st.columns(2)
                with col_act1:
                    if st.button("📥 Carregar na aba 💡 Ideias", type="primary", width="stretch"):
                        ideias_formatadas = [_format_ideia(i) for i in data["ideias"]]
                        from tabs.tab_ideias import _ensure_idea_ids
                        _ensure_idea_ids(ideias_formatadas, "notebooklm")
                        st.session_state["ideias"] = {"ideias": ideias_formatadas}
                        st.session_state["ideias_selecionadas"] = ideias_formatadas
                        save_geracao("ideias", {"ideias": ideias_formatadas})
                        st.success(f"✅ {len(ideias_formatadas)} ideias salvas! Abra a aba '💡 Ideias' para visualizar.")

                with col_act2:
                    if st.button("🎨 Enviar para Gerador de Prompts", width="stretch"):
                        ideias_formatadas = [_format_ideia(i) for i in data["ideias"]]
                        from tabs.tab_ideias import _ensure_idea_ids
                        _ensure_idea_ids(ideias_formatadas, "notebooklm")
                        st.session_state["ideias_selecionadas"] = ideias_formatadas
                        st.session_state["nb_ideias_para_prompts"] = True
                        st.success(f"✅ {len(ideias_formatadas)} ideias enviadas para Prompts!")

                for i, ideia in enumerate(data["ideias"]):
                    with st.expander(f"{'🔴' if i==0 else '🟡' if i==1 else '🟢'} {ideia.get('titulo', '')}"):
                        st.markdown(f"**Eixo:** {ideia.get('eixo', '')}")
                        st.markdown(f"**Tema:** {ideia.get('tema', '')}")
                        st.markdown(f"**Público:** {ideia.get('publico_alvo', 'Pais de classes A/B do Tatuapé')}")
                        st.markdown(f"**CTA:** `{ideia.get('cta', '')}`")
                        st.markdown(f"**Fonte Notebook:** {ideia.get('fonte_notebook', '')}")

                        if st.button("📤 Enviar para Prompts", key=f"send_idea_{i}"):
                            ideia_formatada = _format_ideia(ideia)
                            if "ideias_selecionadas" not in st.session_state:
                                st.session_state["ideias_selecionadas"] = []
                            st.session_state["ideias_selecionadas"].append(ideia_formatada)
                            st.success(f"✅ '{ideia.get('titulo', '')}' enviada para Prompts!")

            if "concorrentes" in data:
                st.markdown("### 🏢 Análise de Concorrência")
                for c in data["concorrentes"]:
                    with st.expander(f"🏫 {c.get('nome', '')}"):
                        st.markdown(f"**O que faz:** {c.get('o_que_faz', '')}")
                        st.markdown(f"**Pontos fortes:** {c.get('pontos_fortes', '')}")
                        st.markdown(f"**Pontos fracos:** {c.get('pontos_fracos', '')}")

            if "dados_relevantes" in data:
                st.markdown("### 📊 Dados Relevantes")
                for d in data["dados_relevantes"]:
                    st.info(f"**{d.get('dado', '')}**\nFonte: {d.get('fonte', '')}")
        else:
            st.markdown("### 📄 Resposta do NotebookLM")
            st.markdown(result)

        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📤 Enviar como Tendências", width="stretch"):
                st.session_state["tendencias_texto"] = result
                st.success("✅ Enviado! Vá para aba '📈 Tendências'")
        with col2:
            if st.button("📤 Enviar como Contexto para Ideias", width="stretch"):
                st.session_state["nb_contexto_para_ideias"] = result
                st.success("✅ Enviado! Vá para aba '💡 Ideias' e use este contexto")

    if selected_nb_id:
        st.markdown("---")
        st.markdown("### 🔗 Link direto para o notebook")
        st.markdown(f"[Abrir no NotebookLM](https://notebooklm.google.com/notebook/{selected_nb_id})")
