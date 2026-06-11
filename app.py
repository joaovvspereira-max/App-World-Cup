"""Aplicação Streamlit — Mundial 2026."""

from datetime import date, datetime
from typing import Any

import pandas as pd
import streamlit as st

from database.auth import AuthError, login_utilizador, registar_utilizador
from database.jogos import get_jogos
from database.supabase_client import get_supabase_client
import urllib.request
import urllib.parse
import json
import time
import unicodedata
from database.palpites import (
    get_palpites_utilizador,
    guardar_palpites_em_lote,
    submeter_palpite,
    get_ranking,
)
from database.palpites_macro import (
    JOGADORES_ELITE,
    OPCAO_OUTRO,
    PAISES_ELITE,
    get_palpite_macro,
    guardar_palpite_macro,
)

st.set_page_config(
    page_title="Mundial 2026",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
        .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
        }
        h1 {
            color: #1A1A2E;
            font-weight: 700;
            margin-bottom: 0.25rem;
        }
        .subtitle {
            color: #5C6B7A;
            font-size: 1.05rem;
            margin-bottom: 1.5rem;
        }
        div[data-testid="stMetric"] {
            background-color: #F0F4F8;
            border-radius: 8px;
            padding: 0.75rem 1rem;
        }
        div[data-testid="stSidebar"] .stTabs [data-baseweb="tab-list"] {
            gap: 0.5rem;
        }
        .jogo-meta {
            color: #5C6B7A;
            font-size: 0.875rem;
            margin-bottom: 0.5rem;
        }
        .jogo-card {
            background: #ffffff;
            padding: 0.6rem 0.75rem;
            border-radius: 10px;
            box-shadow: 0 1px 3px rgba(16,24,40,0.04);
            margin-bottom: 1rem;
        }
        .jogo-linha {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0.5rem 0;
            margin: 0.75rem 0 0.5rem 0;
        }
        .jogo-equipa {
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        .jogo-separador {
            text-align: center;
            font-weight: 700;
            color: #5C6B7A;
        }
        img.flag-icon { border-radius: 4px; vertical-align: middle; }

        /* Estilo global para inputs numéricos de golos */
        input[type="number"] {
            font-size: 1.25rem !important;
            font-weight: 700 !important;
            text-align: center !important;
            border-radius: 8px !important;
            padding: 6px 10px !important;
            box-shadow: 0 1px 2px rgba(16,24,40,0.04) inset !important;
            border: 1px solid #E6E9EE !important;
            width: 64px !important;
        }
        .team-name { font-size: 1.25rem; font-weight:700; }
        .jogo-card { text-align: center; }
        .jogo-equipa { justify-content: center; }
        .sticky-header { position: sticky; top: 0; z-index: 1100; background: white; padding: 0.5rem 0; }
        .sticky-submit { position: sticky; top: 64px; z-index: 1050; background: white; padding: 0.5rem 0; display:flex; justify-content:center; }
    </style>
    """,
    unsafe_allow_html=True,
)

# Mapeamento de países para códigos de bandeira (flagcdn usa códigos ISO 2-letters)
DEFAULT_FLAG_MAP = {
    "Portugal": "pt",
    "Brasil": "br",
    "Espanha": "es",
    "França": "fr",
    "Alemanha": "de",
    "Argentina": "ar",
}
ALIASES = {
    "EUA": "United States",
    "Países Baixos": "Netherlands",
    "Inglaterra": "United Kingdom",
    "Coreia do Sul": "Korea, Republic of",
    "Irão": "Iran",
}


def _normalize(text: str) -> str:
    if not text:
        return ""
    text = str(text)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text.lower().strip()


def build_flag_map_from_db() -> dict:
    """Constrói mapeamento country name -> iso2 (lowercase) a partir da tabela `jogos`.

    Faz fetch de toda a lista de países (`restcountries`) e normaliza nomes para match robusto.
    """
    # cache in session to avoid repeated external requests
    if st.session_state.get("_flag_map_cache"):
        return st.session_state["_flag_map_cache"]

    flag_map = DEFAULT_FLAG_MAP.copy()
    try:
        client = get_supabase_client()
        resp = client.table("jogos").select("equipa_casa, equipa_fora").execute()
        rows = resp.data or []
    except Exception:
        return flag_map

    nomes = set()
    for r in rows:
        if r.get("equipa_casa"):
            nomes.add(r.get("equipa_casa"))
        if r.get("equipa_fora"):
            nomes.add(r.get("equipa_fora"))

    # Build a lookup of country names -> cca2 by fetching all countries once
    name_lookup: dict[str, str] = {}
    try:
        with urllib.request.urlopen("https://restcountries.com/v3.1/all", timeout=10) as u:
            all_c = json.load(u)
            for c in all_c:
                cca2 = c.get("cca2")
                if not cca2:
                    continue
                # common and official names
                names_to_index = []
                name_obj = c.get("name") or {}
                common = name_obj.get("common")
                official = name_obj.get("official")
                if common:
                    names_to_index.append(common)
                if official:
                    names_to_index.append(official)
                # altSpellings
                for alt in c.get("altSpellings", []) or []:
                    names_to_index.append(alt)
                # translations
                for t in (c.get("translations") or {}).values():
                    tn = t.get("common")
                    if tn:
                        names_to_index.append(tn)

                for nm in names_to_index:
                    key = _normalize(nm)
                    if key:
                        name_lookup[key] = cca2.lower()
            # be polite
            time.sleep(0.05)
    except Exception:
        # if all-countries fetch fails, we'll rely on defaults and aliases
        name_lookup = {}

    for nome in nomes:
        if nome in flag_map:
            continue
        norm = _normalize(nome)
        code = name_lookup.get(norm)
        if not code:
            # try alias mapping
            alias = ALIASES.get(nome)
            if alias:
                code = name_lookup.get(_normalize(alias))
        if code:
            flag_map[nome] = code

    # save cache
    st.session_state["_flag_map_cache"] = flag_map
    return flag_map
    


def utilizador_autenticado() -> bool:
    """Indica se existe um utilizador com sessão ativa."""
    return bool(st.session_state.get("user_id"))


def terminar_sessao() -> None:
    """Remove os dados de autenticação da sessão."""
    st.session_state.user_id = None
    st.session_state.user_name = None
    st.session_state.user_email = None


def formatar_data_jogo(valor: Any) -> str | None:
    """Formata a data do jogo para exibição."""
    if not valor:
        return None
    if isinstance(valor, date):
        return valor.strftime("%d/%m/%Y")
    try:
        return datetime.fromisoformat(str(valor).replace("Z", "+00:00")).strftime("%d/%m/%Y")
    except ValueError:
        return str(valor)


def formatar_info_jogo(jogo: dict[str, Any]) -> str:
    """Compõe a linha secundária com data, fase, grupo e cidade."""
    partes: list[str] = []

    data = formatar_data_jogo(jogo.get("data"))
    if data:
        partes.append(data)

    if jogo.get("fase"):
        partes.append(str(jogo["fase"]))

    if jogo.get("grupo"):
        grupo = str(jogo["grupo"])
        partes.append(grupo if grupo.lower().startswith("grupo") else f"Grupo {grupo}")

    if jogo.get("cidade"):
        partes.append(str(jogo["cidade"]))

    return " · ".join(partes) if partes else "—"


def formatar_resultado_real(jogo: dict[str, Any]) -> str | None:
    """Devolve o resultado real formatado, se existir."""
    golos_casa = jogo.get("golos_casa_real")
    golos_fora = jogo.get("golos_fora_real")
    if golos_casa is None or golos_fora is None:
        return None
    return f"{int(golos_casa)} - {int(golos_fora)}"


def preparar_opcao_selectbox(valor_guardado: str | None, opcoes: list[str]) -> tuple[int, str]:
    """Define o índice do selectbox e o texto personalizado para a opção 'Outro...'."""
    opcoes_fixas = opcoes[:-1]
    if valor_guardado and valor_guardado not in opcoes_fixas:
        return len(opcoes) - 1, valor_guardado
    if valor_guardado in opcoes_fixas:
        return opcoes_fixas.index(valor_guardado), ""
    return 0, ""


def resolver_valor_previsao(selecionado: str, outro_texto: str) -> str:
    """Devolve o valor final escolhido no selectbox ou no campo 'Outro...'."""
    if selecionado == OPCAO_OUTRO:
        return outro_texto.strip()
    return selecionado.strip()


def renderizar_previsoes_macro() -> None:
    """Secção de previsões especiais: campeão do mundial e melhor marcador."""
    st.subheader("Previsões de Campeão e Melhor Marcador")

    if not utilizador_autenticado():
        st.caption("Inicia sessão na barra lateral para guardar as tuas previsões especiais.")
        return

    try:
        palpite_macro = get_palpite_macro(st.session_state.user_id)
    except Exception as exc:
        st.error(f"Não foi possível carregar as tuas previsões especiais: {exc}")
        return

    idx_vencedor, outro_vencedor = preparar_opcao_selectbox(
        palpite_macro.get("vencedor_mundial") if palpite_macro else None,
        PAISES_ELITE,
    )
    idx_marcador, outro_marcador = preparar_opcao_selectbox(
        palpite_macro.get("melhor_marcador") if palpite_macro else None,
        JOGADORES_ELITE,
    )

    with st.form("form_palpites_macro"):
        vencedor_selecionado = st.selectbox(
            "Vencedor do Mundial",
            PAISES_ELITE,
            index=idx_vencedor,
        )
        vencedor_outro = ""
        if vencedor_selecionado == OPCAO_OUTRO:
            vencedor_outro = st.text_input(
                "Indica o país",
                value=outro_vencedor,
                placeholder="Escreve o nome do país",
            )

        marcador_selecionado = st.selectbox(
            "Melhor Marcador",
            JOGADORES_ELITE,
            index=idx_marcador,
        )
        marcador_outro = ""
        if marcador_selecionado == OPCAO_OUTRO:
            marcador_outro = st.text_input(
                "Indica o jogador",
                value=outro_marcador,
                placeholder="Escreve o nome do jogador",
            )

        guardar_macro = st.form_submit_button(
            "Guardar previsões especiais",
            use_container_width=True,
        )

    if palpite_macro and palpite_macro.get("atualizado_em"):
        st.caption(f"Última atualização: {palpite_macro['atualizado_em']}")

    if guardar_macro:
        vencedor = resolver_valor_previsao(vencedor_selecionado, vencedor_outro)
        marcador = resolver_valor_previsao(marcador_selecionado, marcador_outro)

        if not vencedor or not marcador:
            st.error("Preenche o vencedor do mundial e o melhor marcador.")
            return

        try:
            guardar_palpite_macro(
                user_id=st.session_state.user_id,
                vencedor_mundial=vencedor,
                melhor_marcador=marcador,
            )
            st.success("Previsões especiais guardadas com sucesso.")
            st.rerun()
        except Exception as exc:
            st.error(f"Erro ao guardar previsões especiais: {exc}")


def renderizar_ranking() -> None:
    """Secção de Ranking: tabela principal e expanders por utilizador."""
    st.subheader("Ranking — Classificação Geral")

    try:
        ranking = get_ranking()
    except Exception as exc:
        st.error(f"Não foi possível carregar o ranking: {exc}")
        return

    if not ranking:
        st.info("Ainda não existem palpites com resultados para compilar o ranking.")
        return

    # DataFrame para a tabela de liderança
    df = pd.DataFrame(
        [{"Nome": r.get("nome"), "Pontos": r.get("pontos_totais", 0)} for r in ranking]
    )
    df = df.sort_values(by="Pontos", ascending=False).reset_index(drop=True)

    st.dataframe(df, use_container_width=True)

    # Expanders com detalhe por utilizador (apenas jogos finalizados aparecem no detalhe)
    for usuario in ranking:
        nome = usuario.get("nome")
        pontos = usuario.get("pontos_totais", 0)
        detalhes = usuario.get("palpites", [])
        bonus = usuario.get("bonus_aplicado", 0)

        with st.expander(f"{nome} — {pontos} pts{' (+' + str(bonus) + ' bonus)' if bonus else ''}"):
            if not detalhes:
                st.write("Sem palpites finalizados.")
                continue
            detalhes_df = pd.DataFrame(detalhes)
            # Coloca a descrição do jogo como primeira coluna
            detalhes_df["Jogo"] = detalhes_df.apply(lambda r: f"{r['equipa_casa']} vs {r['equipa_fora']}", axis=1)
            detalhes_df = detalhes_df[["Jogo", "palpite", "resultado_real", "pontos"]]
            detalhes_df = detalhes_df.rename(columns={"palpite": "Palpite", "resultado_real": "Resultado Real", "pontos": "Pontos"})
            st.table(detalhes_df)


def renderizar_auth() -> None:
    """Formulário de login e registo na barra lateral."""
    with st.sidebar:
        st.header("Entrar na app")
        st.caption("Inicia sessão ou cria uma conta para submeter palpites.")

        tab_login, tab_registo = st.tabs(["Login", "Registo"])

        with tab_login:
            with st.form("form_login", clear_on_submit=False):
                email = st.text_input("Email", placeholder="tu@email.com")
                password = st.text_input("Password", type="password")
                login_submetido = st.form_submit_button("Entrar", use_container_width=True)

            if login_submetido:
                try:
                    dados = login_utilizador(email, password)
                    st.session_state.user_id = dados["user_id"]
                    st.session_state.user_name = dados["user_name"]
                    st.session_state.user_email = dados.get("user_email")
                    st.success(f"Bem-vindo, {dados['user_name']}!")
                    st.rerun()
                except AuthError as exc:
                    st.error(str(exc))
                except Exception as exc:
                    st.error(f"Erro ao iniciar sessão: {exc}")

        with tab_registo:
            with st.form("form_registo", clear_on_submit=True):
                nome = st.text_input("Nome", placeholder="O teu nome")
                email = st.text_input("Email", placeholder="tu@email.com")
                password = st.text_input("Password", type="password")
                registo_submetido = st.form_submit_button("Criar conta", use_container_width=True)

            if registo_submetido:
                try:
                    dados = registar_utilizador(email, password, nome)
                    st.session_state.user_id = dados["user_id"]
                    st.session_state.user_name = dados["user_name"]
                    st.session_state.user_email = dados.get("user_email")
                    st.success("Conta criada com sucesso!")
                    st.rerun()
                except AuthError as exc:
                    st.error(str(exc))
                except Exception as exc:
                    st.error(f"Erro ao criar conta: {exc}")


def renderizar_barra_lateral() -> None:
    """Mostra autenticação ou informação da conta consoante o estado da sessão."""
    # Auth/account area in the sidebar
    if not utilizador_autenticado():
        renderizar_auth()
        return

    with st.sidebar:
        st.header("Conta")
        st.markdown(f"Olá, **{st.session_state.user_name}**")
        if st.button("Terminar sessão", use_container_width=True):
            terminar_sessao()
            st.rerun()


def selecionar_pagina() -> str:
    """Mostra um selector na barra lateral e devolve a página escolhida."""
    with st.sidebar:
        st.header("Navegação")
        opcoes = [
            "Página Inicial",
            "Calendário",
            "Previsões Especiais",
            "Ranking - Classificação Geral",
        ]
        # Mostrar Admin apenas para o email definido em secrets
        admin_email = st.secrets.get("ADMIN_EMAIL") if isinstance(st.secrets, dict) or hasattr(st, 'secrets') else None
        if st.session_state.get("user_email") and admin_email and st.session_state.get("user_email") == admin_email:
            opcoes.append("Admin")

        escolha = st.radio("Ir para", opcoes, index=0)
    return escolha


def renderizar_admin() -> None:
    """Área administrativa — apenas acessível ao email definido em `st.secrets['ADMIN_EMAIL']`."""
    st.subheader("Área Administrativa")

    if not utilizador_autenticado():
        st.warning("Inicia sessão com a conta de administrador para aceder a esta área.")
        return

    admin_email = st.secrets.get("ADMIN_EMAIL")
    if not admin_email or st.session_state.get("user_email") != admin_email:
        st.warning("Não estás autorizado a aceder a esta página.")
        return

    client = get_supabase_client()

    st.markdown("**Inserir / Atualizar resultado de jogo**")
    try:
        jogos = get_jogos()
    except Exception as exc:
        st.error(f"Erro ao carregar jogos: {exc}")
        return

    if jogos:
        escolhas = [f"{j['id']} — {j.get('equipa_casa','?')} vs {j.get('equipa_fora','?')} ({formatar_info_jogo(j)})" for j in jogos]
        idx = st.selectbox("Escolhe o jogo", range(len(escolhas)), format_func=lambda i: escolhas[i])
        jogo = jogos[idx]

        with st.form("form_resultado"):
            golos_casa = st.number_input("Golos casa (real)", min_value=0, value=int(jogo.get("golos_casa_real") or 0), key="admin_golos_casa")
            golos_fora = st.number_input("Golos fora (real)", min_value=0, value=int(jogo.get("golos_fora_real") or 0), key="admin_golos_fora")
            guardar_res = st.form_submit_button("Guardar Resultado")

        if guardar_res:
            try:
                client.table("jogos").update({"golos_casa_real": int(golos_casa), "golos_fora_real": int(golos_fora)}).eq("id", jogo["id"]).execute()
                st.success("Resultado guardado com sucesso.")
                st.rerun()
            except Exception as exc:
                st.error(f"Erro ao guardar resultado: {exc}")

    st.markdown("---")
    st.markdown("**Criar novo jogo (fase de grupos)**")
    with st.form("form_criar_jogo"):
        equipa_casa = st.text_input("Equipa Casa")
        equipa_fora = st.text_input("Equipa Fora")
        data_jogo = st.date_input("Data")
        fase = st.text_input("Fase", value="Grupos")
        grupo = st.text_input("Grupo")
        cidade = st.text_input("Cidade")
        criar = st.form_submit_button("Criar Jogo")

    if criar:
        try:
            payload = {
                "equipa_casa": equipa_casa.strip(),
                "equipa_fora": equipa_fora.strip(),
                "data": data_jogo.isoformat(),
                "fase": fase.strip(),
                "grupo": grupo.strip(),
                "cidade": cidade.strip(),
            }
            client.table("jogos").insert(payload).execute()
            st.success("Jogo criado com sucesso.")
            st.rerun()
        except Exception as exc:
            st.error(f"Erro ao criar jogo: {exc}")


def renderizar_jogo_somente_leitura(jogo: dict[str, Any]) -> None:
    """Exibe um jogo sem inputs de palpite."""
    st.markdown(f'<p class="jogo-meta">{formatar_info_jogo(jogo)}</p>', unsafe_allow_html=True)

    col_casa, col_sep, col_fora = st.columns([5, 1, 5])
    with col_casa:
        st.markdown(f'<p class="jogo-equipa">{jogo.get("equipa_casa", "—")}</p>', unsafe_allow_html=True)
    with col_sep:
        resultado = formatar_resultado_real(jogo)
        st.markdown(
            f'<p class="jogo-separador">{resultado or "—"}</p>',
            unsafe_allow_html=True,
        )
    with col_fora:
        st.markdown(f'<p class="jogo-equipa">{jogo.get("equipa_fora", "—")}</p>', unsafe_allow_html=True)

    st.divider()


def renderizar_formulario_palpites(jogos: list[dict[str, Any]]) -> None:
    """Formulário global com palpites inline para todos os jogos."""
    try:
        palpites_existentes = get_palpites_utilizador(st.session_state.user_id)
    except Exception as exc:
        st.error(f"Não foi possível carregar os teus palpites: {exc}")
        return
    # build dynamic flag map from DB
    flag_map = build_flag_map_from_db()

    palpites_submetidos: list[dict[str, int]] = []
    with st.form("form_palpites"):
        # sticky save button at top
        st.markdown('<div class="sticky-submit">', unsafe_allow_html=True)
        guardar = st.form_submit_button("Guardar Palpites", use_container_width=False)
        st.markdown('</div>', unsafe_allow_html=True)

        for jogo in jogos:
            jogo_id = jogo["id"]
            palpite = palpites_existentes.get(jogo_id, {})

            # visual wrapper (card)
            st.markdown(f'<div class="jogo-card">', unsafe_allow_html=True)
            st.markdown(f'<p class="jogo-meta">{formatar_info_jogo(jogo)}</p>', unsafe_allow_html=True)

            col_left, col_mid, col_sep, col_mid2, col_right = st.columns([2.5, 1, 0.4, 1, 2.5])

            with col_left:
                # home team name + input adjacent
                name_col, input_col = st.columns([3, 1])
                equipe_casa = jogo.get("equipa_casa", "—")
                codigo_casa = flag_map.get(equipe_casa, "")
                img_casa = (
                    f'<img class="flag-icon" src="https://flagcdn.com/48x36/{codigo_casa}.png" width="48" height="36"/>'
                    if codigo_casa
                    else ""
                )
                with name_col:
                    st.markdown(
                        f'<p class="jogo-equipa">{img_casa} <span class="team-name">{equipe_casa}</span></p>',
                        unsafe_allow_html=True,
                    )
                with input_col:
                    golos_casa = st.number_input(
                        "Golos casa",
                        min_value=0,
                        step=1,
                        value=int(palpite.get("golos_casa") or 0),
                        key=f"golos_casa_{jogo_id}",
                        label_visibility="collapsed",
                    )

            with col_sep:
                st.markdown('<p class="jogo-separador">—</p>', unsafe_allow_html=True)

            with col_right:
                # away input + name adjacent (input first so name appears next to it)
                input_col2, name_col2 = st.columns([1, 3])
                equipe_fora = jogo.get("equipa_fora", "—")
                codigo_fora = flag_map.get(equipe_fora, "")
                img_fora = (
                    f'<img class="flag-icon" src="https://flagcdn.com/48x36/{codigo_fora}.png" width="48" height="36"/>'
                    if codigo_fora
                    else ""
                )
                with input_col2:
                    golos_fora = st.number_input(
                        "Golos fora",
                        min_value=0,
                        step=1,
                        value=int(palpite.get("golos_fora") or 0),
                        key=f"golos_fora_{jogo_id}",
                        label_visibility="collapsed",
                    )
                with name_col2:
                    st.markdown(
                        f'<p class="jogo-equipa"><span class="team-name">{equipe_fora}</span> {img_fora}</p>',
                        unsafe_allow_html=True,
                    )

            palpites_submetidos.append(
                {
                    "jogo_id": jogo_id,
                    "golos_casa": st.session_state.get(f"golos_casa_{jogo_id}", int(palpite.get("golos_casa") or 0)),
                    "golos_fora": st.session_state.get(f"golos_fora_{jogo_id}", int(palpite.get("golos_fora") or 0)),
                }
            )
            st.markdown('</div>', unsafe_allow_html=True)
            st.divider()

    if guardar:
        try:
            # Recolecta valores actuais dos inputs (em st.session_state)
            payloads = []
            for p in palpites_submetidos:
                jid = p["jogo_id"]
                payloads.append(
                    {
                        "jogo_id": jid,
                        "golos_casa": int(st.session_state.get(f"golos_casa_{jid}", 0)),
                        "golos_fora": int(st.session_state.get(f"golos_fora_{jid}", 0)),
                    }
                )

            guardar_palpites_em_lote(st.session_state.user_id, payloads)
            st.success(f"{len(payloads)} palpite(s) guardado(s) com sucesso.")
            st.rerun()
        except Exception as exc:
            st.error(f"Erro ao guardar palpites: {exc}")


def exibir_jogos() -> None:
    """Carrega os jogos e exibe o calendário com palpites inline."""
    try:
        jogos = get_jogos()
    except Exception as exc:
        st.error(f"Não foi possível carregar os jogos: {exc}")
        return

    col1, col2 = st.columns(2)
    col1.metric("Total de jogos", len(jogos))
    col2.metric(
        "Jogos com resultado",
        sum(1 for jogo in jogos if formatar_resultado_real(jogo) is not None),
    )

    st.subheader("Calendário de jogos")

    if not jogos:
        st.info("Ainda não existem jogos registados.")
        return

    if utilizador_autenticado():
        renderizar_formulario_palpites(jogos)
    else:
        for jogo in jogos:
            renderizar_jogo_somente_leitura(jogo)


init_auth_state()
pagina = selecionar_pagina()
renderizar_barra_lateral()

st.markdown('<div class="sticky-header"><h1>⚽ Mundial 2026</h1></div>', unsafe_allow_html=True)

if pagina == "Página Inicial":
    st.markdown(
        '<p class="subtitle">Bem-vindo à app de palpites — explora o Mundial 2026.</p>',
        unsafe_allow_html=True,
    )

    # Preview top 3 do ranking
    try:
        ranking = get_ranking()
    except Exception as exc:
        st.error(f"Não foi possível carregar o ranking: {exc}")
        ranking = []

    if ranking:
        top3 = ranking[:3]
        df_top3 = pd.DataFrame([{"Posição": i + 1, "Nome": r.get("nome"), "Pontos": r.get("pontos_totais", 0)} for i, r in enumerate(top3)])
        st.subheader("Top 3")
        st.table(df_top3)
    else:
        st.info("Ainda não existem dados de ranking para apresentar.")

elif pagina == "Calendário":
    st.markdown(
        '<p class="subtitle">Consulta o calendário e submete os teus palpites.</p>',
        unsafe_allow_html=True,
    )
    if not utilizador_autenticado():
        st.info("Inicia sessão na barra lateral para editar e guardar palpites.")
    exibir_jogos()

elif pagina == "Previsões Especiais":
    st.markdown(
        '<p class="subtitle">Vê e guarda o teu vencedor do Mundial e melhor marcador.</p>',
        unsafe_allow_html=True,
    )
    renderizar_previsoes_macro()

elif pagina == "Ranking - Classificação Geral":
    st.markdown(
        '<p class="subtitle">Classificação geral dos participantes.</p>',
        unsafe_allow_html=True,
    )
    renderizar_ranking()

elif pagina == "Admin":
    renderizar_admin()
