#!/usr/bin/env python3
"""Incorpora no banco as decisões preenchidas no Excel de revisão."""

import sys
import os
import shutil

from openpyxl import load_workbook

from config.settings import DB_PATH, EXCEL_PATH, REVIEW_EXCEL_PATH
from src.catalog import CatalogValidationError, load_catalog
from src.exporter import export_all
from src.review_importer import ReviewImportError, import_manual_reviews


def _check_excel_files_closed() -> None:
    """Confere os arquivos antes de alterar o banco e evita saída parcial."""
    for path in (
        REVIEW_EXCEL_PATH,
        EXCEL_PATH,
    ):
        try:
            workbook = load_workbook(path, read_only=True, data_only=True)
            workbook.close()
        except FileNotFoundError:
            continue
        except PermissionError as error:
            raise ReviewImportError(
                "Feche todos os arquivos Excel da pasta exports antes "
                "de incorporar a revisão."
            ) from error


def main() -> None:
    print("\n" + "=" * 68)
    print(" INCORPORAR REVISÃO MANUAL")
    print("=" * 68)
    print("\nLendo as decisões da aba Pendentes...")

    _check_excel_files_closed()
    catalog = load_catalog()
    result = import_manual_reviews(catalog)
    if result["total"] == 0:
        print("Nenhuma decisão preenchida foi encontrada.")
        print("O banco e os arquivos não foram alterados.")
        return

    print(f"Decisões incorporadas: {result['total']}")
    print(f"  Incluídos: {result['incluidos']}")
    print(f"  Corrigidos: {result['corrigidos']}")
    print(f"  Não incluídos: {result['nao_incluidos']}")
    print("\nAtualizando os arquivos...")
    try:
        export_all(catalog, allow_review_overwrite=True)
    except Exception:
        # A incorporação só é considerada concluída se banco e Excels
        # forem publicados juntos. Em caso de falha, o banco volta ao backup.
        backup = result.get("backup")
        if backup and os.path.exists(backup):
            shutil.copy2(backup, DB_PATH)
        raise
    print("Revisão incorporada com sucesso.")


if __name__ == "__main__":
    try:
        main()
    except (CatalogValidationError, ReviewImportError, ValueError) as error:
        print(f"\nNão foi possível incorporar a revisão:\n{error}")
        sys.exit(2)
    except PermissionError:
        print("\nFeche todos os arquivos Excel da pasta exports e tente novamente.")
        sys.exit(3)
    except Exception as error:
        print("\nOcorreu um erro. Nenhuma incorporação parcial foi aplicada.")
        print(f"Detalhe: {error}")
        sys.exit(1)
