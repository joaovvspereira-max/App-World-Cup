"""Operations on the matches table."""

from typing import Any

import pandas as pd

from database.supabase_client import get_supabase_client


def get_jogos() -> list[dict[str, Any]]:
    """Load all matches from the database, ordered by ID."""
    client = get_supabase_client()
    response = client.table("jogos").select("*").order("id").execute()
    return response.data or []


def jogos_para_dataframe(jogos: list[dict[str, Any]]) -> pd.DataFrame:
    """Convert the list of matches into a DataFrame formatted for display."""
    if not jogos:
        return pd.DataFrame(
            columns=[
                "ID",
                "Home Team",
                "Away Team",
                "Resultado",
                "Fase",
            ]
        )

    df = pd.DataFrame(jogos)

    def formatar_resultado(row: pd.Series) -> str:
        if pd.isna(row["golos_casa_real"]) or pd.isna(row["golos_fora_real"]):
            return "—"
        return f"{int(row['golos_casa_real'])} - {int(row['golos_fora_real'])}"

    df["Resultado"] = df.apply(formatar_resultado, axis=1)

    return df.rename(
        columns={
            "id": "ID",
            "equipa_casa": "Home Team",
            "equipa_fora": "Away Team",
            "fase": "Fase",
        }
    )[["ID", "Equipa Casa", "Equipa Fora", "Resultado", "Fase"]]
