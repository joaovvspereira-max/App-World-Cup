from database.auth import AuthError, login_utilizador, registar_utilizador
from database.jogos import get_jogos, jogos_para_dataframe
from database.palpites import get_palpites_utilizador, guardar_palpites_em_lote, submeter_palpite
from database.supabase_client import get_supabase_client

__all__ = [
    "AuthError",
    "get_jogos",
    "get_palpites_utilizador",
    "get_supabase_client",
    "guardar_palpites_em_lote",
    "jogos_para_dataframe",
    "login_utilizador",
    "registar_utilizador",
    "submeter_palpite",
]
