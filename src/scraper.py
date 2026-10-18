"""Coleta com paginação dinâmica e evidência HTTP (fonte configurável)."""

from __future__ import annotations

from datetime import datetime
from dataclasses import dataclass
import hashlib
import logging
import re
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

from config.settings import (
    DELAY_ENTRE_REQUISICOES,
    HEADERS,
    LINK_REGEX,
    LIST_URL,
    MAX_TENTATIVAS,
    PALAVRAS_CHAVE_MERCADO,
    REPORT_URL,
    TIMEOUT_REQUISICAO,
)
from src.database import report_exists, upsert_report
from src.parser import parse_report_html

logger = logging.getLogger(__name__)


class SourceNotConfigured(RuntimeError):
    """Nenhuma fonte online foi configurada por variáveis de ambiente."""


class SiteTemporarilyUnavailable(RuntimeError):
    """Indica que nem a primeira página do site pôde ser consultada."""


@dataclass
class HttpResponse:
    text: str
    url: str
    status_code: int
    content: bytes


@dataclass
class ListingResult:
    items: list[tuple[int, str, str]]
    complete: bool
    failed_page: int | None = None


def safe_request(url: str) -> HttpResponse | None:
    """Faz a requisição com a biblioteca padrão do Python.

    Não depende de biblioteca HTTP externa (usa urllib).
    """
    for attempt in range(1, MAX_TENTATIVAS + 1):
        try:
            request = Request(url, headers=HEADERS)
            with urlopen(request, timeout=TIMEOUT_REQUISICAO) as response:
                content = response.read()
                charset = response.headers.get_content_charset() or "utf-8"
                try:
                    text = content.decode(charset)
                except (LookupError, UnicodeDecodeError):
                    text = content.decode("utf-8", errors="replace")
                return HttpResponse(
                    text=text,
                    url=response.geturl(),
                    status_code=response.status,
                    content=content,
                )
        except (HTTPError, URLError, TimeoutError, OSError) as error:
            logger.warning(
                "Tentativa %s/%s falhou para %s: %s",
                attempt,
                MAX_TENTATIVAS,
                url,
                error,
            )
            if attempt < MAX_TENTATIVAS:
                time.sleep(DELAY_ENTRE_REQUISICOES * attempt)
    return None


def collect_listing_ids(
    stop_after_known_page: bool = True,
) -> ListingResult:
    """Lê páginas somente enquanto elas podem conter relatórios novos.

    A listagem é ordenada do relatório mais recente para o mais antigo. Em uma
    atualização, quando uma página inteira já existe no banco, as páginas
    seguintes também pertencem ao histórico conhecido. Parar nesse ponto evita
    consultar desnecessariamente todas as páginas antigas e reduz bastante a
    chance de timeout no site.
    """
    if not LIST_URL or not REPORT_URL:
        raise SourceNotConfigured(
            "Defina SOURCE_LIST_URL e SOURCE_REPORT_URL (veja o README). "
            "Para testar sem rede, use demo.py."
        )
    collected: dict[int, tuple[int, str, str]] = {}
    page = 1
    while True:
        response = safe_request(LIST_URL.format(page=page))
        if response is None:
            if not collected:
                raise SiteTemporarilyUnavailable(
                    "A fonte não respondeu. Tente novamente mais tarde."
                )
            logger.warning(
                "A página %s não respondeu. Os relatórios já encontrados "
                "serão processados e a varredura ficará marcada como parcial.",
                page,
            )
            return ListingResult(
                items=sorted(collected.values(), key=lambda item: item[0]),
                complete=False,
                failed_page=page,
            )
        soup = BeautifulSoup(response.text, "html.parser")
        page_items = []
        for link in soup.find_all("a", href=True):
            match = re.search(LINK_REGEX, link["href"])
            if not match:
                continue
            report_id = int(match.group(1))
            parent = link.parent
            date_element = parent.find("em") if parent else None
            page_items.append((
                report_id,
                date_element.get_text(strip=True) if date_element else "",
                link.get_text(strip=True),
            ))

        new_items = [item for item in page_items if item[0] not in collected]
        if not page_items or (page > 1 and not new_items):
            break
        for item in new_items:
            collected[item[0]] = item
        logger.info("Página %s: %s relatório(s).", page, len(page_items))

        all_known = all(report_exists(item[0]) for item in page_items)
        if stop_after_known_page and all_known:
            logger.info(
                "Página %s contém somente relatórios já conhecidos. "
                "A busca por novidades foi concluída.",
                page,
            )
            break

        page += 1
        time.sleep(DELAY_ENTRE_REQUISICOES)

    return ListingResult(
        items=sorted(collected.values(), key=lambda item: item[0]),
        complete=True,
    )


def collect_new_reports() -> dict:
    listing = collect_listing_ids(stop_after_known_page=True)
    result = {
        "total_listagem": len(listing.items),
        "novos": 0,
        "existentes": 0,
        "erros": 0,
        "varredura_completa": listing.complete,
        "pagina_falha": listing.failed_page,
        "ids_com_erro": [],
    }
    for report_id, date_hint, _ in listing.items:
        if report_exists(report_id):
            result["existentes"] += 1
            continue

        requested_url = REPORT_URL.format(id=report_id)
        response = safe_request(requested_url)
        if response is None:
            result["erros"] += 1
            result["ids_com_erro"].append(report_id)
            continue
        try:
            report = parse_report_html(
                response.text, requested_url, response.url, report_id
            )
            report.update({
                "codigo_http": response.status_code,
                "data_relatorio": report["data_relatorio"] or date_hint,
                "html_bruto": response.text,
                "hash_conteudo": hashlib.sha256(
                    response.content
                ).hexdigest(),
                "eh_mercado": any(
                    word in report["texto_completo"]
                    for word in PALAVRAS_CHAVE_MERCADO
                ),
                "data_coleta": datetime.now().isoformat(timespec="seconds"),
            })
            upsert_report(report)
            result["novos"] += 1
        except ValueError as error:
            logger.warning("ID %s ignorado: %s", report_id, error)
            result["erros"] += 1
            result["ids_com_erro"].append(report_id)
        time.sleep(DELAY_ENTRE_REQUISICOES)
    return result
