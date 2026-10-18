#!/usr/bin/env python3
"""Demonstração offline: processa relatórios sintéticos e gera os Excels.

    python demo.py

Não usa rede. Os textos em examples/sample_reports são inventados.
"""

from config.settings import SAMPLE_REPORTS_DIR
from src.logger import configure_logging
from src.pipeline import run_pipeline


def main() -> None:
    configure_logging()
    result = run_pipeline(
        collect_online=False,
        force_reprocess=True,
        local_reports_dir=SAMPLE_REPORTS_DIR,
    )
    extraction = result["extracao"]
    print(f"Relatórios importados: {result['relatorios_importados']}")
    print(f"Preços seguros:        {extraction['precos_alta_confianca']}")
    print(f"Casos para revisão:    {extraction['casos_revisao']}")
    for path in result["arquivos"]:
        print(f"Gerado: {path}")


if __name__ == "__main__":
    main()
