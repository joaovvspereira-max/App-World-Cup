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


def get_palpites_utilizador(utilizador_id: str) -> dict[int, dict[str, int]]:
    """Carrega os palpites de um utilizador, indexados por jogo_id."""
    client = get_supabase_client()
    response = (
        client.table("palpites")
        .select("jogo_id, golos_casa_palpite, golos_fora_palpite")
        .eq("utilizador_id", utilizador_id)
        .execute()
    )
    return {
        row["jogo_id"]: {
            "golos_casa": row["golos_casa_palpite"],
            "golos_fora": row["golos_fora_palpite"],
        }
        for row in (response.data or [])
    }


def guardar_palpites_em_lote(
    utilizador_id: str,
    palpites: list[dict[str, int]],
) -> list[dict[str, Any]]:
    """Faz upsert em lote na tabela 'palpites'."""
    if not palpites:
        return []

    client = get_supabase_client()
    payloads = [
        {
            "utilizador_id": utilizador_id,
            "jogo_id": palpite["jogo_id"],
            "golos_casa_palpite": palpite["golos_casa"],
            "golos_fora_palpite": palpite["golos_fora"],
        }
        for palpite in palpites
    ]
    response = (
        client.table("palpites")
        .upsert(payloads, on_conflict="utilizador_id,jogo_id")
        .execute()
    )
    return response.data or payloads
