"""Authentication via Supabase Auth."""

from typing import Any

from database.supabase_client import get_supabase_client


class AuthError(Exception):
    """Authentication error with a user-friendly message."""


def registar_utilizador(email: str, password: str, nome: str) -> dict[str, Any]:
    """Register a new user in Supabase Auth and create the associated profile."""
    email = email.strip()
    nome = nome.strip()

    if not email or not password or not nome:
        raise AuthError("Fill email, password and name.")

    client = get_supabase_client()
    response = client.auth.sign_up(
        {
            "email": email,
            "password": password,
            "options": {"data": {"nome": nome}},
        }
    )

    if not response.user:
        raise AuthError("Could not create account. Check the provided details.")

    user_id = str(response.user.id)

    try:
        client.table("perfis").insert({"id": user_id, "username": nome}).execute()
    except Exception as exc:
        raise AuthError(f"Account created, but failed to save profile: {exc}") from exc

    return {"user_id": user_id, "user_name": nome, "user_email": email}


def login_utilizador(email: str, password: str) -> dict[str, Any]:
    """Authenticate an existing user and return the UUID and name."""
    email = email.strip()

    if not email or not password:
        raise AuthError("Fill email and password.")

    client = get_supabase_client()
    response = client.auth.sign_in_with_password({"email": email, "password": password})

    if not response.user:
        raise AuthError("Invalid credentials.")

    user_id = str(response.user.id)
    user_name = _obter_nome_utilizador(client, user_id, response.user.user_metadata, email)

    return {"user_id": user_id, "user_name": user_name, "user_email": email}


def _obter_nome_utilizador(client, user_id: str, metadata: dict | None, email: str) -> str:
    """Get the name from the profiles table or from Auth metadata."""
    try:
        perfil = client.table("perfis").select("username").eq("id", user_id).single().execute()
        if perfil.data and perfil.data.get("username"):
            return perfil.data["username"]
    except Exception:
        pass

    if metadata and metadata.get("nome"):
        return metadata["nome"]

    return email.split("@")[0]
