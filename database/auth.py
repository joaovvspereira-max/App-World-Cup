"""Autenticação via Supabase Auth."""

from typing import Any

from database.supabase_client import get_supabase_client


class AuthError(Exception):
    """Erro de autenticação com mensagem amigável."""


def registar_utilizador(email: str, password: str, nome: str) -> dict[str, Any]:
    """Regista um novo utilizador no Supabase Auth e cria o perfil associado."""
    email = email.strip()
    nome = nome.strip()

    if not email or not password or not nome:
        raise AuthError("Preenche email, password e nome.")

    client = get_supabase_client()
    response = client.auth.sign_up(
        {
            "email": email,
            "password": password,
            "options": {"data": {"nome": nome}},
        }
    )

    if not response.user:
        raise AuthError("Não foi possível criar a conta. Verifica os dados introduzidos.")

    user_id = str(response.user.id)

    try:
        client.table("perfis").insert({"id": user_id, "username": nome}).execute()
    except Exception as exc:
        raise AuthError(f"Conta criada, mas falhou ao guardar o perfil: {exc}") from exc

    return {"user_id": user_id, "user_name": nome}


def login_utilizador(email: str, password: str) -> dict[str, Any]:
    """Autentica um utilizador existente e devolve o UUID e o nome."""
    email = email.strip()

    if not email or not password:
        raise AuthError("Preenche email e password.")

    client = get_supabase_client()
    response = client.auth.sign_in_with_password({"email": email, "password": password})

    if not response.user:
        raise AuthError("Credenciais inválidas.")

    user_id = str(response.user.id)
    user_name = _obter_nome_utilizador(client, user_id, response.user.user_metadata, email)

    return {"user_id": user_id, "user_name": user_name}


def _obter_nome_utilizador(client, user_id: str, metadata: dict | None, email: str) -> str:
    """Obtém o nome a partir da tabela perfis ou dos metadados do Auth."""
    try:
        perfil = client.table("perfis").select("username").eq("id", user_id).single().execute()
        if perfil.data and perfil.data.get("username"):
            return perfil.data["username"]
    except Exception:
        pass

    if metadata and metadata.get("nome"):
        return metadata["nome"]

    return email.split("@")[0]
