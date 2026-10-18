"""Extracao conservadora de precos por frase e clausula."""

from __future__ import annotations

from dataclasses import dataclass
import re

from config.settings import EXTRACTOR_VERSION
from src.catalog import Catalog


CHINESE_CHAR = r"[\u3400-\u9fff]"
REPORT_VERB_PATTERN = (
    r"(?:\u6682\s*\u62a5|\u62a5\s*\u5230|\u62a5(?:\u4ef7)?)"
)
UNIT_PATTERN = (
    r"(?:\u4e07\s*\u5143|\u5143|\u4e07)\s*[\uff0f/]\s*\u5428"
)
NUMBER_PATTERN = r"(\d+(?:[.,]\d+)?)"

PATTERN_CONCENTRATION = re.compile(
    rf"(\d+(?:[.,]\d+)?)\s*%\s*\u542b\s*\u91cf\s*"
    rf"(?:{CHINESE_CHAR}|\s|[\uff0c,\u3001]){{0,24}}?"
    rf"{REPORT_VERB_PATTERN}\s*{NUMBER_PATTERN}\s*({UNIT_PATTERN})"
)
PATTERN_BASE_100 = re.compile(
    rf"\u6298\s*\u767e\s*{REPORT_VERB_PATTERN}\s*"
    rf"{NUMBER_PATTERN}\s*({UNIT_PATTERN})"
)
PATTERN_QUOTE = re.compile(
    rf"{REPORT_VERB_PATTERN}\s*{NUMBER_PATTERN}\s*({UNIT_PATTERN})"
)
PATTERN_PRICE_VALUE = re.compile(
    rf"{NUMBER_PATTERN}\s*({UNIT_PATTERN})"
)
PATTERN_PARALLEL_REPORT = re.compile(
    rf"\u5206\s*\u522b\s*{REPORT_VERB_PATTERN}"
)

CLAUSE_SEPARATOR = re.compile(r"(?<=[\u3002\uff1b;\uff01\uff1f!?])")
QUOTE_MARKER = re.compile(
    rf"\u62a5\u4ef7|\u6682\s*\u62a5|\u62a5\s*\u5230|"
    rf"\u6298\s*\u767e\s*{REPORT_VERB_PATTERN}|"
    rf"\u542b\s*\u91cf\s*{REPORT_VERB_PATTERN}"
)
LOCAL_SEPARATORS = "\uff0c,\u3001\uff1b;\u3002"
FORM_SUFFIXES = (
    "\u539f\u836f",
    "\u6c34\u5242",
    "\u6bcd\u836f",
    "\u6bcd\u6db2",
    "\u7cbe\u7c89",
    "\u7c89\u5242",
    "\u94a0\u76d0",
    "\u94f5\u76d0",
    "\u4e8c\u6c2f\u76d0",
    "\u4e8c\u6eb4\u76d0",
)
FORM_SUFFIX_PATTERN = "|".join(re.escape(value) for value in FORM_SUFFIXES)
LIQUID_CONCENTRATION_PATTERN = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*\u514b\s*/\s*\u5347"
)
UNKNOWN_PRODUCT_TAIL = re.compile(
    rf"({CHINESE_CHAR}{{3,12}}(?:{FORM_SUFFIX_PATTERN})?)\s*$"
)
UNKNOWN_PRODUCT_HEAD = re.compile(
    rf"^\s*({CHINESE_CHAR}{{2,12}}?)(?:{FORM_SUFFIX_PATTERN}|"
    rf"\u5f00\u5de5|\u4ef7\u683c|\u5e02\u573a|\u8d27\u6e90|"
    rf"\u4f9b\u5e94|\u62a5|\u5382\u5bb6|\u5de5\u5382)"
)
UNKNOWN_STOPWORDS = (
    "\u4ef7\u683c",
    "\u5e02\u573a",
    "\u5de5\u5382",
    "\u5382\u5bb6",
    "\u5f53\u524d",
    "\u539f\u6750\u6599",
    "\u4e2d\u95f4\u4f53",
    "\u8d27\u6e90",
    "\u751f\u4ea7\u4f01\u4e1a",
    "\u6210\u672c",
    "\u627f\u538b",
    "\u63d0\u9ad8",
    "\u5feb\u901f",
    "\u4e0a\u6da8",
    "\u4f9b\u5e94",
    "\u5e93\u5b58",
    "\u4ea7\u54c1",
    "\u76ee\u524d",
    "\u7ec8\u7aef",
    "\u6e20\u9053",
    "\u4e0a\u8c03",
    "\u4e0b\u8c03",
    "\u7ef4\u6301",
    "\u7a33\u5b9a",
    "\u7d27\u5f20",
    "\u5f71\u54cd",
    "\u672c\u5468",
    "\u672c\u6708",
    "\u6708\u5e95",
    "\u73b0\u8d27",
    "\u6de1\u50a8",
    "\u79cd\u8863\u5242",
    "\u54c1\u8d28",
    "\u6d41\u901a\u8d27\u6e90",
    "\u4f4e\u542b\u91cf",
    "\u9ad8\u542b\u91cf",
    "\u90e8\u5206",
    "\u62cc\u79cd\u5242",
    "\u9700\u7528",
    "\u9ad8\u7aef\u539f\u836f",
    "\u6709\u8bc1\u5927\u5382",
    "\u5927\u5382",
    "\u652f\u6491",
    "\u4e8c\u6c2f\u76d0",
    "\u4e8c\u6eb4\u76d0",
)
CONTEXT_PREFIXES = (
    "\u76ee\u524d",
    "\u5f53\u524d",
    "\u672c\u5468",
    "\u672c\u6708",
    "\u6708\u5e95",
    "\u4ea7\u54c1",
    "\u5e02\u573a",
    "\u56fd\u5185",
    "\u4e0a\u6e38",
    "\u4e0b\u6e38",
    "\u5bfc\u81f4",
    "\u5e26\u52a8",
    "\u5e26\u52a8\u4e86",
    "\u4e0d\u5c11",
    "\u8c46\u7530",
    "\u548c",
    "\u53ca",
)
PRODUCT_CONTEXT_FOLLOWERS = (
    "\u5e02\u573a",
    "\u53d7",
    "\u7684",
    "\u548c",
    "\u53ca",
    "\u6bcd\u6db2",
    "\u884c\u60c5",
    "\u4ef7\u683c",
)
SEGMENT_MARKERS = (
    ("qualidade_tratamento_sementes", ("\u79cd\u8863\u5242",)),
    ("mercado_circulante", ("\u6d41\u901a\u8d27\u6e90",)),
    ("canal_fabrica", ("\u5de5\u5382", "\u5382\u5bb6", "\u5927\u5382")),
    ("canal_distribuidor", ("\u6e20\u9053",)),
    ("alta_qualidade", ("\u9ad8\u7aef", "\u9ad8\u8d28\u91cf")),
)
_PRODUCT_PATTERN_CACHE: dict[tuple[str, tuple[str, ...]], re.Pattern] = {}


@dataclass
class ExtractionResult:
    prices: list[dict]
    reviews: list[dict]
    quote_count: int


def normalize_text(text: str) -> str:
    normalized = text.replace("\u3000", " ").replace("\xa0", " ")
    normalized = normalized.replace("\uff0f", "/")
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized


def price_to_yuan(value_text: str, unit: str) -> float:
    value = float(value_text.replace(",", "."))
    compact_unit = re.sub(r"\s+", "", unit).replace("\uff0f", "/")
    # round evita resíduos de ponto flutuante (2.28 * 10000 = 22799.999...).
    return round(value * 10_000, 2) if "\u4e07" in compact_unit else value


def _has_chinese(value: str) -> bool:
    return re.search(CHINESE_CHAR, value) is not None


def _compact_alias_text(value: str) -> str:
    return re.sub(r"\s+", "", value)


def _normalize_excerpt_key(value: str) -> str:
    return re.sub(r"\s+", "", value or "")


def _normalize_form_original(value: str) -> str:
    return re.sub(r"\s+", "", value or "")


def _tolerant_name_pattern(name: str) -> str:
    pieces = []
    for index, char in enumerate(name):
        pieces.append(re.escape(char))
        if index < len(name) - 1 and _has_chinese(char) and _has_chinese(name[index + 1]):
            pieces.append(r"\s*")
    return "".join(pieces)


def _tolerant_non_chinese_pattern(name: str) -> str:
    pieces = []
    for char in name:
        if char in ",-/":
            pieces.append(rf"\s*{re.escape(char)}\s*")
        else:
            pieces.append(re.escape(char))
    return "".join(pieces)


def _product_pattern(catalog: Catalog) -> re.Pattern:
    names = sorted(catalog.aliases, key=len, reverse=True)
    cache_key = (catalog.version, tuple(names))
    cached = _PRODUCT_PATTERN_CACHE.get(cache_key)
    if cached is not None:
        return cached
    patterns = []
    for name in names:
        escaped = (
            _tolerant_name_pattern(name)
            if _has_chinese(name)
            else _tolerant_non_chinese_pattern(name)
        )
        if _has_chinese(name):
            context_prefixes = "|".join(
                rf"(?<={re.escape(value)})" for value in CONTEXT_PREFIXES
            )
            prefix = rf"(?:(?<!{CHINESE_CHAR})|(?<=\u5347)|{context_prefixes})"
            if any(name.endswith(suffix) for suffix in FORM_SUFFIXES):
                patterns.append(rf"{prefix}{escaped}")
            else:
                context_followers = "|".join(
                    re.escape(value) for value in PRODUCT_CONTEXT_FOLLOWERS
                )
                patterns.append(
                    rf"{prefix}{escaped}"
                    rf"(?=(?:{FORM_SUFFIX_PATTERN})|(?:{context_followers})|"
                    rf"{REPORT_VERB_PATTERN}|"
                    rf"(?!{CHINESE_CHAR}).|$)"
                )
        else:
            patterns.append(escaped)
    compiled = re.compile("|".join(patterns))
    _PRODUCT_PATTERN_CACHE[cache_key] = compiled
    return compiled


def _iter_clauses(text: str):
    start = 0
    for match in CLAUSE_SEPARATOR.finditer(text):
        end = match.end()
        clause = text[start:end].strip()
        if clause:
            yield start, clause
        start = end
    tail = text[start:].strip()
    if tail:
        yield start, tail


def _specific_matches(clause: str) -> list[dict]:
    found = []
    occupied: list[tuple[int, int]] = []

    parallel = PATTERN_PARALLEL_REPORT.search(clause)
    if parallel:
        for match in PATTERN_PRICE_VALUE.finditer(clause, parallel.end()):
            found.append({
                "start": match.start(),
                "end": match.end(),
                "concentracao": "",
                "value": match.group(1),
                "unit": match.group(2),
                "rule": "lista_respectiva",
            })
            occupied.append(match.span())

    for match in PATTERN_CONCENTRATION.finditer(clause):
        found.append({
            "start": match.start(),
            "end": match.end(),
            "concentracao": f"{match.group(1).replace(',', '.')}%",
            "value": match.group(2),
            "unit": match.group(3),
            "rule": "concentracao_explicita",
        })
        occupied.append(match.span())

    for match in PATTERN_BASE_100.finditer(clause):
        found.append({
            "start": match.start(),
            "end": match.end(),
            "concentracao": "100% (\u6298\u767e)",
            "value": match.group(1),
            "unit": match.group(2),
            "rule": "base_100_zhebai",
        })
        occupied.append(match.span())

    for match in PATTERN_QUOTE.finditer(clause):
        if any(
            not (match.end() <= start or match.start() >= end)
            for start, end in occupied
        ):
            continue
        found.append({
            "start": match.start(),
            "end": match.end(),
            "concentracao": "",
            "value": match.group(1),
            "unit": match.group(2),
            "rule": "cotacao_generica",
        })

    return sorted(found, key=lambda item: item["start"])


def _parallel_product_matches(
    clause: str,
    quote_matches: list[dict],
    product_matches: list,
) -> dict[int, object]:
    if len(quote_matches) < 2:
        return {}
    preceding = [
        match for match in product_matches
        if match.start() < quote_matches[0]["start"]
    ]
    if len(preceding) < len(quote_matches):
        return {}

    explicit_list = any(
        quote["rule"] == "lista_respectiva" for quote in quote_matches
    )
    list_text = clause[preceding[-len(quote_matches)].start():quote_matches[0]["start"]]
    implicit_list = "\u3001" in list_text and len(preceding) == len(quote_matches)
    if not explicit_list and not implicit_list:
        return {}

    selected = preceding[-len(quote_matches):]
    return {index: match for index, match in enumerate(selected)}


def _shared_product_matches(
    clause: str,
    quote_matches: list[dict],
    product_matches: list,
) -> list:
    if len(quote_matches) != 1:
        return []

    quote = quote_matches[0]
    local_start = _nearest_separator_after(clause, 0, quote["start"])
    local_products = [
        match for match in product_matches
        if local_start <= match.start() < quote["start"]
    ]
    if not 2 <= len(local_products) <= 3:
        return []

    list_text = clause[local_products[0].start():quote["start"]]
    has_shared_connector = (
        "\u548c" in list_text or "\u53ca" in list_text
    )
    if not has_shared_connector:
        return []

    last_product_end = max(match.end() for match in local_products)
    tail = clause[last_product_end:quote["start"]]
    if "\u3001" in tail:
        return []
    return local_products


def _nearest_separator_after(clause: str, start: int, end: int) -> int:
    separator_positions = [
        clause.rfind(separator, start, end) for separator in LOCAL_SEPARATORS
    ]
    last_separator = max(separator_positions)
    return last_separator + 1 if last_separator >= start else start


def _previous_quote_end(quote_start: int, quote_matches: list[dict]) -> int:
    previous = [
        quote["end"] for quote in quote_matches if quote["end"] <= quote_start
    ]
    return max(previous) if previous else 0


def _looks_like_unknown_candidate(candidate: str) -> bool:
    candidate = candidate.strip()
    if not candidate:
        return False
    if candidate in FORM_SUFFIXES:
        return False
    if any(word in candidate for word in UNKNOWN_STOPWORDS):
        return False
    return True


def _unknown_product_after_known(
    clause: str,
    chosen_end: int,
    quote_start: int,
    product_matches: list,
    quote_matches: list[dict],
) -> str | None:
    local_start = _nearest_separator_after(clause, chosen_end, quote_start)
    if any(local_start <= match.start() < quote_start for match in product_matches):
        return None

    local_text = clause[local_start:quote_start].strip()
    if local_text:
        match = UNKNOWN_PRODUCT_TAIL.search(local_text)
        if match:
            candidate = match.group(1)
            if _looks_like_unknown_candidate(candidate):
                return candidate

    previous_quote_end = _previous_quote_end(quote_start, quote_matches)
    if previous_quote_end <= chosen_end:
        return None
    after_previous_quote = clause[previous_quote_end:quote_start].strip()
    for part in re.split(f"[{re.escape(LOCAL_SEPARATORS)}]+", after_previous_quote):
        part = part.strip()
        if not part:
            continue
        match = UNKNOWN_PRODUCT_HEAD.search(part)
        if match and _looks_like_unknown_candidate(match.group(1)):
            return match.group(1)
        if any(word in part for word in UNKNOWN_STOPWORDS):
            continue
    return None


def _context_after_product(clause: str, product_match) -> str:
    return clause[product_match.end():product_match.end() + 8]


def _form_original(clause: str, product_match) -> str:
    start = product_match.start()
    prefix = clause[max(0, start - 16):start]
    concentration = LIQUID_CONCENTRATION_PATTERN.search(prefix)
    if concentration and not prefix[concentration.end():].strip():
        start -= len(prefix) - concentration.start()

    end = product_match.end()
    suffix = _context_after_product(clause, product_match)
    for marker in FORM_SUFFIXES:
        if suffix.startswith(marker):
            end += len(marker)
            break
    return clause[start:end].strip() or product_match.group()


def _segment_info(clause: str, product_match, quote: dict) -> str:
    local_start = _nearest_separator_after(clause, product_match.end(), quote["start"])
    local = clause[local_start:quote["start"]]
    for segment, markers in SEGMENT_MARKERS:
        if any(marker in local for marker in markers):
            return segment
    return "nao_identificado"


def _form_info(clause: str, product_match, quote: dict) -> tuple[str, str, str]:
    original = _normalize_form_original(_form_original(clause, product_match))
    local_start = _nearest_separator_after(clause, product_match.end(), quote["start"])
    local = original + clause[local_start:min(len(clause), quote["start"] + 4)]
    liquid_concentration = LIQUID_CONCENTRATION_PATTERN.search(original)

    if quote["rule"] == "base_100_zhebai" or "\u6298\u767e" in local:
        return "base_100", original, ""
    if "\u6c34\u5242" in local or liquid_concentration:
        concentration = ""
        if liquid_concentration:
            concentration = (
                f"{liquid_concentration.group(1).replace(',', '.')}"
                "\u514b/\u5347"
            )
        return "liquido_agua", original, concentration
    if "\u4e8c\u6c2f\u76d0" in local:
        return "sal_dicloreto", original, ""
    if "\u4e8c\u6eb4\u76d0" in local:
        return "sal_dibrometo", original, ""
    if "\u6bcd\u836f" in local or "\u6bcd\u6db2" in local:
        return "mae_intermediaria", original, ""
    if "\u7cbe\u7c89" in local or "\u7c89\u5242" in local:
        return "po_cristalino", original, ""
    if "\u94a0\u76d0" in local:
        return "sal_sodico", original, ""
    if "\u94f5\u76d0" in local:
        return "sal_amoniaco", original, ""
    if "\u539f\u836f" in local:
        return "tecnico_original", original, ""
    return "nao_identificada", original, ""


def _qualitative_concentration(
    clause: str, product_match, quote: dict
) -> str:
    local = clause[product_match.end():quote["start"]]
    low_position = local.rfind("\u4f4e\u542b\u91cf")
    high_position = local.rfind("\u9ad8\u542b\u91cf")
    if low_position > high_position:
        return "baixo_teor"
    if high_position > low_position:
        return "alto_teor"
    return ""


def _known_product_subject(product_match, catalog: Catalog) -> dict:
    main_name = catalog.aliases[_compact_alias_text(product_match.group())]
    marker_context = product_match.group() + _context_after_product(
        product_match.string, product_match
    )
    has_form_marker = any(
        marker in marker_context for marker in FORM_SUFFIXES
    )
    return {
        "type": "product",
        "match": product_match,
        "found_name": product_match.group(),
        "main_name": main_name,
        "confidence": "alta" if has_form_marker else "media",
    }


def _quote_starts_clause(clause: str, quote: dict) -> bool:
    return not clause[:quote["start"]].strip()


def _subject_product_for_quote(
    clause: str,
    quote_start: int,
    product_matches: list,
    quote_matches: list[dict],
    catalog: Catalog,
):
    candidates = [
        match for match in product_matches if match.start() < quote_start
    ]
    if not candidates:
        return None

    chosen = candidates[-1]
    unknown_name = _unknown_product_after_known(
        clause, chosen.end(), quote_start, product_matches, quote_matches
    )
    if unknown_name:
        return {
            "type": "unknown",
            "found_name": unknown_name,
            "confidence": "baixa",
        }

    main_name = catalog.aliases[_compact_alias_text(chosen.group())]
    distance = quote_start - chosen.end()
    marker_context = chosen.group() + _context_after_product(clause, chosen)
    has_form_marker = any(marker in marker_context for marker in FORM_SUFFIXES)
    confidence = "alta" if has_form_marker or distance <= 80 else "media"
    return {
        "type": "product",
        "match": chosen,
        "found_name": chosen.group(),
        "main_name": main_name,
        "confidence": confidence,
    }


def _review(
    report_date: str,
    product_suggested: str,
    price: float,
    clause: str,
    reason: str,
    confidence: str,
) -> dict:
    return {
        "data_relatorio": report_date,
        "produto_sugerido": product_suggested,
        "preco_yuan_ton": price,
        "trecho_original": clause,
        "motivo": reason,
        "confianca": confidence,
    }


def extract_prices(
    text: str,
    url: str,
    report_date: str,
    report_id: int,
    catalog: Catalog,
) -> ExtractionResult:
    normalized = normalize_text(text or "")
    product_regex = _product_pattern(catalog)
    prices: list[dict] = []
    reviews: list[dict] = []
    quote_count = len(QUOTE_MARKER.findall(normalized))
    carry_product: tuple[str, object] | None = None

    for clause_start, clause in _iter_clauses(normalized):
        quote_matches = _specific_matches(clause)
        product_matches = list(product_regex.finditer(clause))
        if not quote_matches:
            if product_matches:
                carry_product = (clause, product_matches[-1])
            continue

        if not product_matches:
            if (
                carry_product is None
                or len(quote_matches) != 1
                or not _quote_starts_clause(clause, quote_matches[0])
            ):
                for quote in quote_matches:
                    reviews.append(_review(
                        report_date,
                        "produto_desconhecido",
                        price_to_yuan(quote["value"], quote["unit"]),
                        clause,
                        (
                            "A frase contem cotacao, mas nenhum produto do catalogo "
                            "oficial foi identificado."
                        ),
                        "baixa",
                    ))
                carry_product = None
                continue

        parallel_products = _parallel_product_matches(
            clause, quote_matches, product_matches
        )
        shared_products = _shared_product_matches(
            clause, quote_matches, product_matches
        )
        for quote_index, quote in enumerate(quote_matches):
            price = price_to_yuan(quote["value"], quote["unit"])
            has_product_before_quote = any(
                match.start() < quote["start"] for match in product_matches
            )
            uses_carry_product = (
                not has_product_before_quote
                and carry_product is not None
                and _quote_starts_clause(clause, quote)
            )
            if quote_index in parallel_products:
                subjects = [_known_product_subject(
                    parallel_products[quote_index], catalog
                )]
            elif quote_index == 0 and shared_products:
                subjects = [
                    _known_product_subject(match, catalog)
                    for match in shared_products
                ]
            elif uses_carry_product:
                subjects = [_known_product_subject(carry_product[1], catalog)]
            else:
                subjects = [_subject_product_for_quote(
                    clause, quote["start"], product_matches,
                    quote_matches, catalog
                )]
            if subjects[0] is None:
                reviews.append(_review(
                    report_date,
                    "produto_desconhecido",
                    price,
                    clause,
                    (
                        "A cotacao aparece antes de qualquer produto oficial "
                        "identificado na frase."
                    ),
                    "baixa",
                ))
                continue
            if subjects[0]["type"] == "unknown":
                reviews.append(_review(
                    report_date,
                    "produto_desconhecido",
                    price,
                    clause,
                    (
                        "A cotacao esta mais proxima de um provavel produto "
                        "fora do catalogo oficial."
                    ),
                    subjects[0]["confidence"],
                ))
                continue

            for subject in subjects:
                product_match = subject["match"]
                main_name = subject["main_name"]
                product = catalog.products[main_name]
                original_unit = re.sub(r"\s+", "", quote["unit"])
                form_clause = clause
                trace_clause = clause
                form_quote = quote
                if uses_carry_product:
                    form_clause = f"{carry_product[0]} {clause}"
                    trace_clause = form_clause
                    offset = len(carry_product[0]) + 1
                    form_quote = {
                        **quote,
                        "start": quote["start"] + offset,
                        "end": quote["end"] + offset,
                    }
                forma_preco, forma_original, form_concentration = _form_info(
                    form_clause, product_match, form_quote
                )
                segmento_preco = _segment_info(
                    form_clause, product_match, form_quote
                )
                concentration = (
                    quote["concentracao"]
                    or form_concentration
                    or _qualitative_concentration(
                        form_clause, product_match, form_quote
                    )
                )
                record = {
                    "data_relatorio": report_date,
                    "id_relatorio": report_id,
                    "produto_chines": main_name,
                    "produto_ingles": product["ingles"],
                    "produto_portugues": product["portugues"],
                    "categoria": product["categoria"],
                    "concentracao": concentration,
                    "forma_preco": forma_preco,
                    "forma_original": forma_original,
                    "segmento_preco": segmento_preco,
                    "preco_yuan_ton": price,
                    "unidade_original": f"{quote['value']}{original_unit}",
                    "url": url,
                    "trecho_original": trace_clause,
                    "nome_encontrado": subject["found_name"],
                    "posicao_texto": clause_start + quote["start"],
                    "regra_aplicada": (
                        "contexto_frase_anterior"
                        if uses_carry_product
                        else
                        "preco_compartilhado"
                        if shared_products else quote["rule"]
                    ),
                    "confianca": subject["confidence"],
                    "extractor_version": EXTRACTOR_VERSION,
                    "catalog_version": catalog.version,
                }
                if subject["confidence"] == "alta":
                    prices.append(record)
                else:
                    reviews.append(_review(
                        report_date,
                        product["portugues"],
                        price,
                        trace_clause,
                        (
                            "O produto foi reconhecido, mas nao aparece no inicio "
                            "da frase. E necessaria confirmacao humana."
                        ),
                        subject["confidence"],
                    ))
        carry_product = None

    unique_prices = []
    seen = set()
    for price in prices:
        key = (
            price["produto_chines"],
            price["concentracao"],
            price["forma_preco"],
            price["forma_original"],
            price["segmento_preco"],
            price["preco_yuan_ton"],
            _normalize_excerpt_key(price["trecho_original"]),
        )
        if key not in seen:
            seen.add(key)
            unique_prices.append(price)

    return ExtractionResult(unique_prices, reviews, quote_count)
