"""Operations on the predictions (palpites) table."""

from typing import Any

from database.supabase_client import get_supabase_client


def calcular_pontos_jogo(p_casa: int, p_fora: int, r_casa: int | None, r_fora: int | None) -> int:
    """Calcula os pontos de um único jogo segundo as regras fornecidas.

    Rules:
    - Correct trend: +3
    - Exact goal difference (only if trend correct): +3
    - Exact home goals: +2
    - Exact away goals: +2
    Matches without real result return 0.
    """
    if r_casa is None or r_fora is None:
        return 0
    pontos = 0
    tendencia_real = 1 if r_casa > r_fora else (-1 if r_casa < r_fora else 0)
    tendencia_palpite = 1 if p_casa > p_fora else (-1 if p_casa < p_fora else 0)
    if tendencia_real == tendencia_palpite:
        pontos += 3
        # diferença de golos só conta se acertou na tendência
        if (r_casa - r_fora) == (p_casa - p_fora):
            pontos += 3
    if p_casa == r_casa:
        pontos += 2
    if p_fora == r_fora:
        pontos += 2
    return pontos


def get_ranking() -> list[dict]:
    """Compila o ranking baseado em todos os palpites e resultados reais.

    Returns a list of dicts with keys:
    - user_id, nome, pontos_totais, palpites (list of per-game details)

    Also attempts to read an optional `resultado_macro` table to obtain the
    real `vencedor_mundial` and `melhor_marcador` — if missing, bonuses are not applied.
    """
    client = get_supabase_client()

    # Load matches with real results
    jogos_resp = client.table("jogos").select(
        "id, equipa_casa, equipa_fora, golos_casa_real, golos_fora_real, fase, data"
    ).execute()
    jogos = {row["id"]: row for row in (jogos_resp.data or [])}

    # Load all predictions
    palpites_resp = client.table("palpites").select(
        "utilizador_id, jogo_id, golos_casa_palpite, golos_fora_palpite"
    ).execute()
    palpites = palpites_resp.data or []

    # Load profiles to map names
    perfis_resp = client.table("perfis").select("id, username").execute()
    perfis = {row["id"]: row.get("username") or row["id"] for row in (perfis_resp.data or [])}

    # Load macro predictions per user (vencedor_mundial, melhor_marcador)
    macro_resp = client.table("palpites_macro").select("user_id, vencedor_mundial, melhor_marcador").execute()
    macros = {row["user_id"]: row for row in (macro_resp.data or [])}

    # Attempt to obtain official macro result (optional)
    vencedor_real = None
    melhor_marcador_real = None
    try:
        res_macro = client.table("resultado_macro").select("vencedor_mundial, melhor_marcador").limit(1).execute()
        if res_macro.data:
            vencedor_real = res_macro.data[0].get("vencedor_mundial")
            melhor_marcador_real = res_macro.data[0].get("melhor_marcador")
    except Exception:
        # tabela opcional não existe ou erro — ignora bónus
        vencedor_real = None
        melhor_marcador_real = None

    # Aggregate points per user
    usuarios: dict[str, dict] = {}

    for p in palpites:
        uid = p.get("utilizador_id")
        jogo_id = p.get("jogo_id")
        if uid is None or jogo_id is None:
            continue
        jogo = jogos.get(jogo_id)
        # só conta jogos com resultado real
        if not jogo or jogo.get("golos_casa_real") is None or jogo.get("golos_fora_real") is None:
            continue

        p_casa = p.get("golos_casa_palpite")
        p_fora = p.get("golos_fora_palpite")
        try:
            p_casa = int(p_casa)
            p_fora = int(p_fora)
        except Exception:
            continue

        r_casa = jogo.get("golos_casa_real")
        r_fora = jogo.get("golos_fora_real")
        try:
            r_casa = int(r_casa)
            r_fora = int(r_fora)
        except Exception:
            # se não forem inteiros, ignora
            continue

        pontos = calcular_pontos_jogo(p_casa, p_fora, r_casa, r_fora)

        usuario = usuarios.setdefault(uid, {"user_id": uid, "nome": perfis.get(uid, uid), "pontos_totais": 0, "palpites": []})

        usuario["pontos_totais"] += pontos
        usuario["palpites"].append(
            {
                "jogo_id": jogo_id,
                "equipa_casa": jogo.get("equipa_casa"),
                "equipa_fora": jogo.get("equipa_fora"),
                "palpite": f"{p_casa} - {p_fora}",
                "resultado_real": f"{r_casa} - {r_fora}",
                "pontos": pontos,
            }
        )

    # Apply macro bonuses per user
    for uid, usuario in usuarios.items():
        macro = macros.get(uid)
        if not macro:
            continue
        bonus = 0
        if vencedor_real and macro.get("vencedor_mundial") and macro.get("vencedor_mundial") == vencedor_real:
            bonus += 50
        if melhor_marcador_real and macro.get("melhor_marcador") and macro.get("melhor_marcador") == melhor_marcador_real:
            bonus += 50
        usuario["pontos_totais"] += bonus
        usuario["bonus_aplicado"] = bonus

    # Convert to sorted list
    ranking = sorted(usuarios.values(), key=lambda u: u["pontos_totais"], reverse=True)
    return ranking


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
    # Safer upsert: don't rely on DB having a unique constraint for (utilizador_id, jogo_id).
    # Instead, fetch existing rows for this user and update them individually; insert the rest.
    jogo_ids = [p["jogo_id"] for p in palpites]
    existing_resp = (
        client.table("palpites")
        .select("id, jogo_id")
        .eq("utilizador_id", utilizador_id)
        .in_("jogo_id", jogo_ids)
        .execute()
    )
    existing = {row["jogo_id"]: row for row in (existing_resp.data or [])}

    to_update = []
    to_insert = []
    for p in payloads:
        jid = p["jogo_id"]
        if jid in existing:
            # update existing row
            to_update.append((existing[jid]["id"], p))
        else:
            to_insert.append(p)

    results: list[dict[str, Any]] = []
    # perform updates
    for row_id, p in to_update:
        try:
            resp = client.table("palpites").update({
                "golos_casa_palpite": p["golos_casa_palpite"],
                "golos_fora_palpite": p["golos_fora_palpite"],
            }).eq("id", row_id).execute()
            if resp.data:
                results.extend(resp.data)
        except Exception:
            # best-effort: skip failures and continue
            pass

    # perform bulk insert for new rows
    if to_insert:
        try:
            resp = client.table("palpites").insert(to_insert).execute()
            if resp.data:
                results.extend(resp.data)
        except Exception:
            # fallback: if bulk insert fails, attempt single inserts
            for p in to_insert:
                try:
                    r = client.table("palpites").insert(p).execute()
                    if r.data:
                        results.extend(r.data)
                except Exception:
                    pass

    return results
