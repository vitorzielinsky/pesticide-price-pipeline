"""Configurações do projeto.

Tudo que é específico de uma fonte de dados (URLs, padrão de links) vem de
variáveis de ambiente. O repositório não traz nenhuma fonte configurada:
use uma fonte pública cujos termos de uso permitam a coleta automatizada.
"""

import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
EXPORTS_DIR = os.path.join(BASE_DIR, "exports")
LOGS_DIR = os.path.join(BASE_DIR, "logs")

DB_PATH = os.path.join(DATA_DIR, "prices.db")
EXCEL_PATH = os.path.join(EXPORTS_DIR, "prices.xlsx")
REVIEW_EXCEL_PATH = os.path.join(EXPORTS_DIR, "manual_review.xlsx")
LOG_PATH = os.path.join(LOGS_DIR, "pipeline.log")

# Catálogo de produtos (nomes em chinês/inglês/português + categoria).
CATALOG_PATH = os.environ.get(
    "CATALOG_PATH", os.path.join(BASE_DIR, "catalog", "example_catalog.xlsx")
)
# Aliases opcionais: {"alias em chinês": "nome principal no catálogo"}.
ALIASES_PATH = os.environ.get(
    "ALIASES_PATH", os.path.join(BASE_DIR, "catalog", "aliases.json")
)

# Pasta com relatórios em texto (.txt) para rodar o pipeline offline.
SAMPLE_REPORTS_DIR = os.path.join(BASE_DIR, "examples", "sample_reports")

# --- Coleta online (opcional) -------------------------------------------------
# SOURCE_LIST_URL   ex.: "https://exemplo.org/lista?page={page}"
# SOURCE_REPORT_URL ex.: "https://exemplo.org/relatorio?id={id}"
# SOURCE_LINK_REGEX regex com 1 grupo que captura o ID no href dos links
LIST_URL = os.environ.get("SOURCE_LIST_URL", "")
REPORT_URL = os.environ.get("SOURCE_REPORT_URL", "")
LINK_REGEX = os.environ.get("SOURCE_LINK_REGEX", r"[?&]id=(\d+)")

DELAY_ENTRE_REQUISICOES = 2.0   # segundos entre requisições (seja gentil)
TIMEOUT_REQUISICAO = 30
MAX_TENTATIVAS = 3
HEADERS = {
    "User-Agent": "pesticide-price-pipeline/1.0 (research project)",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

# Palavras (em chinês) que indicam relatório de mercado com cotações.
PALAVRAS_CHAVE_MERCADO = [
    "原药", "除草剂", "杀虫剂", "杀菌剂", "万元/吨", "元/吨",
    "报价", "行情", "价格指数",
]

# --- Log ----------------------------------------------------------------------
LOG_LEVEL = "INFO"
LOG_MAX_BYTES = 5_242_880
LOG_BACKUP_COUNT = 3

# --- Versões gravadas em cada resultado (rastreabilidade) --------------------
EXTRACTOR_VERSION = "2.3.2"
SCHEMA_VERSION = "4"

# Limites usados apenas como alertas de qualidade.
MIN_TEXT_LENGTH = 200
MAX_PRICES_PER_PRODUCT_REPORT = 5
EXTREME_PRICE_YUAN_TON = 2_000_000
