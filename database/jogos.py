"""Operações sobre a tabela de jogos."""

from typing import Any

import pandas as pd

from database.supabase_client import get_supabase_client


def get_jogos() -> list[dict[str, Any]]:
    """Carrega todos os jogos da base de dados, ordenados por ID."""
    client = get_supabase_client()
    response = client.table("jogos").select("*").order("id").execute()
    return response.data or []


def jogos_para_dataframe(jogos: list[dict[str, Any]]) -> pd.DataFrame:
    """Converte a lista de jogos num DataFrame formatado para exibição."""
    if not jogos:
        return pd.DataFrame(
            columns=[
                "ID",
                "Equipa Casa",
                "Equipa Fora",
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
            "equipa_casa": "Equipa Casa",
            "equipa_fora": "Equipa Fora",
            "fase": "Fase",
        }
    )[["ID", "Equipa Casa", "Equipa Fora", "Resultado", "Fase"]]
