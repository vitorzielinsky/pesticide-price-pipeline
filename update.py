#!/usr/bin/env python3
"""Atualização periódica (só relatórios novos)."""

import logging
import sys

from src.catalog import CatalogValidationError
from src.logger import configure_logging
from src.pipeline import run_pipeline
from src.scraper import SiteTemporarilyUnavailable, SourceNotConfigured


def main() -> None:
    configure_logging()
    print("\n" + "=" * 68)
    print(" ATUALIZAÇÃO")
    print("=" * 68)
    print("\nConferindo catálogo, novos relatórios e preços...")
    result = run_pipeline(collect_online=True, force_reprocess=False)
    collection = result["coleta"]
    extraction = result["extracao"]
    print(f"Novos relatórios: {collection['novos']}")
    if collection["erros"]:
        ids = ", ".join(str(value) for value in collection["ids_com_erro"])
        print(
            f"Relatórios ainda não baixados: {collection['erros']} "
            f"(IDs: {ids})"
        )
        print("Execute novamente mais tarde para tentar somente os que faltam.")
    print(f"Preços seguros processados: {extraction['precos_alta_confianca']}")
    print(f"Casos encaminhados para revisão: {extraction['casos_revisao']}")
    if not collection.get("varredura_completa", True):
        print(
            "\nATENÇÃO: o site deixou de responder na página "
            f"{collection['pagina_falha']}."
        )
        print(
            "Os relatórios encontrados antes disso foram processados. "
            "Execute a atualização novamente mais tarde para completar a busca."
        )
    print("\nArquivos atualizados:")
    for path in result["arquivos"]:
        print(f"  - {path}")
    print("\nAtualização concluída.")


if __name__ == "__main__":
    try:
        main()
    except CatalogValidationError as error:
        print(f"\nNão foi possível continuar:\n{error}")
        print("Confira o catálogo e execute novamente.")
        sys.exit(2)
    except SiteTemporarilyUnavailable:
        print("\nA fonte está temporariamente indisponível.")
        print("Nenhum Excel foi substituído; o último arquivo válido foi mantido.")
        print("Tente executar a atualização novamente mais tarde.")
        sys.exit(3)
    except SourceNotConfigured as error:
        print(f"\n{error}")
        sys.exit(4)
    except KeyboardInterrupt:
        print("\nExecução interrompida pelo usuário.")
        sys.exit(1)
    except Exception as error:
        # Mensagem curta no console; o detalhe técnico fica no log.
        logging.getLogger(__name__).error(
            "Atualização não concluída: %s", error
        )
        print("\nA atualização falhou. Os últimos arquivos válidos foram mantidos.")
        print(f"Detalhe: {error}")
        sys.exit(1)
