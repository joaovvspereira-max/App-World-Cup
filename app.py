"""Aplicação Streamlit — Mundial 2026."""

import streamlit as st

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
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("⚽ Mundial 2026")
st.markdown(
    '<p class="subtitle">Consulta os jogos e submete o teu palpite.</p>',
    unsafe_allow_html=True,
)


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


def formulario_palpite() -> None:
    """Formulário lateral para submeter um palpite ao Jogo ID 1."""
    with st.sidebar:
        st.header("Submeter palpite")
        st.caption("Palpite para o **Jogo ID 1**")

        with st.form("form_palpite", clear_on_submit=True):
            utilizador_id = st.text_input(
                "ID do utilizador (UUID)",
                placeholder="ex: 550e8400-e29b-41d4-a716-446655440000",
                help="UUID do perfil na tabela 'perfis'.",
            )
            col_casa, col_fora = st.columns(2)
            with col_casa:
                golos_casa = st.number_input("Golos (casa)", min_value=0, step=1, value=0)
            with col_fora:
                golos_fora = st.number_input("Golos (fora)", min_value=0, step=1, value=0)

            submetido = st.form_submit_button("Submeter palpite", use_container_width=True)

        if submetido:
            if not utilizador_id.strip():
                st.error("Indica o ID do utilizador.")
                return

            try:
                submeter_palpite(
                    utilizador_id=utilizador_id.strip(),
                    jogo_id=1,
                    golos_casa=golos_casa,
                    golos_fora=golos_fora,
                )
                st.success(f"Palpite registado: {golos_casa} - {golos_fora}")
            except Exception as exc:
                st.error(f"Erro ao submeter palpite: {exc}")


formulario_palpite()
exibir_jogos()
