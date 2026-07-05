"""Operations on the predictions (palpites) table."""

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from database.supabase_client import get_supabase_client

# Matches excluded from the ranking — points are always zero for these game IDs.
JOGOS_EXCLUIDOS_RANKING: frozenset[int] = frozenset({1, 2})

# Timezone in which jogos.hora_jogo is expressed. Change if your kickoff times
# are stored in another zone (this MUST match the SQL cleanup query).
LIGA_TIMEZONE = ZoneInfo("Europe/Lisbon")

# Message shown for a finished match where the user made no prediction.
SEM_PALPITE_MSG = "0 points. No prediction was made for this match"


def _tem_palpite(p_casa: int | None, p_fora: int | None) -> bool:
    """A prediction only counts if BOTH goal values are present (not null)."""
    return p_casa is not None and p_fora is not None


def _to_int_or_none(value: Any) -> int | None:
    """Coerce to int, returning None for null/blank/'-'/invalid values."""
    if value is None:
        return None
    if isinstance(value, str) and value.strip() in ("", "-", "—"):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _kickoff_datetime(data: Any, hora: Any) -> datetime | None:
    """Build a timezone-aware kickoff datetime from jogos.data + jogos.hora_jogo.

    Returns None when either piece is missing or unparseable, in which case the
    match is treated as NOT started (so we never accidentally lock it).
    """
    if not data or not hora:
        return None
    try:
        naive = datetime.fromisoformat(f"{data}T{hora}")
    except ValueError:
        return None
    return naive.replace(tzinfo=LIGA_TIMEZONE)


def _carregar_kickoffs(client, ids: list[int]) -> dict[int, datetime | None]:
    """Load kickoff datetimes for the given match IDs."""
    if not ids:
        return {}
    resp = (
        client.table("jogos")
        .select("id, data, hora_jogo")
        .in_("id", list({i for i in ids if i is not None}))
        .execute()
    )
    return {
        row["id"]: _kickoff_datetime(row.get("data"), row.get("hora_jogo"))
        for row in (resp.data or [])
    }


def calcular_pontos_jogo(
    p_casa: int | None,
    p_fora: int | None,
    r_casa: int | None,
    r_fora: int | None,
) -> int:
    """Calcula os pontos de um único jogo segundo as regras fornecidas.

    Rules:
    - Correct trend: +3
    - Exact goal difference (only if trend correct): +3
    - Exact home goals: +2
    - Exact away goals: +2
    Matches without a real result, OR predictions without both goal values
    (null/"no prediction"), return 0.
    """
    if r_casa is None or r_fora is None:
        return 0
    if p_casa is None or p_fora is None:
        # No prediction was made for this match.
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


def atualizar_pontos_jogo(jogo_id: int, r_casa: int | None, r_fora: int | None, client=None) -> int:
    """Persist points for every prediction on a match once the real result exists."""
    if client is None:
        client = get_supabase_client()

    if jogo_id is None:
        return 0

    try:
        resp = (
            client.table("palpites")
            .select("id, golos_casa_palpite, golos_fora_palpite")
            .eq("jogo_id", jogo_id)
            .execute()
        )
    except Exception:
        return 0

    updated = 0
    for p in resp.data or []:
        try:
            p_casa = _to_int_or_none(p.get("golos_casa_palpite"))
            p_fora = _to_int_or_none(p.get("golos_fora_palpite"))
            if r_casa is None or r_fora is None:
                pontos = None
            elif p_casa is None or p_fora is None:
                pontos = 0
            else:
                pontos = calcular_pontos_jogo(p_casa, p_fora, r_casa, r_fora)

            client.table("palpites").update({"pontos": pontos}).eq("id", p["id"]).execute()
            updated += 1
        except Exception:
            continue

    return updated


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
        "id, equipa_casa, equipa_fora, golos_casa_real, golos_fora_real, fase, jornada, data"
    ).execute()
    jogos = {row["id"]: row for row in (jogos_resp.data or [])}

    # Load all predictions with their persisted points and row ids so ranking
    # can use stored values and backfill missing ones for finished matches.
    palpites_resp = client.table("palpites").select(
        "id, utilizador_id, jogo_id, golos_casa_palpite, golos_fora_palpite, pontos"
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

        # null golos => "no prediction"; kept as None instead of being skipped.
        p_casa = _to_int_or_none(p.get("golos_casa_palpite"))
        p_fora = _to_int_or_none(p.get("golos_fora_palpite"))
        tem_palpite = _tem_palpite(p_casa, p_fora)

        r_casa = _to_int_or_none(jogo.get("golos_casa_real"))
        r_fora = _to_int_or_none(jogo.get("golos_fora_real"))
        if r_casa is None or r_fora is None:
            # real result not a clean integer — skip
            continue

        # Prefer the persisted per-match points when available; fall back to
        # recomputing from the official result if the row has not been backfilled.
        pontos_salvos = p.get("pontos")
        if pontos_salvos is not None:
            try:
                pontos = int(pontos_salvos)
            except (TypeError, ValueError):
                pontos = 0
        elif jogo_id in JOGOS_EXCLUIDOS_RANKING or not tem_palpite:
            pontos = 0
        else:
            pontos = calcular_pontos_jogo(p_casa, p_fora, r_casa, r_fora)
            try:
                client.table("palpites").update({"pontos": pontos}).eq("id", p["id"]).execute()
            except Exception:
                pass

        usuario = usuarios.setdefault(uid, {"user_id": uid, "nome": perfis.get(uid, uid), "pontos_totais": 0, "palpites": []})

        usuario["pontos_totais"] += pontos
        usuario["palpites"].append(
            {
                "jogo_id": jogo_id,
                "equipa_casa": jogo.get("equipa_casa"),
                "equipa_fora": jogo.get("equipa_fora"),
                "fase": jogo.get("fase"),
                "jornada": jogo.get("jornada"),
                "palpite": f"{p_casa} - {p_fora}" if tem_palpite else "—",
                "resultado_real": f"{r_casa} - {r_fora}",
                "pontos": pontos,
                "sem_palpite": not tem_palpite,
                "mensagem": SEM_PALPITE_MSG if not tem_palpite else None,
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

    # Order each user's per-game details by match ID
    for usuario in usuarios.values():
        usuario["palpites"].sort(key=lambda d: d.get("jogo_id") or 0)

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
        .select("jogo_id, golos_casa_palpite, golos_fora_palpite, pontos")
        .eq("utilizador_id", utilizador_id)
        .execute()
    )
    return {
        row["jogo_id"]: {
            "golos_casa": row["golos_casa_palpite"],
            "golos_fora": row["golos_fora_palpite"],
            "pontos": row.get("pontos"),
        }
        for row in (response.data or [])
    }


def guardar_palpites_em_lote(
    utilizador_id: str,
    palpites: list[dict[str, int]],
) -> dict[str, Any]:
    """Persist a batch of predictions for one user, robustly and verifiably.

    Behaviour:
    - Missing/None goal values are stored as NULL ("no prediction"). A user who
      leaves a match as "-" and saves writes NULL, never 0-0.
    - A match is only written when BOTH goals are present OR both are empty
      (clearing). A half-filled row (one box typed, the other empty) is treated
      as "no prediction" and stored as NULL/NULL — it can never silently become
      0-0.
    - Matches that have ALREADY STARTED (kickoff <= now, LIGA_TIMEZONE) are
      LOCKED and skipped entirely, so a late edit never overwrites or creates
      rows for past matches.

    Returns a structured report instead of a raw row list, so the UI can tell
    the difference between "actually saved", "nothing to save", and "failed":

        {
            "ok": bool,                 # True only if every attempted write succeeded
            "saved": [jogo_id, ...],    # ids confirmed written to the DB
            "skipped_locked": [...],    # ids skipped because the match started
            "failed": [...],            # ids that could not be written
            "rows": [ ... ],            # the DB rows returned for saved predictions
        }

    Uses an upsert with on_conflict on (utilizador_id, jogo_id), which requires a
    UNIQUE constraint on those two columns. After writing, it RE-READS the rows
    to confirm the values actually landed — success is never assumed.
    """
    report: dict[str, Any] = {
        "ok": True,
        "saved": [],
        "skipped_locked": [],
        "failed": [],
        "rows": [],
    }
    if not palpites:
        report["ok"] = False  # nothing happened; let caller decide messaging
        return report

    client = get_supabase_client()

    # Resolve kickoff times so we can lock matches that already started.
    ids = [p.get("jogo_id") for p in palpites if p.get("jogo_id") is not None]
    kickoffs = _carregar_kickoffs(client, ids)
    agora = datetime.now(LIGA_TIMEZONE)

    payloads: list[dict[str, Any]] = []
    for palpite in palpites:
        jid = palpite.get("jogo_id")
        if jid is None:
            continue

        kickoff = kickoffs.get(jid)
        if kickoff is not None and agora >= kickoff:
            report["skipped_locked"].append(jid)
            continue

        casa = _to_int_or_none(palpite.get("golos_casa"))
        fora = _to_int_or_none(palpite.get("golos_fora"))

        # Half-filled => treat as no prediction (NULL/NULL). This prevents the
        # "stored 0-0 by mistake" symptom: a stray 0 in one box never produces
        # a scored 0-0 row on its own.
        if (casa is None) != (fora is None):
            casa = None
            fora = None

        payloads.append({
            "utilizador_id": utilizador_id,
            "jogo_id": jid,
            "golos_casa_palpite": casa,
            "golos_fora_palpite": fora,
        })

    if not payloads:
        # Everything was locked or invalid — not an error, but nothing saved.
        report["ok"] = len(report["skipped_locked"]) > 0
        return report

    attempted_ids = {p["jogo_id"] for p in payloads}

    # --- Primary path: one batched upsert -----------------------------------
    upsert_failed = False
    try:
        client.table("palpites").upsert(
            payloads, on_conflict="utilizador_id,jogo_id"
        ).execute()
    except Exception:
        upsert_failed = True

    # --- Fallback: per-row upsert if the batch raised -----------------------
    if upsert_failed:
        for payload in payloads:
            try:
                client.table("palpites").upsert(
                    payload, on_conflict="utilizador_id,jogo_id"
                ).execute()
            except Exception:
                # Last resort: explicit update, then insert if missing.
                jid = payload["jogo_id"]
                try:
                    existing = (
                        client.table("palpites")
                        .select("id")
                        .eq("utilizador_id", utilizador_id)
                        .eq("jogo_id", jid)
                        .limit(1)
                        .execute()
                    )
                    if existing and getattr(existing, "data", None):
                        client.table("palpites").update({
                            "golos_casa_palpite": payload["golos_casa_palpite"],
                            "golos_fora_palpite": payload["golos_fora_palpite"],
                        }).eq("utilizador_id", utilizador_id).eq(
                            "jogo_id", jid
                        ).execute()
                    else:
                        client.table("palpites").insert(payload).execute()
                except Exception:
                    pass  # verified below regardless

    # --- Verification: re-read what is actually in the DB -------------------
    # Success is confirmed by reading the rows back and comparing values, so we
    # never report a save that did not persist.
    verified_rows: list[dict[str, Any]] = []
    try:
        check = (
            client.table("palpites")
            .select("id, jogo_id, golos_casa_palpite, golos_fora_palpite")
            .eq("utilizador_id", utilizador_id)
            .in_("jogo_id", list(attempted_ids))
            .execute()
        )
        verified_rows = check.data or []
    except Exception:
        verified_rows = []

    db_by_id = {r["jogo_id"]: r for r in verified_rows}
    want_by_id = {p["jogo_id"]: p for p in payloads}

    # If a real result is already known for the match, persist the computed
    # points in the predictions table immediately so ranking reads are accurate.
    try:
        jogos_resp = (
            client.table("jogos")
            .select("id, golos_casa_real, golos_fora_real")
            .in_("id", list(attempted_ids))
            .execute()
        )
        jogos_por_id = {row["id"]: row for row in (jogos_resp.data or [])}
    except Exception:
        jogos_por_id = {}

    for jid, want in want_by_id.items():
        got = db_by_id.get(jid)
        if (
            got is not None
            and got.get("golos_casa_palpite") == want["golos_casa_palpite"]
            and got.get("golos_fora_palpite") == want["golos_fora_palpite"]
        ):
            report["saved"].append(jid)
            report["rows"].append(got)

            jogo = jogos_por_id.get(jid) or {}
            r_casa = _to_int_or_none(jogo.get("golos_casa_real"))
            r_fora = _to_int_or_none(jogo.get("golos_fora_real"))
            if r_casa is not None and r_fora is not None:
                try:
                    p_casa = _to_int_or_none(got.get("golos_casa_palpite"))
                    p_fora = _to_int_or_none(got.get("golos_fora_palpite"))
                    if p_casa is None or p_fora is None:
                        pontos = 0
                    else:
                        pontos = calcular_pontos_jogo(p_casa, p_fora, r_casa, r_fora)
                    client.table("palpites").update({"pontos": pontos}).eq("id", got["id"]).execute()
                except Exception:
                    pass
        else:
            report["failed"].append(jid)

    report["ok"] = len(report["failed"]) == 0
    return report


def get_palpites_por_jogo() -> dict[int, list[dict]]:
    """Returns predictions grouped by jogo_id, each entry includes user_id, nome,
    palpite (formatted "X - Y", or "—" when no prediction was made) and pontos
    (None if match has no real result yet).

    Used by the match schedule to display other users' predictions and the
    points they scored for each finished match. Entries where both goal values
    are null carry sem_palpite=True and a `mensagem` for finished matches.
    """
    client = get_supabase_client()

    # Load all predictions
    palpites_resp = client.table("palpites").select(
        "utilizador_id, jogo_id, golos_casa_palpite, golos_fora_palpite"
    ).execute()
    palpites = palpites_resp.data or []

    # Load matches (we only need IDs and real results here)
    jogos_resp = client.table("jogos").select(
        "id, golos_casa_real, golos_fora_real"
    ).execute()
    jogos = {row["id"]: row for row in (jogos_resp.data or [])}

    # Load profiles to map names
    perfis_resp = client.table("perfis").select("id, username").execute()
    perfis = {row["id"]: row.get("username") or row["id"] for row in (perfis_resp.data or [])}

    result: dict[int, list[dict]] = {}
    for p in palpites:
        jogo_id = p.get("jogo_id")
        uid = p.get("utilizador_id")
        if jogo_id is None or uid is None:
            continue

        # null golos => "no prediction"; kept as None instead of being skipped.
        p_casa = _to_int_or_none(p.get("golos_casa_palpite"))
        p_fora = _to_int_or_none(p.get("golos_fora_palpite"))
        tem_palpite = _tem_palpite(p_casa, p_fora)

        jogo = jogos.get(jogo_id) or {}
        r_casa = jogo.get("golos_casa_real")
        r_fora = jogo.get("golos_fora_real")
        jogo_terminado = r_casa is not None and r_fora is not None

        if jogo_terminado:
            if jogo_id in JOGOS_EXCLUIDOS_RANKING or not tem_palpite:
                pontos = 0
            else:
                try:
                    pontos = calcular_pontos_jogo(p_casa, p_fora, int(r_casa), int(r_fora))
                except Exception:
                    pontos = 0
        else:
            pontos = None

        result.setdefault(jogo_id, []).append({
            "user_id": uid,
            "nome": perfis.get(uid, uid),
            "palpite": f"{p_casa} - {p_fora}" if tem_palpite else "—",
            "pontos": pontos,
            "sem_palpite": not tem_palpite,
            "mensagem": SEM_PALPITE_MSG if (not tem_palpite and jogo_terminado) else None,
        })

    # Sort each list by points descending (None goes last)
    for jogo_id in result:
        result[jogo_id] = sorted(
            result[jogo_id],
            key=lambda x: (x.get("pontos") is None, -(x.get("pontos") or 0)),
        )

    return result