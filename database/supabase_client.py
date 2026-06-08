"""Ligação à base de dados Supabase."""

import streamlit as st
from supabase import Client, create_client


@st.cache_resource
def get_supabase_client() -> Client:
    """Cria e reutiliza um cliente Supabase com credenciais do secrets.toml."""
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
    except (KeyError, FileNotFoundError) as exc:
        
        st.error(
            "Credenciais Supabase em falta. "
            "Cria `.streamlit/secrets.toml` com SUPABASE_URL e SUPABASE_KEY."
        )
        st.stop()
        raise exc

    return create_client(url, key)
