"""
tabs/tab_legendas.py — Aba de Geração de Legendas.

Gera 3 opções de legenda conectadas ao tema do carrossel selecionado.
"""
import json

import streamlit as st

from batch_engine import gerar_legendas_ideia
from persistence import save_geracao
from tabs._ui import api_key_ok, clipboard_button, empty_state, seletor_tom


def render() -> None:
    st.markdown("## 📝 Gerador de Legendas")
    st.markdown("Gera 3 opções de legenda conectadas ao tema do carrossel selecionado.")

    if not st.session_state.get("ideias_selecionadas"):
        empty_state("selecao")
    else:
        ideias_sel = st.session_state["ideias_selecionadas"]
        opts_l = {f"{i.get('eixo','?')} — {i.get('titulo','')}": i for i in ideias_sel}
        escolha_l = st.selectbox("Carrossel:", list(opts_l.keys()), key="sel_legenda")
        tom = seletor_tom("tom_selecionado_legendas")

        if st.button("📝 Gerar Legendas", type="primary", width="stretch"):
            if not api_key_ok():
                st.warning("⚠️ Configure a chave API Gemini.")
            else:
                ideia = opts_l[escolha_l]
                with st.spinner("🤖 Gerando 3 opções de legenda…"):
                    dados = gerar_legendas_ideia(ideia, forcar=True, tom=tom)
                    if dados:
                        dados["titulo"] = ideia.get("titulo", "Ideia")
                        dados["eixo"] = ideia.get("eixo", "")
                        dados["curso"] = ideia.get("curso", "")
                        dados["cta"] = ideia.get("cta", "")
                        st.session_state.setdefault("legendas_lote", []).append(dados)
                        save_geracao("legendas", dados)
                        novo_idx_l = len(st.session_state["legendas_lote"])
                        st.session_state["sel_legendas_lote"] = f"{novo_idx_l}. {dados['titulo']}"
                        st.success("✅ 3 legendas geradas!")
                        st.rerun()

        if st.session_state.get("legendas_lote"):
            legendas_items = st.session_state["legendas_lote"]
            labels_l = [f"{n + 1}. {it.get('titulo') or 'Ideia'}" for n, it in enumerate(legendas_items)]
            # Seletor quando há várias gerações (P3 — nada se sobrescreve)
            if len(legendas_items) > 1:
                if st.session_state.get("sel_legendas_lote") not in labels_l:
                    st.session_state["sel_legendas_lote"] = labels_l[-1]
                csel_l, cdel_l = st.columns([5, 1])
                with csel_l:
                    escolhido_l = st.selectbox("Geração de legendas:", labels_l, key="sel_legendas_lote")
                    idx_l = labels_l.index(escolhido_l)
                with cdel_l:
                    st.write("")  # alinha o botão ao selectbox
                    if st.button("🗑️", key="del_legendas_lote", help="Remover esta geração"):
                        legendas_items.pop(idx_l)
                        if not legendas_items:
                            st.session_state.pop("legendas_lote", None)
                        st.session_state.pop("sel_legendas_lote", None)
                        st.rerun()
            else:
                idx_l = 0
            legendas_data = legendas_items[idx_l]
            titulo_l = legendas_data.get("titulo", "Carrossel")
            eixo_l = legendas_data.get("eixo", "")
            badge_eixo = f" • Eixo: **{eixo_l}**" if eixo_l else ""
            st.info(f"📌 **Carrossel:** {titulo_l}{badge_eixo}")
            opcao_icons = {1: "🔴", 2: "🟡", 3: "🟢"}

            for leg in legendas_data.get("legendas", []):
                op = leg.get("opcao", 1)
                estilo = leg.get("estilo", "")
                tecnica = leg.get("tecnica", "")
                titulo_exp = f"{opcao_icons.get(op,'•')} Opção {op} — {estilo}"
                if tecnica:
                    titulo_exp += f" [{tecnica}]"
                legenda_completa = leg.get("legenda_completa", "")
                # Contagem local: o número do modelo (char_count) só entra como
                # fallback quando o texto completo não veio na resposta.
                char_count = (
                    len(legenda_completa)
                    if legenda_completa
                    else int(leg.get("char_count") or 0)
                )

                with st.expander(
                    titulo_exp,
                    expanded=(op == 1),
                ):
                    if leg.get("por_que_funciona"):
                        st.info(f"🧠 **Estratégia de Conversão:** {leg['por_que_funciona']}")

                    st.markdown(f"**🎣 Gancho:** {leg.get('gancho','')}")
                    st.markdown(f"**📖 Corpo:** {leg.get('corpo','')}")
                    st.markdown(f"**📢 CTA:** {leg.get('cta','')}")
                    st.markdown(f"**# Hashtags:** {leg.get('hashtags','')}")
                    st.divider()
                    st.markdown("**📋 Legenda completa:**")
                    st.code(legenda_completa, language=None)

                    # Contagem de caracteres
                    if char_count > 2200:
                        st.error(f"⚠️ {char_count} chars — acima do limite do Instagram (2.200)")
                    elif char_count > 1800:
                        st.warning(f"⏳ {char_count} chars — próximo do limite")
                    else:
                        st.success(f"✅ {char_count} chars — dentro do ideal")

                    clipboard_button(
                        legenda_completa,
                        f"📋 Copiar Legenda Opção {op}",
                        key=f"clip_leg_{op}",
                    )

            if legendas_data.get("dicas_uso"):
                st.divider()
                st.markdown("### 💡 Dicas de Uso")
                st.info(legendas_data["dicas_uso"])

            st.divider()
            c1, c2 = st.columns(2)
            with c1:
                st.download_button(
                    "⬇️ Exportar JSON",
                    data=json.dumps(legendas_data, ensure_ascii=False, indent=2),
                    file_name="legendas_carrossel.json",
                    mime="application/json",
                    width="stretch",
                )
            with c2:
                txt_legs = "\n\n---\n\n".join(
                    f"OPÇÃO {leg.get('opcao','?')} — {leg.get('estilo','')}\n\n{leg.get('legenda_completa','')}"
                    for leg in legendas_data.get("legendas", [])
                )
                st.download_button(
                    "⬇️ Exportar .txt",
                    data=txt_legs,
                    file_name="legendas_carrossel.txt",
                    mime="text/plain",
                    width="stretch",
                )
