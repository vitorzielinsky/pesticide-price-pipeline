"""Orquestra catálogo, coleta (online ou local), extração e publicação."""

from __future__ import annotations

from datetime import datetime
import glob
import logging
import os

from config.settings import PALAVRAS_CHAVE_MERCADO, SAMPLE_REPORTS_DIR
from src.catalog import CatalogValidationError, load_catalog
from src.database import (
    deduplicate_auto_rejected_reviews,
    initialize_database,
    pending_reports,
    replace_report_results,
    report_exists,
    resolve_unknown_reviews,
    set_metadata,
    upsert_report,
)
from src.exporter import export_all
from src.extractor import extract_prices

logger = logging.getLogger(__name__)


def load_local_reports(directory: str = SAMPLE_REPORTS_DIR) -> int:
    """Importa relatórios .txt de uma pasta (modo offline / demonstração).

    Formato de cada arquivo::

        id: 1001
        date: 2024-03-04
        title: Título do relatório
        ---
        texto do relatório...
    """
    imported = 0
    for path in sorted(glob.glob(os.path.join(directory, "*.txt"))):
        with open(path, encoding="utf-8") as file:
            header, _, body = file.read().partition("\n---\n")
        meta = {}
        for line in header.splitlines():
            key, _, value = line.partition(":")
            meta[key.strip().lower()] = value.strip()
        report_id = int(meta["id"])
        if report_exists(report_id):
            continue
        upsert_report({
            "id_relatorio": report_id,
            "url_solicitada": f"local://{os.path.basename(path)}",
            "url_final": f"local://{os.path.basename(path)}",
            "codigo_http": None,
            "data_relatorio": meta.get("date", ""),
            "titulo": meta.get("title", ""),
            "texto_completo": body.strip(),
            "html_bruto": None,
            "hash_conteudo": None,
            "eh_mercado": any(w in body for w in PALAVRAS_CHAVE_MERCADO),
            "data_coleta": datetime.now().isoformat(timespec="seconds"),
        })
        imported += 1
    return imported


def process_pending(catalog, force_reprocess: bool = False) -> dict:
    reports = pending_reports(force_reprocess=force_reprocess)
    total_prices = 0
    total_reviews = 0
    for report_id, url, date, text in reports:
        result = extract_prices(text, url, date, report_id, catalog)
        if result.reviews:
            state = "revisao_manual"
            message = (
                f"{len(result.reviews)} caso(s) precisam de revisão humana."
            )
        elif result.prices:
            state = "extraido"
            message = f"{len(result.prices)} preço(s) de confiança alta."
        elif result.quote_count:
            state = "falha_extracao"
            message = (
                "O relatório contém termos de cotação, mas nenhum preço seguro "
                "foi reconhecido."
            )
        else:
            state = "sem_preco_confirmado"
            message = "Nenhum termo de cotação foi encontrado."
        replace_report_results(
            report_id, result.prices, result.reviews, state, message,
        )
        total_prices += len(result.prices)
        total_reviews += len(result.reviews)
    return {
        "relatorios_processados": len(reports),
        "precos_alta_confianca": total_prices,
        "casos_revisao": total_reviews,
    }


def run_pipeline(
    collect_online: bool,
    force_reprocess: bool = False,
    local_reports_dir: str | None = None,
) -> dict:
    """Executa catálogo, coleta opcional, processamento e publicação."""
    catalog = load_catalog()
    initialize_database()
    set_metadata("catalog_version", catalog.version)
    set_metadata("catalog_hash", catalog.file_hash)
    set_metadata("catalog_modified_at", catalog.file_modified_at)

    imported = 0
    if local_reports_dir:
        imported = load_local_reports(local_reports_dir)

    if collect_online:
        # A dependência de rede só é carregada quando realmente necessária.
        from src.scraper import collect_new_reports
        collection = collect_new_reports()
    else:
        collection = {
            "total_listagem": 0,
            "novos": 0,
            "existentes": 0,
            "erros": 0,
            "varredura_completa": True,
            "pagina_falha": None,
            "ids_com_erro": [],
        }
    extraction = process_pending(catalog, force_reprocess=force_reprocess)
    extraction["revisoes_fora_catalogo_resolvidas"] = (
        resolve_unknown_reviews(catalog)
    )
    extraction["revisoes_automaticas_duplicadas_removidas"] = (
        deduplicate_auto_rejected_reviews()
    )
    outputs = export_all(catalog)
    return {
        "relatorios_importados": imported,
        "coleta": collection,
        "extracao": extraction,
        "arquivos": outputs,
        "catalogo": catalog.version,
    }


__all__ = ["CatalogValidationError", "run_pipeline"]
