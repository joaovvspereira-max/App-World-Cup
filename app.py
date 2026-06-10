"""Aplicação Streamlit — Mundial 2026."""

import streamlit as st

from database.auth import AuthError, login_utilizador, registar_utilizador
from database.jogos import get_jogos, jogos_para_dataframe
from database.palpites import submeter_palpite

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


def formulario_palpite() -> None:
    """Formulário lateral para submeter um palpite ao Jogo ID 1."""
    with st.sidebar:
        st.divider()
        st.header("Submeter palpite")
        st.caption(f"Palpite para o **Jogo ID 1** · {st.session_state.user_name}")

        with st.form("form_palpite", clear_on_submit=True):
            col_casa, col_fora = st.columns(2)
            with col_casa:
                golos_casa = st.number_input("Golos (casa)", min_value=0, step=1, value=0)
            with col_fora:
                golos_fora = st.number_input("Golos (fora)", min_value=0, step=1, value=0)

            submetido = st.form_submit_button("Submeter palpite", use_container_width=True)

        if submetido:
            try:
                submeter_palpite(
                    utilizador_id=st.session_state.user_id,
                    jogo_id=1,
                    golos_casa=golos_casa,
                    golos_fora=golos_fora,
                )
                st.success(f"Palpite registado: {golos_casa} - {golos_fora}")
            except Exception as exc:
                st.error(f"Erro ao submeter palpite: {exc}")


def renderizar_barra_lateral() -> None:
    """Mostra autenticação ou funcionalidades de edição consoante o estado da sessão."""
    if not utilizador_autenticado():
        renderizar_auth()
        return

    with st.sidebar:
        st.header("Conta")
        st.markdown(f"Olá, **{st.session_state.user_name}**")
        if st.button("Terminar sessão", use_container_width=True):
            terminar_sessao()
            st.rerun()

    formulario_palpite()


def exibir_jogos() -> None:
    """Carrega os jogos da base de dados e exibe-os numa tabela."""
    try:
        jogos = get_jogos()
    except Exception as exc:
        st.error(f"Não foi possível carregar os jogos: {exc}")
        return

    df = jogos_para_dataframe(jogos)

    col1, col2 = st.columns(2)
    col1.metric("Total de jogos", len(df))
    col2.metric("Jogos com resultado", int((df["Resultado"] != "—").sum()))

    st.subheader("Calendário de jogos")
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "ID": st.column_config.NumberColumn("ID", width="small"),
            "Equipa Casa": st.column_config.TextColumn("Equipa Casa"),
            "Equipa Fora": st.column_config.TextColumn("Equipa Fora"),
            "Resultado": st.column_config.TextColumn("Resultado"),
            "Fase": st.column_config.TextColumn("Fase"),
        },
    )


init_auth_state()
renderizar_barra_lateral()

st.title("⚽ Mundial 2026")
st.markdown(
    '<p class="subtitle">Consulta os jogos e submete o teu palpite.</p>',
    unsafe_allow_html=True,
)

if not utilizador_autenticado():
    st.info("Inicia sessão na barra lateral para submeter palpites.")

exibir_jogos()
