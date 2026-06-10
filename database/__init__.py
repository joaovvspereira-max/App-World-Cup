from database.auth import AuthError, login_utilizador, registar_utilizador
from database.jogos import get_jogos, jogos_para_dataframe
from database.palpites import get_palpites_utilizador, guardar_palpites_em_lote, submeter_palpite
from database.palpites_macro import (
    JOGADORES_ELITE,
    OPCAO_OUTRO,
    PAISES_ELITE,
    get_palpite_macro,
    guardar_palpite_macro,
)
from database.supabase_client import get_supabase_client

__all__ = [
    "AuthError",
    "JOGADORES_ELITE",
    "OPCAO_OUTRO",
    "PAISES_ELITE",
    "get_jogos",
    "get_palpite_macro",
    "get_palpites_utilizador",
    "get_supabase_client",
    "guardar_palpite_macro",
    "guardar_palpites_em_lote",
    "jogos_para_dataframe",
    "login_utilizador",
    "registar_utilizador",
    "submeter_palpite",
]
