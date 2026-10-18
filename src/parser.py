"""Parser HTML com título e ID validados explicitamente."""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

from bs4 import BeautifulSoup



def _id_from_url(url: str) -> int | None:
    try:
        values = parse_qs(urlparse(url).query).get("id", [])
        return int(values[0]) if values else None
    except (TypeError, ValueError):
        return None


def _article_container(soup: BeautifulSoup):
    selectors = (
        ".news-content",
        ".article-content",
        ".news-detail",
        ".news_show",
        ".content",
        "#content",
    )
    for selector in selectors:
        container = soup.select_one(selector)
        if container:
            return container
    return soup.find("body") or soup


def extrair_data(soup: BeautifulSoup, html: str) -> str:
    """Data de publicação em YYYY-MM-DD, ou "" se não encontrada.

    Procura o padrão "发布时间：AAAA-MM-DD" (publicado em). Se não houver,
    tenta uma data AAAAMMDD no início do texto (comum em títulos).
    """
    texto_pagina = soup.get_text()
    for fonte in (texto_pagina, html):
        match = re.search(r"发布时间[：:]\s*(\d{4}-\d{2}-\d{2})", fonte)
        if match:
            return match.group(1)
    match = re.search(r"(20\d{2})(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])", texto_pagina[:500])
    if match:
        return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
    return ""


def extrair_texto_principal(soup: BeautifulSoup) -> str:
    """Texto limpo do conteúdo principal, sem scripts, menus ou rodapé."""
    for tag in soup(["script", "style", "nav", "footer"]):
        tag.decompose()
    container = _article_container(soup)
    texto = container.get_text(separator="\n", strip=True)
    return re.sub(r"\n{3,}", "\n\n", texto).strip()


def extract_title(soup: BeautifulSoup) -> str:
    """Procura o título dentro do artigo e rejeita títulos genéricos de menu (lista ajustável por fonte)."""
    invalid = {
        "产品中心",  # Central de produtos
        "首页",
        "新闻中心",
    }
    container = _article_container(soup)
    for selector in ("h1", "h2", "h3", ".title", ".news-title"):
        for element in container.select(selector):
            title = element.get_text(" ", strip=True)
            if title and title not in invalid:
                return title

    title_tag = soup.find("title")
    title = title_tag.get_text(" ", strip=True) if title_tag else ""
    return "" if title in invalid else title


def parse_report_html(
    html: str,
    requested_url: str,
    final_url: str,
    requested_id: int,
) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    final_id = _id_from_url(final_url)

    canonical = soup.find("link", rel=lambda value: value and "canonical" in value)
    canonical_id = _id_from_url(canonical.get("href", "")) if canonical else None
    confirmed_id = canonical_id or final_id
    if confirmed_id is not None and confirmed_id != requested_id:
        raise ValueError(
            f"O relatório solicitado ({requested_id}) redirecionou para "
            f"outro ID ({confirmed_id})."
        )

    text = extrair_texto_principal(soup)
    if not text:
        raise ValueError(f"O relatório {requested_id} não possui texto legível.")

    return {
        "id_relatorio": requested_id,
        "url_solicitada": requested_url,
        "url_final": final_url,
        "data_relatorio": extrair_data(soup, html),
        "titulo": extract_title(soup),
        "texto_completo": text,
    }
