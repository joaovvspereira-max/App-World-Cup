"""Supabase database connection."""

import streamlit as st
from supabase import Client, create_client


@st.cache_resource
def get_supabase_client() -> Client:
    """Create and reuse a Supabase client using credentials from secrets.toml."""
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
    except (KeyError, FileNotFoundError) as exc:
        st.error(
            "Supabase credentials missing. "
            "Create `.streamlit/secrets.toml` with SUPABASE_URL and SUPABASE_KEY."
        )
        st.stop()
        raise exc

    return create_client(url, key)
