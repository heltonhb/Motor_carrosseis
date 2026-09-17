"""
instagram_service.py — Integração com Instagram Graph API (V1).

Busca métricas de posts do Instagram Business Account e transforma no formato
esperado pelo app (mesmo schema do persistence.metrica).

Pré-requisitos:
- Token de acesso de longa duração (válido por 90 dias)
- Instagram Business Account ID
- Permissões: instagram_basic, pages_show_list, pages_read_engagement

Exemplo de uso:
    from instagram_service import fetch_post_metrics
    metrics = fetch_post_metrics(token, account_id, post_ids=["123", "456"])
"""

from __future__ import annotations

import json
import urllib.request
import urllib.error
from datetime import datetime
from typing import Any


def fetch_post_metrics(
    access_token: str,
    ig_account_id: str,
    post_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    """
    Busca métricas de posts específicos do Instagram Business Account.

    Args:
        access_token: Token de acesso de longa duração da API.
        ig_account_id: ID da conta Business do Instagram.
        post_ids: Lista de IDs de posts a buscar. Se None, busca todos.

    Returns:
        Lista de dicts com as métricas no formato esperado pelo app.
    """
    base_url = "https://graph.facebook.com/v21.0"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    def make_request(url: str) -> dict[str, Any]:
        """Faz requisição HTTP GET e retorna JSON."""
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            return {"error": f"HTTP {e.code}: {e.read().decode('utf-8')}"}

    def get_user_id(access_token: str) -> str | None:
        """Obtém o ID do usuário do token."""
        url = f"{base_url}/me?fields=id&access_token={access_token}"
        data = make_request(url)
        return data.get("id")

    def get_ig_media_ids(account_id: str) -> list[str]:
        """Obtém todos os IDs de mídia da conta."""
        url = f"{base_url}/{account_id}/media?fields=id&access_token={access_token}"
        data = make_request(url)
        if "error" in data:
            return []
        return [item["id"] for item in data.get("data", [])]

    if not post_ids:
        post_ids = get_ig_media_ids(ig_account_id)

    metrics: list[dict[str, Any]] = []

    for media_id in post_ids:
        media_url = f"{base_url}/{media_id}?fields=caption,timestamp,media_type&access_token={access_token}"
        media_data = make_request(media_url)

        if "error" in media_data:
            continue

        stats_url = f"{base_url}/{media_id}/insights?metric=impressions,likes,comments,shares,saves&access_token={access_token}"
        stats_data = make_request(stats_url)

        if "error" in stats_data or "data" not in stats_data:
            continue

        stats = {}
        for item in stats_data["data"]:
            stats[item["name"]] = item.get("values", [{}])[0].get("value", 0)

        caption = media_data.get("caption", "")
        title = caption.split("\n")[0][:60] if caption else f"Post {media_id[-6:]}"

        try:
            date_str = media_data["timestamp"][:10]
        except (KeyError, TypeError):
            date_str = datetime.now().strftime("%Y-%m-%d")

        alc = stats.get("impressions", 0)
        salvamentos = stats.get("saves", 0)
        envios = stats.get("shares", 0)
        leads = 0

        metrica = {
            "titulo": title,
            "data": date_str,
            "alcance": alc,
            "taxa_salvamentos": round((salvamentos / alc) * 100, 2) if alc > 0 else 0.0,
            "taxa_envios": round((envios / alc) * 100, 2) if alc > 0 else 0.0,
            "taxa_nao_seguidores": 0.0,
            "leads_whatsapp": leads,
            "instagram_post_id": media_id,
        }
        metrics.append(metrica)

    return metrics
