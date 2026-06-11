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
