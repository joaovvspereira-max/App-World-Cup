"""Operações sobre a tabela de palpites."""

from typing import Any

from database.supabase_client import get_supabase_client


def submeter_palpite(
    utilizador_id: str,
    jogo_id: int,
    golos_casa: int,
    golos_fora: int,
) -> dict[str, Any]:
    """Insere um palpite na tabela 'palpites'."""
    client = get_supabase_client()
    payload = {
        "utilizador_id": utilizador_id,
        "jogo_id": jogo_id,
        "golos_casa_palpite": golos_casa,
        "golos_fora_palpite": golos_fora,
    }
    response = client.table("palpites").insert(payload).execute()
    return response.data[0] if response.data else payload
