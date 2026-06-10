"""Aplicação Streamlit — Mundial 2026."""

from datetime import date, datetime
from typing import Any

import pandas as pd
import streamlit as st

from database.auth import AuthError, login_utilizador, registar_utilizador
from database.jogos import get_jogos
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
            margin-bottom: 0.25rem;
        }
        .jogo-linha {
            margin-bottom: 1.25rem;
        }
        .jogo-equipa {
            font-weight: 600;
            text-align: center;
            padding-top: 0.35rem;
        }
        .jogo-separador {
            text-align: center;
            font-weight: 700;
            padding-top: 0.35rem;
            color: #5C6B7A;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


def init_auth_state() -> None:
    """Garante que o estado de autenticação existe na sessão."""
    if "user_id" not in st.session_state:
        st.session_state.user_id = None
    if "user_name" not in st.session_state:
        st.session_state.user_name = None


def utilizador_autenticado() -> bool:
    """Indica se existe um utilizador com sessão ativa."""
    return bool(st.session_state.get("user_id"))


def terminar_sessao() -> None:
    """Remove os dados de autenticação da sessão."""
    st.session_state.user_id = None
    st.session_state.user_name = None


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
                    st.success("Conta criada com sucesso!")
                    st.rerun()
                except AuthError as exc:
                    st.error(str(exc))
                except Exception as exc:
                    st.error(f"Erro ao criar conta: {exc}")


def renderizar_barra_lateral() -> None:
    """Mostra autenticação ou informação da conta consoante o estado da sessão."""
    if not utilizador_autenticado():
        renderizar_auth()
        return

    with st.sidebar:
        st.header("Conta")
        st.markdown(f"Olá, **{st.session_state.user_name}**")
        if st.button("Terminar sessão", use_container_width=True):
            terminar_sessao()
            st.rerun()


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

    palpites_submetidos: list[dict[str, int]] = []
    with st.form("form_palpites"):
        for jogo in jogos:
            jogo_id = jogo["id"]
            palpite = palpites_existentes.get(jogo_id, {})

            # Card container
            with st.container():
                st.markdown(
                    f'<p class="jogo-meta">{formatar_info_jogo(jogo)}</p>',
                    unsafe_allow_html=True,
                )

                col_casa, col_golos_casa, col_sep, col_golos_fora, col_fora = st.columns(
                    [3, 1, 0.4, 1, 3]
                )

                with col_casa:
                    st.markdown(
                        f'<p class="jogo-equipa">{jogo.get("equipa_casa", "—")}</p>',
                        unsafe_allow_html=True,
                    )
                with col_golos_casa:
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
                with col_golos_fora:
                    golos_fora = st.number_input(
                        "Golos fora",
                        min_value=0,
                        step=1,
                        value=int(palpite.get("golos_fora") or 0),
                        key=f"golos_fora_{jogo_id}",
                        label_visibility="collapsed",
                    )
                with col_fora:
                    st.markdown(
                        f'<p class="jogo-equipa">{jogo.get("equipa_fora", "—")}</p>',
                        unsafe_allow_html=True,
                    )

            palpites_submetidos.append(
                {
                    "jogo_id": jogo_id,
                    "golos_casa": st.session_state.get(f"golos_casa_{jogo_id}", int(palpite.get("golos_casa") or 0)),
                    "golos_fora": st.session_state.get(f"golos_fora_{jogo_id}", int(palpite.get("golos_fora") or 0)),
                }
            )
            st.divider()

        guardar = st.form_submit_button("Guardar Palpites", use_container_width=True)

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
renderizar_barra_lateral()

st.title("⚽ Mundial 2026")
st.markdown(
    '<p class="subtitle">Consulta os jogos e submete os teus palpites.</p>',
    unsafe_allow_html=True,
)

if not utilizador_autenticado():
    st.info("Inicia sessão na barra lateral para editar e guardar palpites.")

renderizar_previsoes_macro()
st.divider()
renderizar_ranking()
st.divider()
exibir_jogos()
