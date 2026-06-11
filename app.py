"""Streamlit app — World Cup 2026."""

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
import re
import unicodedata
import difflib
from database.palpites import (
    get_palpites_utilizador,
    guardar_palpites_em_lote,
    submeter_palpite,
    get_ranking,
    calcular_pontos_jogo,
)
import os
from pathlib import Path


def _read_local_secrets() -> dict:
    """Try to read .streamlit/secrets.toml directly as a fallback when `st.secrets` is empty.

    Uses tomllib (Python 3.11+) or the third-party `toml` package if available.
    Returns a dict with parsed values or an empty dict on failure.
    """
    secrets_path = Path.cwd() / ".streamlit" / "secrets.toml"
    if not secrets_path.exists():
        return {}
    try:
        import tomllib as _toml
    except Exception:
        try:
            import toml as _toml
        except Exception:
            return {}
    try:
        with secrets_path.open("rb") as f:
            data = _toml.load(f)
        return data or {}
    except Exception:
        return {}
from database.palpites_macro import (
    JOGADORES_ELITE,
    OPCAO_OUTRO,
    PAISES_ELITE,
    get_palpite_macro,
    guardar_palpite_macro,
)

st.set_page_config(
    page_title="World Cup 2026",
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
            font-size: 0.95rem;
            margin-top: 0.04rem;
            margin-bottom: 0.08rem;
            font-weight: 600;
        }
        .jogo-card {
            background: transparent;
            padding: 0.18rem 0.75rem;
            border-radius: 0;
            box-shadow: none;
            margin: 0 0 0.12rem 0;
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
        img.flag-icon { border-radius: 12px; vertical-align: middle; border: 1px solid #E6E9EE; background: white; padding: 2px; object-fit: cover; max-width:100%; height:auto; }
        .flag-wrapper { display:flex; align-items:center; width:80px; box-sizing:border-box; overflow:hidden; }
        .flag-left { justify-content:flex-start; padding-left:6px; }
        .flag-right { justify-content:flex-end; padding-right:6px; }
        .team-block { display:flex; align-items:center; gap:0.75rem; justify-content:center; min-height:48px; }

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
        .team-name { font-size: 1.25rem; font-weight:800; }
        .jogo-card { text-align: center; padding: 0.24rem 0.75rem; margin-top:0.125rem; border-bottom: 1px solid #E6E9EE; }
        .jogo-equipa { justify-content: center; }
        .result-space { height: 4px; }
            .resultado-real { text-align: center; font-size: 1.05rem; font-weight: 700; color: #1A1A2E; margin: 0.25rem 0; }
        input[type="number"] { width: 56px !important; height:40px !important; }
        .sticky-header { position: sticky; top: 0; z-index: 1100; background: white; padding: 0.5rem 0; }
        .sticky-submit { display: none; }
        .save-card { width:100%; display:block; margin-top:0.5rem; }
        .save-card .stButton>button { background-color:#0b63d6 !important; color:white !important; font-weight:900 !important; font-size:22px !important; height:64px !important; border-radius:12px !important; width:100% !important; text-transform:uppercase !important; letter-spacing:0.6px !important; }

        /* Hide default empty form header/panel that sometimes renders above the first card */
        form[aria-label="form_palpites"] { background: transparent !important; box-shadow: none !important; padding: 0 !important; margin: 0 !important; border-radius: 0 !important; }
        form[aria-label="form_palpites"] > div:first-child { display: none !important; }
        /* Reduce divider (hr) spacing and any Streamlit divider wrappers inside the form */
        form[aria-label="form_palpites"] hr, form[aria-label="form_palpites"] .stDivider { margin: 0.125rem 0 !important; padding: 0 !important; }
        hr { margin: 0.125rem 0 !important; }
        /* Style any submit button inside the form reliably */
        form[aria-label="form_palpites"] .stButton>button,
        form[aria-label="form_palpites"] button[type="submit"],
        form[aria-label="form_palpites"] input[type="submit"],
        form[aria-label="form_palpites"] .save-card .stButton>button,
        .save-card button,
        .save-card input[type="submit"] {
            background-color:#0b63d6 !important;
            background-image: none !important;
            color: #ffffff !important;
            font-weight: 900 !important;
            font-size: 24px !important;
            height: 64px !important;
            padding: 0 1rem !important;
            border: none !important;
            box-shadow: none !important;
            border-radius: 12px !important;
            width: 100% !important;
            text-transform: uppercase !important;
            letter-spacing: 0.6px !important;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# Mapping of countries to flag codes (flagcdn uses ISO 2-letter codes)
DEFAULT_FLAG_MAP = {
    # English keys (existing)
    "South Africa": "za",
    "Germany": "de",
    "Saudi Arabia": "sa",
    "Algeria": "dz",
    "Argentina": "ar",
    "Australia": "au",
    "Austria": "at",
    "Belgium": "be",
    "Brazil": "br",
    "Bosnia and Herzegovina": "ba",
    "Canada": "ca",
    "Qatar": "qa",
    "Czechia": "cz",
    "Colombia": "co",
    "Curaçao": "cw",
    "Croatia": "hr",
    "Cape Verde": "cv",
    "South Korea": "kr",
    "Ivory Coast": "ci",
    "Congo DR": "cd",
    "Egypt": "eg",
    "Ecuador": "ec",
    "Spain": "es",
    "United States": "us",
    "France": "fr",
    "Ghana": "gh",
    "Haiti": "ht",
    "Scotland": "gb-sct",
    "England": "gb-eng",
    "Iran": "ir",
    "Iraq": "iq",
    "Italy": "it",
    "Japan": "jp",
    "Jordan": "jo",
    "Morocco": "ma",
    "Mexico": "mx",
    "New Zealand": "nz",
    "Netherlands": "nl",
    "Norway": "no",
    "Paraguay": "py",
    "Portugal": "pt",
    "Panama": "pa",
    "Senegal": "sn",
    "Sweden": "se",
    "Switzerland": "ch",
    "Tunisia": "tn",
    "Turkey": "tr",
    "Uruguay": "uy",
    "Uzbekistan": "uz",
}
# Note: ALIASES removed — matching uses fuzzy/name heuristics now.

# Clear any previously cached flag map so updated defaults take effect immediately.
try:
    if hasattr(st, "session_state") and st.session_state.get("_flag_map_cache"):
        st.session_state.pop("_flag_map_cache", None)
except Exception:
    pass


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
    country_records: list[dict] = []
    try:
        with urllib.request.urlopen("https://restcountries.com/v3.1/all", timeout=10) as u:
            all_c = json.load(u)
            for c in all_c:
                cca2 = c.get("cca2")
                if not cca2:
                    continue
                # collect all possible name variants for robust matching
                name_obj = c.get("name") or {}
                common = name_obj.get("common")
                official = name_obj.get("official")
                variants = set()
                if common:
                    variants.add(common)
                if official:
                    variants.add(official)
                for alt in c.get("altSpellings", []) or []:
                    variants.add(alt)
                for t in (c.get("translations") or {}).values():
                    tn = t.get("common")
                    if tn:
                        variants.add(tn)

                # also add the variants normalized into lookup
                for nm in variants:
                    key = _normalize(nm)
                    if key:
                        name_lookup[key] = cca2.lower()

                country_records.append({
                    "cca2": cca2.lower(),
                    "variants": [ _normalize(v) for v in variants if v ],
                    "all_variants": list(variants),
                })
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
        # no explicit aliases available — try fuzzy/substring/token heuristics
        # try exact substring/token or fuzzy matching against country_records
        if not code and country_records:
            # 1) exact variant contains / is contained
            for rec in country_records:
                for v in rec["variants"]:
                    if v == norm or v in norm or norm in v:
                        code = rec["cca2"]
                        break
                if code:
                    break

        # 2) difflib close matches on normalized keys
        if not code and name_lookup:
            close = difflib.get_close_matches(norm, list(name_lookup.keys()), n=1, cutoff=0.8)
            if close:
                code = name_lookup.get(close[0])

        # 3) token overlap heuristic
        if not code and country_records:
            tokens = set(norm.split())
            best = (None, 0)
            for rec in country_records:
                for v in rec["variants"]:
                    v_tokens = set(v.split())
                    inter = len(tokens & v_tokens)
                    if inter > best[1]:
                        best = (rec["cca2"], inter)
            if best[0] and best[1] >= 1:
                code = best[0]

        if code:
            flag_map[nome] = code
        else:
            flag_map[nome] = ""

    # save cache
    st.session_state["_flag_map_cache"] = flag_map
    return flag_map
    

def init_auth_state() -> None:
    """Inicializa chaves de autenticação em `st.session_state` se não existirem.

    Evita NameError ao aceder a `st.session_state['user_id']` antes de existir.
    """
    if "user_id" not in st.session_state:
        st.session_state.user_id = None
    if "user_name" not in st.session_state:
        st.session_state.user_name = None
    if "user_email" not in st.session_state:
        st.session_state.user_email = None


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
    # If it's a date or datetime-like include time when available
    try:
        s = str(valor)
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        # if time is midnight and original string had no time, show only date
        if dt.time().hour == 0 and dt.time().minute == 0 and ("T" not in s and "+" not in s):
            return dt.strftime("%d/%m/%Y")
        return dt.strftime("%d/%m/%Y %H:%M")
    except Exception:
        try:
            if isinstance(valor, date):
                return valor.strftime("%d/%m/%Y")
        except Exception:
            pass
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
    """Special predictions section: World Cup winner and top scorer."""
    st.subheader("Special Predictions: Winner & Top Scorer")

    if not utilizador_autenticado():
        st.caption("Sign in in the sidebar to save your special predictions.")
        return

    try:
        palpite_macro = get_palpite_macro(st.session_state.user_id)
    except Exception as exc:
        st.error(f"Could not load your special predictions: {exc}")
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
            "Save special predictions",
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
            st.success("Special predictions saved successfully.")
            st.rerun()
        except Exception as exc:
                st.error(f"Error saving special predictions: {exc}")


def renderizar_ranking() -> None:
    """Ranking section: leaderboard table and per-user expanders."""
    st.subheader("Ranking — Overall Standings")

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
        [{"Name": r.get("nome"), "Points": r.get("pontos_totais", 0)} for r in ranking]
    )
    df = df.sort_values(by="Points", ascending=False).reset_index(drop=True)
    # Position column starting at 1
    df.insert(0, "Position", range(1, len(df) + 1))

    # Make a visually pleasant styled table: center, highlight top 3
    def _highlight_top(row):
        # row.name is 0-based index after reset
        if row.name < 3:
            return ["background-color: #fff8e1; font-weight: bold; text-align: center;" for _ in row]
        return ["text-align: center;" for _ in row]

    styled = (
        df.style
        .apply(_highlight_top, axis=1)
        .set_properties(**{"text-align": "center"})
        .format({"Points": "{:.0f}"})
    )

    st.dataframe(styled, use_container_width=True)

    # Expanders com detalhe por utilizador (apenas jogos finalizados aparecem no detalhe)
    for usuario in ranking:
        nome = usuario.get("nome")
        pontos = usuario.get("pontos_totais", 0)
        detalhes = usuario.get("palpites", [])
        bonus = usuario.get("bonus_aplicado", 0)

        with st.expander(f"{nome} — {pontos} pts{' (+' + str(bonus) + ' bonus)' if bonus else ''}"):
            if not detalhes:
                st.write("No finalized predictions.")
                continue
            detalhes_df = pd.DataFrame(detalhes)
            # Place match description as the first column
            detalhes_df["Match"] = detalhes_df.apply(lambda r: f"{r['equipa_casa']} vs {r['equipa_fora']}", axis=1)
            detalhes_df = detalhes_df[["Match", "palpite", "resultado_real", "pontos"]]
            detalhes_df = detalhes_df.rename(columns={"palpite": "Prediction", "resultado_real": "Actual Result", "pontos": "Points"})
            st.table(detalhes_df)


def renderizar_auth() -> None:
    """Login and register form in the sidebar."""
    with st.sidebar:
        st.header("Sign In")
        st.caption("Sign in or create an account to submit predictions.")

        tab_login, tab_registo = st.tabs(["Login", "Register"])

        with tab_login:
            with st.form("form_login", clear_on_submit=False):
                email = st.text_input("Email", placeholder="tu@email.com")
                password = st.text_input("Password", type="password")
                login_submetido = st.form_submit_button("Sign In", use_container_width=True)

            if login_submetido:
                try:
                    dados = login_utilizador(email, password)
                    st.session_state.user_id = dados["user_id"]
                    st.session_state.user_name = dados["user_name"]
                    st.session_state.user_email = dados.get("user_email")
                    st.success(f"Welcome, {dados['user_name']}!")
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
                registo_submetido = st.form_submit_button("Create account", use_container_width=True)

            if registo_submetido:
                try:
                    dados = registar_utilizador(email, password, nome)
                    st.session_state.user_id = dados["user_id"]
                    st.session_state.user_name = dados["user_name"]
                    st.session_state.user_email = dados.get("user_email")
                    st.success("Account created successfully!")
                    st.rerun()
                except AuthError as exc:
                    st.error(str(exc))
                except Exception as exc:
                    st.error(f"Error creating account: {exc}")


def renderizar_barra_lateral() -> None:
    """Shows authentication or account info depending on session state."""
    # Auth/account area in the sidebar
    if not utilizador_autenticado():
        renderizar_auth()
        return

    with st.sidebar:
        st.header("Account")
        st.markdown(f"Hello, **{st.session_state.user_name}**")
        if st.session_state.get("user_email"):
            st.caption(f"{st.session_state.get('user_email')}")
        
        if st.button("Sign Out", use_container_width=True):
            terminar_sessao()
            st.rerun()


def selecionar_pagina() -> str:
    """Show a sidebar selector and return the chosen page."""
    with st.sidebar:
        st.header("Navigation")
        # If we have a user_id but no user_email in session, attempt to fetch the email from Supabase
        if not st.session_state.get("user_email") and st.session_state.get("user_id"):
            try:
                client = get_supabase_client()
                uid = st.session_state.get("user_id")
                fetched_email = None
                # Try a few variants of the client auth API to be compatible with supabase-py versions
                try:
                    user_obj = client.auth.admin.get_user_by_id(uid)  # newer API
                    fetched_email = getattr(user_obj, "email", None) or (user_obj.user.email if getattr(user_obj, 'user', None) else None)
                except Exception:
                    try:
                        user_obj = client.auth.api.get_user_by_id(uid)  # older API
                        fetched_email = user_obj.get("email") if isinstance(user_obj, dict) else None
                    except Exception:
                        try:
                            user_obj = client.auth.get_user(uid)
                            fetched_email = getattr(user_obj, "email", None) or (user_obj.user.email if getattr(user_obj, 'user', None) else None)
                        except Exception:
                            fetched_email = None

                if fetched_email:
                    st.session_state.user_email = fetched_email
            except Exception:
                # ignore failures — fallback checks remain
                pass
        opcoes = [
            "Home",
            "Schedule",
            "Special Predictions",
            "Ranking - Overall Standings",
        ]
        # Mostrar Admin apenas para o(s) email(s) definido(s) em secrets
        admin_secret = None
        if isinstance(st.secrets, dict) or hasattr(st, "secrets"):
            admin_secret = st.secrets.get("ADMIN_EMAIL")
        # fallback: try reading local .streamlit/secrets.toml directly
        if not admin_secret:
            local = _read_local_secrets()
            if local and isinstance(local, dict):
                admin_secret = local.get("ADMIN_EMAIL")

        admin_emails = []
        if admin_secret:
            if isinstance(admin_secret, str):
                admin_emails = [e.strip() for e in admin_secret.split(",") if e.strip()]
            elif isinstance(admin_secret, (list, tuple)):
                admin_emails = list(admin_secret)

        # Primary check: match by email
        # Primary check: match by email
        if st.session_state.get("user_email") and admin_emails and st.session_state.get("user_email") in admin_emails:
            opcoes.append("Admin")
        else:
            # Fallback: allow specifying admin by user_id in secrets for robust detection
            admin_uid_secret = None
            if admin_secret:
                # allow a separate ADMIN_USER_ID value in secrets (string or CSV)
                admin_uid_secret = st.secrets.get("ADMIN_USER_ID") if isinstance(st.secrets, dict) or hasattr(st, 'secrets') else None
            if not admin_uid_secret:
                local = _read_local_secrets()
                if local and isinstance(local, dict):
                    admin_uid_secret = local.get("ADMIN_USER_ID")
            admin_uids = []
            if admin_uid_secret:
                if isinstance(admin_uid_secret, str):
                    admin_uids = [u.strip() for u in admin_uid_secret.split(",") if u.strip()]
                elif isinstance(admin_uid_secret, (list, tuple)):
                    admin_uids = list(admin_uid_secret)
            if st.session_state.get("user_id") and admin_uids and str(st.session_state.get("user_id")) in admin_uids:
                opcoes.append("Admin")

        escolha = st.radio("Go to", opcoes, index=0)
    return escolha


def renderizar_admin() -> None:
    """Admin area — only accessible to the email defined in `st.secrets['ADMIN_EMAIL']`."""
    st.subheader("Admin Area")

    if not utilizador_autenticado():
        st.warning("Sign in with the administrator account to access this area.")
        return

    admin_secret = st.secrets.get("ADMIN_EMAIL") if isinstance(st.secrets, dict) or hasattr(st, "secrets") else None
    # fallback to local secrets file if Streamlit runtime didn't load secrets
    if not admin_secret:
        local = _read_local_secrets()
        if local and isinstance(local, dict):
            admin_secret = local.get("ADMIN_EMAIL")
    # environment variable fallback (useful for deployed environments)
    if not admin_secret:
        admin_secret = os.environ.get("ADMIN_EMAIL")

    admin_emails = []
    if admin_secret:
        if isinstance(admin_secret, str):
            admin_emails = [e.strip() for e in admin_secret.split(",") if e.strip()]
        elif isinstance(admin_secret, (list, tuple)):
            admin_emails = list(admin_secret)

    # Also support ADMIN_USER_ID secret as fallback
    admin_uids = []
    admin_uid_secret = st.secrets.get("ADMIN_USER_ID") if isinstance(st.secrets, dict) or hasattr(st, 'secrets') else None
    if not admin_uid_secret:
        local = _read_local_secrets()
        if local and isinstance(local, dict):
            admin_uid_secret = local.get("ADMIN_USER_ID")
    # environment variable fallback
    if not admin_uid_secret:
        admin_uid_secret = os.environ.get("ADMIN_USER_ID")
    if admin_uid_secret:
        if isinstance(admin_uid_secret, str):
            admin_uids = [u.strip() for u in admin_uid_secret.split(",") if u.strip()]
        elif isinstance(admin_uid_secret, (list, tuple)):
            admin_uids = list(admin_uid_secret)

    if not admin_emails and not admin_uids:
        st.warning("You are not authorized to access this page.")
        return

    # authorize if email matches or user_id matches
    if not ((st.session_state.get("user_email") and st.session_state.get("user_email") in admin_emails) or (st.session_state.get("user_id") and str(st.session_state.get("user_id")) in admin_uids)):
        st.warning("You are not authorized to access this page.")
        return

    client = get_supabase_client()

    st.markdown("**Insert / Update match result**")
    try:
        jogos = get_jogos()
    except Exception as exc:
        st.error(f"Erro ao carregar jogos: {exc}")
        return

    if jogos:
        escolhas = [f"{j['id']} — {j.get('equipa_casa','?')} vs {j.get('equipa_fora','?')} ({formatar_info_jogo(j)})" for j in jogos]
        idx = st.selectbox("Choose match", range(len(escolhas)), format_func=lambda i: escolhas[i])
        jogo = jogos[idx]
        with st.form("form_resultado"):
            golos_casa = st.number_input("Home goals (actual)", min_value=0, value=int(jogo.get("golos_casa_real") or 0), key="admin_golos_casa")
            golos_fora = st.number_input("Away goals (actual)", min_value=0, value=int(jogo.get("golos_fora_real") or 0), key="admin_golos_fora")
            guardar_res = st.form_submit_button("Save Result")

        if guardar_res:
            try:
                # update official result for the match
                client.table("jogos").update({"golos_casa_real": int(golos_casa), "golos_fora_real": int(golos_fora)}).eq("id", jogo["id"]).execute()
            except Exception as exc:
                st.error(f"Error saving result: {exc}")
            else:
                # After saving the official result, update all user predictions for this match with calculated points
                try:
                    palpites_resp = client.table("palpites").select("id, utilizador_id, golos_casa_palpite, golos_fora_palpite").eq("jogo_id", jogo["id"]).execute()
                    palpites_list = palpites_resp.data or []
                except Exception as exc:
                    st.warning(f"Result saved but failed to load predictions for scoring: {exc}")
                    st.rerun()

                updated = 0
                for p in palpites_list:
                    try:
                        p_casa = int(p.get("golos_casa_palpite") or 0)
                        p_fora = int(p.get("golos_fora_palpite") or 0)
                        pontos = calcular_pontos_jogo(p_casa, p_fora, int(golos_casa), int(golos_fora))
                        resp = client.table("palpites").update({"pontos": pontos}).eq("id", p["id"]).execute()
                        if resp and getattr(resp, "data", None):
                            updated += 1
                    except Exception:
                        # skip failures per-row
                        pass

                st.success(f"Result saved and updated {updated} prediction(s) with points.")
                st.rerun()

            # If jogo id is greater than 72, allow editing the team names
            try:
                jogo_id_val = int(jogo.get("id"))
            except Exception:
                jogo_id_val = None

            if jogo_id_val and jogo_id_val > 72:
                st.markdown("---")
                st.markdown("**Edit teams for this match**")
                with st.form(f"form_edit_teams_{jogo.get('id')}"):
                    new_casa = st.text_input("Home Team Name", value=str(jogo.get("equipa_casa") or ""))
                    new_fora = st.text_input("Away Team Name", value=str(jogo.get("equipa_fora") or ""))
                    guardar_equipas = st.form_submit_button("Save Teams")

                if guardar_equipas:
                    try:
                        payload = {
                            "equipa_casa": new_casa.strip(),
                            "equipa_fora": new_fora.strip(),
                        }
                        client.table("jogos").update(payload).eq("id", jogo.get("id")).execute()
                        st.success("Teams updated successfully.")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Error updating teams: {exc}")

    # (Create new match removed: admin page now only updates existing match results)


def renderizar_jogo_somente_leitura(jogo: dict[str, Any]) -> None:
    """Display a match without prediction inputs."""
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

    # compact separator handled by CSS; avoid Streamlit's default divider


def renderizar_formulario_palpites(jogos: list[dict[str, Any]]) -> None:
    """Global form with inline predictions for all matches."""
    try:
        palpites_existentes = get_palpites_utilizador(st.session_state.user_id)
    except Exception as exc:
        st.error(f"Could not load your predictions: {exc}")
        return
    # build dynamic flag map from DB
    flag_map = build_flag_map_from_db()

    palpites_submetidos: list[dict[str, int]] = []
    with st.form("form_palpites"):
        # removed top sticky save; per-tab save buttons will appear after each jornada's matches
        # group matches by the 'jornada' column (matchday)
        from collections import defaultdict

        jogos_por_jornada: dict[str, list[dict]] = defaultdict(list)
        for j in jogos:
            chave = j.get("jornada") or j.get("matchday") or j.get("round") or ""
            jogos_por_jornada[str(chave)].append(j)

        # order jornadas with sensible tournament order: numeric matchdays first, then knockout rounds with final last
        def _j_key(k: str):
            """Return a sortable key for jornada labels.

            Ordering desired:
            - Matchday 1, Matchday 2, Matchday 3, ... (numeric matchdays ascending)
            - Round of 32
            - Round of 16
            - Quarter-finals
            - Semi-finals
            - Third place play-off
            - Final
            """
            s = str(k).strip()
            sl = s.lower()
            if s == "":
                return (9999, 0, "")

            # numeric matchday detection: digit plus 'matchday' or 'jornada' or plain number
            m = re.search(r"(\d+)", s)
            if m and ("matchday" in sl or "jornada" in sl or sl.isdigit()):
                return (0, int(m.group(1)), sl)

            # explicit keyword mapping to ensure the desired tournament order
            order_keywords = [
                ("round of 32", 1),
                ("round 32", 1),
                ("round of 16", 2),
                ("round 16", 2),
                ("quarter", 3),
                ("quart", 3),
                ("semi", 4),
                ("semif", 4),
                ("third", 5),
                ("third place", 5),
                ("play-off", 5),
                ("playoff", 5),
                ("final", 6),
            ]
            for kw, rank in order_keywords:
                if kw in sl:
                    return (100 + rank, 0, sl)

            # groups / generic matchdays without a number should appear before knockouts
            if "group" in sl or "grupo" in sl or "matchday" in sl or "jornada" in sl:
                return (0, 999, sl)

            # Fallback: place after known items but before unknown final ones
            return (1000, 0, sl)

        jornadas = sorted(jogos_por_jornada.keys(), key=_j_key)

        # create tabs inside the single form; each tab will include its own Save button at the bottom
        tabs = st.tabs([str(j) if str(j) else "All" for j in jornadas])
        for idx, jlabel in enumerate(jornadas):
            tab = tabs[idx]
            with tab:
                # show counts below tabs for this jornada
                rows = jogos_por_jornada[jlabel]
                total = len(rows)
                with_result = sum(1 for r in rows if formatar_resultado_real(r) is not None)
                st.markdown(
                    f'<div style="color:#6B7280; margin-bottom:0.25rem;">Matches: <strong>{total}</strong> · Completed: <strong>{with_result}</strong></div>',
                    unsafe_allow_html=True,
                )

                for jogo in rows:
                    jogo_id = jogo["id"]
                    palpite = palpites_existentes.get(jogo_id, {})

                    # visual wrapper (card)
                    st.markdown(f'<div class="jogo-card">', unsafe_allow_html=True)
                    st.markdown(f'<p class="jogo-meta">{formatar_info_jogo(jogo)}</p>', unsafe_allow_html=True)

                    # layout with 5 columns so flags are at the card edges and names sit between flag and central score
                    col_flag_left, col_name_left, col_sep, col_name_right, col_flag_right = st.columns([1, 3.6, 0.4, 3.6, 1])

                    # left flag
                    equipe_casa = jogo.get("equipa_casa", "—")
                    codigo_casa = flag_map.get(equipe_casa, "")
                    with col_flag_left:
                        img_casa = (
                            f'<div class="flag-wrapper flag-left"><img class="flag-icon" src="https://flagcdn.com/64x48/{codigo_casa.lower()}.png" width="64" height="48" onerror="if(!this.dataset.t1){{this.dataset.t1=1;this.src=\'https://flagcdn.com/{codigo_casa.lower()}.svg\';}}else{{this.onerror=null;this.src=\'https://flagcdn.com/64x48/gb.png\';}}"/></div>'
                            if codigo_casa
                            else '<div class="flag-wrapper flag-left"></div>'
                        )
                        st.markdown(img_casa, unsafe_allow_html=True)

                    # left name + input (name aligned right so it's near center)
                    with col_name_left:
                        name_sub, input_sub = st.columns([3, 1])
                        with name_sub:
                            st.markdown(f'<div style="text-align:right" class="team-block"><span class="team-name">{equipe_casa}</span></div>', unsafe_allow_html=True)
                        with input_sub:
                            # disable prediction input if real result exists
                            disabled = jogo.get("golos_casa_real") is not None and jogo.get("golos_fora_real") is not None
                            golos_casa = st.number_input(
                                    "Home goals",
                                    min_value=0,
                                    step=1,
                                    value=int(palpite.get("golos_casa") or 0),
                                    key=f"golos_casa_{jogo_id}",
                                    label_visibility="collapsed",
                                    disabled=disabled,
                                )

                    with col_sep:
                        st.markdown('<p class="jogo-separador">—</p>', unsafe_allow_html=True)

                    # right name + input (input near center, name left-aligned)
                    equipe_fora = jogo.get("equipa_fora", "—")
                    codigo_fora = flag_map.get(equipe_fora, "")
                    with col_name_right:
                        input_sub2, name_sub2 = st.columns([1, 3])
                        with input_sub2:
                            disabled = jogo.get("golos_casa_real") is not None and jogo.get("golos_fora_real") is not None
                            golos_fora = st.number_input(
                                "Away goals",
                                min_value=0,
                                step=1,
                                value=int(palpite.get("golos_fora") or 0),
                                key=f"golos_fora_{jogo_id}",
                                label_visibility="collapsed",
                                disabled=disabled,
                            )
                        with name_sub2:
                            st.markdown(f'<div style="text-align:left" class="team-block"><span class="team-name">{equipe_fora}</span></div>', unsafe_allow_html=True)

                    # right flag
                    with col_flag_right:
                        img_fora = (
                            f'<div class="flag-wrapper flag-right"><img class="flag-icon" src="https://flagcdn.com/64x48/{codigo_fora.lower()}.png" width="64" height="48" onerror="if(!this.dataset.t1){{this.dataset.t1=1;this.src=\'https://flagcdn.com/{codigo_fora.lower()}.svg\';}}else{{this.onerror=null;this.src=\'https://flagcdn.com/64x48/gb.png\';}}"/></div>'
                            if codigo_fora
                            else '<div class="flag-wrapper flag-right"></div>'
                        )
                        st.markdown(img_fora, unsafe_allow_html=True)

                    palpites_submetidos.append(
                        {
                            "jogo_id": jogo_id,
                            "golos_casa": st.session_state.get(f"golos_casa_{jogo_id}", int(palpite.get("golos_casa") or 0)),
                            "golos_fora": st.session_state.get(f"golos_fora_{jogo_id}", int(palpite.get("golos_fora") or 0)),
                        }
                    )
                    # If the match already has a real result, show it and the points for this user's palpite
                    if jogo.get("golos_casa_real") is not None and jogo.get("golos_fora_real") is not None:
                        try:
                            r_casa = int(jogo.get("golos_casa_real"))
                            r_fora = int(jogo.get("golos_fora_real"))
                        except Exception:
                            r_casa = jogo.get("golos_casa_real")
                            r_fora = jogo.get("golos_fora_real")

                        pontos_palpite = palpite.get("pontos")
                        if pontos_palpite is None:
                            try:
                                pontos_palpite = calcular_pontos_jogo(
                                    int(palpite.get("golos_casa") or 0),
                                    int(palpite.get("golos_fora") or 0),
                                    int(r_casa),
                                    int(r_fora),
                                )
                            except Exception:
                                pontos_palpite = 0

                        # show centered English text with larger font
                        st.markdown(f'<p class="resultado-real">Actual result: {int(r_casa)}-{int(r_fora)}<br>+{pontos_palpite} points</p>', unsafe_allow_html=True)
                    # do not render extra spacer when result exists
                    st.markdown('</div>', unsafe_allow_html=True)

                # One Save button per jornada (after listing all matches in this tab)
                st.markdown('<div class="save-card">', unsafe_allow_html=True)
                guardar_j = st.form_submit_button("💾 SAVE PREDICTIONS", key=f"save_{idx}_{jlabel}", use_container_width=True)
                st.markdown('</div>', unsafe_allow_html=True)

                if guardar_j:
                    try:
                        payloads = []
                        for p in palpites_submetidos:
                            jid = p["jogo_id"]
                            payloads.append({
                                "jogo_id": jid,
                                "golos_casa": int(st.session_state.get(f"golos_casa_{jid}", 0)),
                                "golos_fora": int(st.session_state.get(f"golos_fora_{jid}", 0)),
                            })
                        results = guardar_palpites_em_lote(st.session_state.user_id, payloads)
                        # Only show success when the DB returned inserted/updated rows
                        if results:
                            st.success(f"{len(results)} prediction(s) saved successfully.")
                            st.rerun()
                        else:
                            # Provide diagnostics to help debug why nothing was saved
                            st.warning(
                                "No changes were made to your predictions. Possible causes: not signed in, DB RLS/policies blocking writes, or predictions identical to existing values."
                            )
                            uid = st.session_state.get("user_id") if isinstance(st.session_state, dict) else getattr(st.session_state, "user_id", None)
                            st.markdown(f"**Debug:** user id = {uid} | payloads = {len(payloads)}")
                            # show a short preview of the payloads
                            try:
                                st.json(payloads[:10])
                            except Exception:
                                st.write(payloads[:10])
                    except Exception as exc:
                        st.error(f"Error saving predictions: {exc}")


def exibir_jogos() -> None:
    """Load matches and display schedule with inline predictions."""
    try:
        jogos = get_jogos()
    except Exception as exc:
        st.error(f"Could not load matches: {exc}")
        return

    st.subheader("Match Schedule")

    if not jogos:
        st.info("No matches registered yet.")
        return

    if utilizador_autenticado():
        renderizar_formulario_palpites(jogos)
    else:
        # group matches by jornada for read-only view as well
        from collections import defaultdict
        jogos_por_jornada: dict[str, list[dict]] = defaultdict(list)
        for j in jogos:
            chave = j.get("jornada") or j.get("matchday") or j.get("round") or ""
            jogos_por_jornada[str(chave)].append(j)

        def _j_key(k: str):
            s = str(k).strip()
            if s == "":
                return (0, 0, "")
            try:
                return (1, int(s), "")
            except Exception:
                sl = s.lower()
                if "final" in sl:
                    return (4, 0, sl)
                if "semif" in sl or "meia" in sl:
                    return (3, 0, sl)
                if "quart" in sl or "quarter" in sl:
                    return (2, 0, sl)
                if "round of 16" in sl or "oitav" in sl or "round16" in sl:
                    return (2, 1, sl)
                if "round of 32" in sl or "32" in sl:
                    return (1, 1000, sl)
                if "group" in sl or "grupo" in sl or "matchday" in sl or "jornada" in sl:
                    return (1, 0, sl)
                return (2, 50, sl)

        jornadas = sorted(jogos_por_jornada.keys(), key=_j_key)
        # build labels with counts
        tab_labels = []
        for j in jornadas:
            rows = jogos_por_jornada[j]
            total = len(rows)
            with_result = sum(1 for r in rows if formatar_resultado_real(r) is not None)
            label = str(j) if str(j) else "All"
            tab_labels.append(f"{label} ({total}/{with_result})")

        tabs = st.tabs(tab_labels)
        for idx, jlabel in enumerate(jornadas):
            with tabs[idx]:
                for jogo in jogos_por_jornada[jlabel]:
                    renderizar_jogo_somente_leitura(jogo)


init_auth_state()
pagina = selecionar_pagina()
renderizar_barra_lateral()

st.markdown('<div class="sticky-header"><h1>⚽ World Cup 2026</h1></div>', unsafe_allow_html=True)

if pagina == "Home":
    st.markdown(
        '<p class="subtitle">Welcome to the predictions app — explore World Cup 2026.</p>',
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
        # translate columns for display
        df_top3 = pd.DataFrame([{"Position": i + 1, "Name": r.get("nome"), "Points": r.get("pontos_totais", 0)} for i, r in enumerate(top3)])
        st.table(df_top3)
    else:
        st.info("No ranking data to display yet.")

elif pagina == "Schedule":
    st.markdown(
        '<p class="subtitle">Browse the schedule and submit your predictions.</p>',
        unsafe_allow_html=True,
    )
    if not utilizador_autenticado():
        st.info("Sign in in the sidebar to edit and save predictions.")
    exibir_jogos()

elif pagina == "Special Predictions":
    st.markdown(
        '<p class="subtitle">View and save your World Cup winner and top scorer predictions.</p>',
        unsafe_allow_html=True,
    )
    renderizar_previsoes_macro()

elif pagina == "Ranking - Overall Standings":
    st.markdown(
        '<p class="subtitle">Overall leaderboard of participants.</p>',
        unsafe_allow_html=True,
    )
    renderizar_ranking()

elif pagina == "Admin":
    renderizar_admin()
