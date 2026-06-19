"""Special predictions: World Cup winner and top scorer."""

from datetime import datetime, timezone
from typing import Any

from database.supabase_client import get_supabase_client

OPCAO_OUTRO = "Other..."

PAISES_ELITE = [
    "Portugal",
    "Brazil",
    "France",
    "Argentina",
    "Netherlands",
    "Belgium",
    "Germany",
    "Spain",
    "England",
    "Croatia",
    "Uruguay",
    "United States",
    "Mexico",
    OPCAO_OUTRO,
]

JOGADORES_ELITE = [
    "Michael Olise",
    "Ousmane Dembelé",
    "Kylian Mbappé",
    "Vinicius Jr",
    "Erling Haaland",
    "Jude Bellingham",
    "Harry Kane",
    "Lionel Messi",
    "Romelu Lukaku",
    "Lamine Yamal",
    "Cristiano Ronaldo",
    "Mikel Oyarzabal",
    "Pedri",
    "Jamal Musiala",
    "Neymar",
    "Raphinha",
    "Bruno Fernandes",
    OPCAO_OUTRO,
]


def get_palpite_macro(user_id: str) -> dict[str, Any] | None:
    """Load the single macro prediction record for the user."""
    client = get_supabase_client()
    response = (
        client.table("palpites_macro")
        .select("id, user_id, vencedor_mundial, melhor_marcador, atualizado_em")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else None


def guardar_palpite_macro(
    user_id: str,
    vencedor_mundial: str,
    melhor_marcador: str,
) -> dict[str, Any]:
    """Insert or update the user's single macro prediction record."""
    client = get_supabase_client()
    payload = {
        "user_id": user_id,
        "vencedor_mundial": vencedor_mundial.strip(),
        "melhor_marcador": melhor_marcador.strip(),
        "atualizado_em": datetime.now(timezone.utc).isoformat(),
    }
    response = (
        client.table("palpites_macro")
        .upsert(payload, on_conflict="user_id")
        .execute()
    )
    return response.data[0] if response.data else payload


def get_todos_palpites_macro() -> list[dict[str, Any]]:
    """Return every user's macro prediction together with their display name.

    Mirrors how the match pages build "other users' predictions": names come
    from the `perfis` table (id -> username), and palpites_macro.user_id maps
    to perfis.id (the same join get_ranking already uses for macro bonuses).

    Each entry has the keys:
    user_id, nome, vencedor_mundial, melhor_marcador, atualizado_em.
    """
    client = get_supabase_client()

    # Load all macro predictions.
    response = (
        client.table("palpites_macro")
        .select("user_id, vencedor_mundial, melhor_marcador, atualizado_em")
        .execute()
    )
    rows = response.data or []

    # Load profiles to map user_id -> display name (same source as match pages).
    perfis_resp = client.table("perfis").select("id, username").execute()
    perfis = {
        row["id"]: row.get("username") or row["id"]
        for row in (perfis_resp.data or [])
    }

    resultado = [
        {
            "user_id": row.get("user_id"),
            "nome": perfis.get(row.get("user_id"), row.get("user_id")),
            "vencedor_mundial": row.get("vencedor_mundial"),
            "melhor_marcador": row.get("melhor_marcador"),
            "atualizado_em": row.get("atualizado_em"),
        }
        for row in rows
    ]

    # Stable display order: alphabetical by name.
    resultado.sort(key=lambda x: str(x.get("nome") or "").lower())
    return resultado