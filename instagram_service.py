"""
instagram_service.py — Integração com Instagram Graph API (V1).

Busca métricas de posts do Instagram Business Account e transforma no formato
esperado pelo app (mesmo schema do persistence.metrica).

Pré-requisitos:
- Token de acesso de longa duração (válido por 90 dias) com scopes:
  instagram_basic, pages_show_list, pages_read_engagement
- Page ID da página do Facebook conectada à conta do Instagram

Exemplo de uso:
    from instagram_service import fetch_post_metrics
    metrics = fetch_post_metrics(token, page_id, post_ids=["123", "456"])
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import datetime
from typing import Any
from urllib.parse import urlencode


def fetch_post_metrics(
    access_token: str,
    page_id: str,
    post_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    """
    Busca métricas de posts específicos do Instagram Business Account.
    Usa a Page ID da página do Facebook conectada ao Instagram.

    Args:
        access_token: Token de acesso de longa duração com scopes de pages.
        page_id: ID da página do Facebook conectada à conta Instagram.
        post_ids: Lista de IDs de posts a buscar. Se None, busca todos.

    Returns:
        Lista de dicts com as métricas no formato esperado pelo app.
    """
    base_url = "https://graph.facebook.com/v21.0"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    def make_request(url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Faz requisição HTTP GET e retorna JSON."""
        if not url.startswith("http"):
            url = f"{base_url}/{url.lstrip('/')}"
        if params:
            url = f"{url}?{urlencode(params)}"
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            return {"error": f"HTTP {e.code}: {e.read().decode('utf-8')}"}
        except urllib.error.URLError as e:
            return {"error": f"Rede indisponível: {e.reason}"}

    def get_ig_account_id_from_page(page_id: str, access_token: str) -> str | None:
        """Obtém o ID da conta Instagram vinculada à página."""
        data = make_request(f"{page_id}/instagram_business_account")
        if "error" in data:
            return None
        ig_account = data.get("instagram_business_account", {})
        if isinstance(ig_account, dict):
            return ig_account.get("id")
        return None

    def get_ig_media_ids(ig_account_id: str) -> list[str]:
        """Obtém todos os IDs de mídia da conta do Instagram."""
        data = make_request(f"{ig_account_id}/media", {"fields": "id", "limit": 100})
        media_ids: list[str] = []
        while data and "error" not in data:
            media_ids.extend(
                item["id"] for item in data.get("data", []) if item.get("id")
            )
            next_url = data.get("paging", {}).get("next")
            if not next_url:
                break
            data = make_request(next_url)
        return media_ids

    # Obter IG Account ID a partir da Page ID
    ig_account_id = get_ig_account_id_from_page(page_id, access_token)
    if not ig_account_id:
        return []

    if not post_ids:
        post_ids = get_ig_media_ids(ig_account_id)

    metrics: list[dict[str, Any]] = []

    for media_id in post_ids:
        media_data = make_request(
            media_id,
            {"fields": "caption,timestamp,media_type"},
        )

        if "error" in media_data:
            continue

        stats_data = make_request(
            f"{media_id}/insights",
            {"metric": "reach,impressions,likes,comments,shares,saves"},
        )

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

        # Alcance e impressões são métricas diferentes. O feedback loop usa
        # alcance; impressões ficam armazenadas apenas como dado adicional.
        alc = stats.get("reach", 0)
        if alc <= 0:
            continue
        impressoes = stats.get("impressions", 0)
        salvamentos = stats.get("saves", 0)
        envios = stats.get("shares", 0)
        leads = 0

        metrica = {
            "titulo": title,
            "data": date_str,
            "alcance": alc,
            "impressoes": impressoes,
            "taxa_salvamentos": round((salvamentos / alc) * 100, 2) if alc > 0 else 0.0,
            "taxa_envios": round((envios / alc) * 100, 2) if alc > 0 else 0.0,
            "taxa_nao_seguidores": 0.0,
            "leads_whatsapp": leads,
            "instagram_post_id": media_id,
        }
        metrics.append(metrica)

    return metrics
