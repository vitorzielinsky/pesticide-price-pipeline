#!/usr/bin/env python3
"""Primeira execução e reconstrução completa."""

import logging
import sys

from src.catalog import CatalogValidationError
from src.logger import configure_logging
from src.pipeline import run_pipeline
from src.scraper import SiteTemporarilyUnavailable, SourceNotConfigured


def main() -> None:
    configure_logging()
    print("\n" + "=" * 68)
    print(" COLETA COMPLETA")
    print("=" * 68)
    print("\n[1/4] Conferindo a planilha oficial de nomes...")
    print("[2/4] Buscando relatórios novos...")

    result = run_pipeline(collect_online=True, force_reprocess=True)
    extraction = result["extracao"]
    collection = result["coleta"]
    print("[3/4] Conferindo produtos, preços e casos duvidosos...")
    print(
        f"      {extraction['precos_alta_confianca']} preço(s) seguro(s); "
        f"{extraction['casos_revisao']} caso(s) para revisão."
    )
    if collection["erros"]:
        ids = ", ".join(str(value) for value in collection["ids_com_erro"])
        print(
            f"      {collection['erros']} relatório(s) ainda não foram "
            f"baixados (IDs: {ids})."
        )
    print("[4/4] Gerando os arquivos...")
    for path in result["arquivos"]:
        print(f"      OK: {path}")
    if not collection.get("varredura_completa", True):
        print(
            "\nATENÇÃO: a coleta online foi parcial porque a página "
            f"{collection['pagina_falha']} não respondeu."
        )
        print(
            "Os relatórios localizados foram processados. Execute novamente "
            "mais tarde para completar a busca."
        )
    print("\nExecução concluída.")


if __name__ == "__main__":
    try:
        main()
    except CatalogValidationError as error:
        print(f"\nNão foi possível continuar:\n{error}")
        print("Nenhum Excel foi substituído.")
        sys.exit(2)
    except SiteTemporarilyUnavailable:
        print("\nA fonte está temporariamente indisponível.")
        print("Nenhum Excel foi substituído; os últimos arquivos válidos foram mantidos.")
        print("Tente executar a coleta novamente mais tarde.")
        sys.exit(3)
    except SourceNotConfigured as error:
        print(f"\n{error}")
        sys.exit(4)
    except KeyboardInterrupt:
        print("\nExecução interrompida pelo usuário.")
        sys.exit(1)
    except Exception as error:
        logging.getLogger(__name__).error(
            "Coleta não concluída: %s", error
        )
        print("\nO sistema encontrou um erro e preservou os arquivos anteriores.")
        print(f"Detalhe: {error}")
        sys.exit(1)
