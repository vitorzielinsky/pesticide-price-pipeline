"""Camada SQLite: relatórios, preços, revisão manual e verificações."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
import os
import re
import sqlite3

from config.settings import (
    DB_PATH,
    EXTREME_PRICE_YUAN_TON,
    EXTRACTOR_VERSION,
    MAX_PRICES_PER_PRODUCT_REPORT,
    SCHEMA_VERSION,
)


VALID_STATES = {
    "pendente",
    "extraido",
    "sem_preco_confirmado",
    "falha_extracao",
    "revisao_manual",
}

REPORT_VERB_PATTERN = r"(?:\u6682\s*\u62a5|\u62a5\s*\u5230|\u62a5(?:\u4ef7)?)"
UNIT_PATTERN = r"(?:\u4e07\s*\u5143|\u5143|\u4e07)\s*[\uff0f/]\s*\u5428"
QUOTE_PATTERN = re.compile(
    rf"{REPORT_VERB_PATTERN}\s*(\d+(?:[.,]\d+)?)\s*({UNIT_PATTERN})"
)
REVIEW_LOCAL_SEPARATORS = "\uff0c,\u3001\uff1b;\u3002"


def _compact_review_text(value: str) -> str:
    return re.sub(r"\s+", "", value or "")


def _catalog_alias_in_text(catalog, text: str) -> tuple[str, dict] | None:
    if catalog is None:
        return None
    compact_text = _compact_review_text(text)
    aliases = sorted(catalog.aliases, key=len, reverse=True)
    for alias in aliases:
        if _compact_review_text(alias) in compact_text:
            main_name = catalog.aliases[alias]
            return main_name, catalog.products[main_name]
    return None


def _review_price_to_yuan(value_text: str, unit: str) -> float:
    value = float(value_text.replace(",", "."))
    compact_unit = re.sub(r"\s+", "", unit).replace("\uff0f", "/")
    return value * 10_000 if "\u4e07" in compact_unit else value


def _context_for_review_price(text: str, price_yuan: float | None) -> str:
    if price_yuan is None:
        return text or ""
    previous_end = 0
    for match in QUOTE_PATTERN.finditer(text or ""):
        quoted_price = _review_price_to_yuan(match.group(1), match.group(2))
        if abs(quoted_price - price_yuan) > 0.01:
            previous_end = match.end()
            continue
        before_quote = text[previous_end:match.start()]
        separator_positions = [
            before_quote.rfind(separator) for separator in REVIEW_LOCAL_SEPARATORS
        ]
        last_separator = max(separator_positions)
        if last_separator >= 0:
            return before_quote[last_separator + 1:]
        return before_quote
    return text or ""


def _catalog_alias_in_review_context(
    catalog, text: str, price_yuan: float | None
) -> tuple[str, dict] | None:
    status, match = _review_catalog_assessment(catalog, text, price_yuan)
    return match if status == "safe" else None


def _review_catalog_assessment(
    catalog, text: str, price_yuan: float | None
) -> tuple[str, tuple[str, dict] | None]:
    if catalog is None or price_yuan is None:
        return "none", None
    if "\u4e2d\u95f4\u4f53\u5e02\u573a" in (text or ""):
        return "none", None

    from src.extractor import extract_prices

    result = extract_prices(text or "", "", "", 0, catalog)
    matching_products = {
        price["produto_chines"]
        for price in result.prices
        if abs(price["preco_yuan_ton"] - price_yuan) <= 0.01
    }
    matching_suggestions = {
        review["produto_sugerido"]
        for review in result.reviews
        if abs((review["preco_yuan_ton"] or 0) - price_yuan) <= 0.01
        and review["produto_sugerido"] != "produto_desconhecido"
    }

    candidates = set(matching_products)
    for suggestion in matching_suggestions:
        for main_name, product in catalog.products.items():
            if product["portugues"] == suggestion:
                candidates.add(main_name)

    if len(candidates) == 1:
        main_name = next(iter(candidates))
        return "safe", (main_name, catalog.products[main_name])
    if len(candidates) > 1:
        return "ambiguous", None

    matching_unknown = any(
        abs((review["preco_yuan_ton"] or 0) - price_yuan) <= 0.01
        and review["produto_sugerido"] == "produto_desconhecido"
        for review in result.reviews
    )
    if matching_unknown and not result.prices and _catalog_alias_in_text(catalog, text):
        return "ambiguous", None
    return "none", None


def _ensure_price_columns(conn: sqlite3.Connection) -> None:
    existing = {
        row[1] for row in conn.execute("PRAGMA table_info(precos)").fetchall()
    }
    if "forma_preco" not in existing:
        conn.execute("""
            ALTER TABLE precos
            ADD COLUMN forma_preco TEXT NOT NULL DEFAULT 'nao_identificada'
        """)
    if "forma_original" not in existing:
        conn.execute("""
            ALTER TABLE precos
            ADD COLUMN forma_original TEXT NOT NULL DEFAULT ''
        """)
    if "segmento_preco" not in existing:
        conn.execute("""
            ALTER TABLE precos
            ADD COLUMN segmento_preco TEXT NOT NULL DEFAULT 'nao_identificado'
        """)


@contextmanager
def connection():
    """Abre conexão com integridade referencial habilitada."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def initialize_database() -> None:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS metadata (
                chave TEXT PRIMARY KEY,
                valor TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS relatorios (
                id_relatorio INTEGER PRIMARY KEY,
                url_solicitada TEXT NOT NULL,
                url_final TEXT,
                codigo_http INTEGER,
                data_relatorio TEXT,
                titulo TEXT,
                texto_completo TEXT NOT NULL,
                html_bruto TEXT,
                hash_conteudo TEXT,
                eh_mercado INTEGER NOT NULL DEFAULT 0,
                estado_processamento TEXT NOT NULL DEFAULT 'pendente'
                    CHECK (estado_processamento IN (
                        'pendente', 'extraido', 'sem_preco_confirmado',
                        'falha_extracao', 'revisao_manual'
                    )),
                data_coleta TEXT,
                mensagem_estado TEXT
            );

            CREATE TABLE IF NOT EXISTS precos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                id_relatorio INTEGER NOT NULL,
                data_relatorio TEXT,
                produto_chines TEXT NOT NULL,
                produto_ingles TEXT NOT NULL,
                produto_portugues TEXT NOT NULL,
                categoria TEXT NOT NULL,
                concentracao TEXT NOT NULL DEFAULT '',
                forma_preco TEXT NOT NULL DEFAULT 'nao_identificada',
                forma_original TEXT NOT NULL DEFAULT '',
                segmento_preco TEXT NOT NULL DEFAULT 'nao_identificado',
                preco_yuan_ton REAL NOT NULL CHECK (preco_yuan_ton > 0),
                unidade_original TEXT NOT NULL,
                url TEXT NOT NULL,
                trecho_original TEXT NOT NULL,
                nome_encontrado TEXT NOT NULL,
                posicao_texto INTEGER NOT NULL,
                regra_aplicada TEXT NOT NULL,
                confianca TEXT NOT NULL CHECK (
                    confianca IN ('alta', 'media', 'baixa')
                ),
                extractor_version TEXT NOT NULL,
                catalog_version TEXT NOT NULL,
                FOREIGN KEY (id_relatorio)
                    REFERENCES relatorios(id_relatorio) ON DELETE CASCADE,
                UNIQUE (
                    id_relatorio, produto_chines, concentracao, forma_preco,
                    forma_original, segmento_preco, preco_yuan_ton,
                    posicao_texto
                )
            );

            CREATE TABLE IF NOT EXISTS revisao_manual (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                id_relatorio INTEGER NOT NULL,
                data_relatorio TEXT,
                produto_sugerido TEXT,
                preco_yuan_ton REAL,
                trecho_original TEXT NOT NULL,
                motivo TEXT NOT NULL,
                confianca TEXT NOT NULL,
                decisao TEXT NOT NULL DEFAULT '',
                observacao TEXT NOT NULL DEFAULT '',
                responsavel TEXT NOT NULL DEFAULT '',
                FOREIGN KEY (id_relatorio)
                    REFERENCES relatorios(id_relatorio) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_corrigido_precos_data
                ON precos(data_relatorio);
            CREATE INDEX IF NOT EXISTS idx_corrigido_precos_produto
                ON precos(produto_chines);
            CREATE INDEX IF NOT EXISTS idx_corrigido_relatorios_estado
                ON relatorios(estado_processamento);
        """)
        _ensure_price_columns(conn)
        conn.execute(
            "INSERT OR REPLACE INTO metadata(chave, valor) VALUES (?, ?)",
            ("schema_version", SCHEMA_VERSION),
        )
        conn.execute(
            "INSERT OR REPLACE INTO metadata(chave, valor) VALUES (?, ?)",
            ("extractor_version", EXTRACTOR_VERSION),
        )


def set_metadata(key: str, value: str) -> None:
    with connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO metadata(chave, valor) VALUES (?, ?)",
            (key, value),
        )


def report_exists(report_id: int) -> bool:
    with connection() as conn:
        return conn.execute(
            "SELECT 1 FROM relatorios WHERE id_relatorio = ?", (report_id,)
        ).fetchone() is not None


def upsert_report(report: dict) -> None:
    """Inclui relatório novo sem apagar processamento histórico existente."""
    with connection() as conn:
        conn.execute("""
            INSERT INTO relatorios (
                id_relatorio, url_solicitada, url_final, codigo_http,
                data_relatorio, titulo, texto_completo, html_bruto,
                hash_conteudo, eh_mercado, estado_processamento, data_coleta
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pendente', ?)
            ON CONFLICT(id_relatorio) DO UPDATE SET
                url_final = excluded.url_final,
                codigo_http = excluded.codigo_http,
                data_relatorio = excluded.data_relatorio,
                titulo = excluded.titulo,
                texto_completo = excluded.texto_completo,
                html_bruto = COALESCE(excluded.html_bruto, relatorios.html_bruto),
                hash_conteudo = excluded.hash_conteudo,
                eh_mercado = excluded.eh_mercado
        """, (
            report["id_relatorio"],
            report["url_solicitada"],
            report.get("url_final"),
            report.get("codigo_http"),
            report.get("data_relatorio"),
            report.get("titulo"),
            report.get("texto_completo", ""),
            report.get("html_bruto"),
            report.get("hash_conteudo"),
            1 if report.get("eh_mercado") else 0,
            report.get("data_coleta")
            or datetime.now().isoformat(timespec="seconds"),
        ))


def pending_reports(force_reprocess: bool = False) -> list[tuple]:
    with connection() as conn:
        if force_reprocess:
            where = "eh_mercado = 1"
        else:
            # Casos em revisão permanecem intactos até decisão humana ou uma
            # reconstrução completa explicitamente solicitada.
            where = (
                "eh_mercado = 1 AND estado_processamento IN "
                "('pendente', 'falha_extracao')"
            )
        return conn.execute("""
            SELECT id_relatorio, url_solicitada, data_relatorio, texto_completo
            FROM relatorios
            WHERE """ + where + """
            ORDER BY id_relatorio
        """).fetchall()


def replace_report_results(
    report_id: int,
    prices: list[dict],
    reviews: list[dict],
    state: str,
    message: str = "",
) -> None:
    """Troca atomicamente o resultado de um relatório.

    Se qualquer inserção falhar, o resultado anterior continua intacto.
    """
    if state not in VALID_STATES:
        raise ValueError(f"Estado inválido: {state}")

    with connection() as conn:
        # Aprovações humanas permanecem válidas mesmo quando o relatório é
        # reprocessado automaticamente em uma coleta completa.
        conn.execute("""
            DELETE FROM precos
            WHERE id_relatorio = ?
              AND regra_aplicada <> 'revisao_manual_aprovada'
        """, (report_id,))
        conn.execute(
            """
            DELETE FROM revisao_manual
            WHERE id_relatorio = ?
              AND (
                    COALESCE(decisao, '') = ''
                    OR responsavel LIKE 'Regra autom%'
                  )
            """,
            (report_id,)
        )
        for price in prices:
            conn.execute("""
                INSERT OR IGNORE INTO precos (
                    id_relatorio, data_relatorio, produto_chines,
                    produto_ingles, produto_portugues, categoria,
                    concentracao, forma_preco, forma_original, segmento_preco,
                    preco_yuan_ton, unidade_original, url, trecho_original,
                    nome_encontrado, posicao_texto, regra_aplicada,
                    confianca, extractor_version,
                    catalog_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                report_id,
                price["data_relatorio"],
                price["produto_chines"],
                price["produto_ingles"],
                price["produto_portugues"],
                price["categoria"],
                price.get("concentracao") or "",
                price.get("forma_preco") or "nao_identificada",
                price.get("forma_original") or "",
                price.get("segmento_preco") or "nao_identificado",
                price["preco_yuan_ton"],
                price["unidade_original"],
                price["url"],
                price["trecho_original"],
                price["nome_encontrado"],
                price["posicao_texto"],
                price["regra_aplicada"],
                price["confianca"],
                price["extractor_version"],
                price["catalog_version"],
            ))
        for review in reviews:
            existing_resolved = conn.execute("""
                SELECT trecho_original FROM revisao_manual
                WHERE id_relatorio = ?
                  AND COALESCE(preco_yuan_ton, -1) = COALESCE(?, -1)
                  AND COALESCE(decisao, '') <> ''
                  AND COALESCE(responsavel, '') NOT LIKE 'Regra autom%'
            """, (
                report_id,
                review.get("preco_yuan_ton"),
            )).fetchall()
            review_excerpt_key = _normalized_review_excerpt(
                review["trecho_original"]
            )
            if existing_resolved:
                if any(
                    _normalized_review_excerpt(row[0]) == review_excerpt_key
                    for row in existing_resolved
                ):
                    continue
            conn.execute("""
                INSERT INTO revisao_manual (
                    id_relatorio, data_relatorio, produto_sugerido,
                    preco_yuan_ton, trecho_original, motivo, confianca
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                report_id,
                review.get("data_relatorio"),
                review.get("produto_sugerido", ""),
                review.get("preco_yuan_ton"),
                review["trecho_original"],
                review["motivo"],
                review.get("confianca", "baixa"),
            ))
        conn.execute("""
            UPDATE relatorios
            SET estado_processamento = ?, mensagem_estado = ?
            WHERE id_relatorio = ?
        """, (state, message, report_id))


def apply_manual_review_decisions(
    decisions: list[dict],
    catalog_version: str,
) -> dict:
    """Aplica decisões humanas em uma única transação.

    A função recebe decisões já validadas pelo importador. Se qualquer item
    falhar, nenhuma decisão parcial é gravada.
    """
    result = {"incluidos": 0, "nao_incluidos": 0, "corrigidos": 0}
    with connection() as conn:
        affected_reports = set()
        for item in decisions:
            review = conn.execute("""
                SELECT id_relatorio, data_relatorio, preco_yuan_ton,
                       trecho_original, decisao
                FROM revisao_manual
                WHERE id = ?
            """, (item["review_id"],)).fetchone()
            if review is None:
                raise ValueError(
                    f"O caso {item['review_id']} não existe mais no banco."
                )
            if review[4]:
                raise ValueError(
                    f"O caso {item['review_id']} já foi incorporado."
                )

            report_id, report_date, price, excerpt, _ = review
            affected_reports.add(report_id)
            decision = item["decision"]

            if decision in {"Incluir", "Corrigir"}:
                product = item["product"]
                report = conn.execute("""
                    SELECT url_solicitada FROM relatorios
                    WHERE id_relatorio = ?
                """, (report_id,)).fetchone()
                if price is None or price <= 0:
                    raise ValueError(
                        f"O caso {item['review_id']} não possui preço válido."
                    )
                conn.execute("""
                    INSERT OR IGNORE INTO precos (
                        id_relatorio, data_relatorio, produto_chines,
                        produto_ingles, produto_portugues, categoria,
                        concentracao, preco_yuan_ton, unidade_original, url,
                        trecho_original, nome_encontrado, posicao_texto,
                        regra_aplicada, confianca, extractor_version,
                        catalog_version
                    ) VALUES (?, ?, ?, ?, ?, ?, '', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    report_id,
                    report_date,
                    product["chines"],
                    product["ingles"],
                    product["portugues"],
                    product["categoria"],
                    price,
                    "Aprovado em revisão manual",
                    report[0],
                    excerpt,
                    item["product_text"],
                    -item["review_id"],
                    "revisao_manual_aprovada",
                    "alta",
                    "manual",
                    catalog_version,
                ))
                result[
                    "incluidos" if decision == "Incluir" else "corrigidos"
                ] += 1
            else:
                result["nao_incluidos"] += 1

            conn.execute("""
                UPDATE revisao_manual
                SET decisao = ?, observacao = ?, responsavel = ?
                WHERE id = ?
            """, (
                decision,
                item["observation"],
                item["responsible"],
                item["review_id"],
            ))

        for report_id in affected_reports:
            pending = conn.execute("""
                SELECT COUNT(*) FROM revisao_manual
                WHERE id_relatorio = ?
                  AND COALESCE(decisao, '') = ''
            """, (report_id,)).fetchone()[0]
            if pending:
                continue
            price_count = conn.execute("""
                SELECT COUNT(*) FROM precos WHERE id_relatorio = ?
            """, (report_id,)).fetchone()[0]
            state = "extraido" if price_count else "sem_preco_confirmado"
            conn.execute("""
                UPDATE relatorios
                SET estado_processamento = ?,
                    mensagem_estado = 'Revisão manual incorporada.'
                WHERE id_relatorio = ?
            """, (state, report_id))

    result["total"] = len(decisions)
    return result


def fetch_prices(high_confidence_only: bool = True) -> list[tuple]:
    where = "WHERE confianca = 'alta'" if high_confidence_only else ""
    with connection() as conn:
        return conn.execute(f"""
            SELECT data_relatorio, id_relatorio, produto_chines,
                   produto_ingles, produto_portugues, categoria,
                   concentracao, forma_preco, forma_original, segmento_preco,
                   preco_yuan_ton, unidade_original, url,
                   trecho_original, regra_aplicada, confianca
            FROM precos
            {where}
            ORDER BY data_relatorio, produto_chines, preco_yuan_ton
        """).fetchall()


def fetch_reports() -> list[tuple]:
    with connection() as conn:
        return conn.execute("""
            SELECT id_relatorio, data_relatorio, titulo, eh_mercado,
                   estado_processamento, url_solicitada, data_coleta,
                   mensagem_estado
            FROM relatorios
            ORDER BY data_relatorio, id_relatorio
        """).fetchall()


def fetch_reviews() -> list[tuple]:
    with connection() as conn:
        return conn.execute("""
            SELECT r.id, r.id_relatorio, r.data_relatorio,
                   r.produto_sugerido, r.preco_yuan_ton,
                   r.trecho_original, r.motivo, r.confianca,
                   r.decisao, r.observacao, r.responsavel
            FROM revisao_manual r
            ORDER BY r.data_relatorio, r.id_relatorio, r.id
        """).fetchall()


def resolve_unknown_reviews(catalog=None) -> int:
    """Encerra cotações fora do catálogo sem descartá-las da auditoria."""
    with connection() as conn:
        if catalog is not None:
            unknowns = conn.execute("""
                SELECT id, trecho_original, preco_yuan_ton
                FROM revisao_manual
                WHERE produto_sugerido = 'produto_desconhecido'
            """).fetchall()
            for review_id, excerpt, price_yuan in unknowns:
                assessment, match = _review_catalog_assessment(
                    catalog, excerpt, price_yuan
                )
                if assessment == "ambiguous":
                    conn.execute("""
                        UPDATE revisao_manual
                        SET motivo = CASE
                                WHEN motivo LIKE '%referencia oficial ambigua%'
                                THEN motivo
                                ELSE motivo || ' Caso com referencia oficial ambigua; revisar manualmente.'
                            END,
                            decisao = '',
                            observacao = '',
                            responsavel = ''
                        WHERE id = ?
                    """, (review_id,))
                    continue
                if assessment != "safe" or not match:
                    continue
                _, product = match
                conn.execute("""
                    UPDATE revisao_manual
                    SET produto_sugerido = ?,
                        motivo = motivo || ' Alias oficial encontrado no trecho; revisar manualmente.',
                        decisao = '',
                        observacao = '',
                        responsavel = ''
                    WHERE id = ?
                """, (product["portugues"], review_id))

        cursor = conn.execute("""
            UPDATE revisao_manual
            SET decisao = 'Não incluir',
                observacao = ?,
                responsavel = 'Regra automática - catálogo oficial'
            WHERE produto_sugerido = 'produto_desconhecido'
              AND COALESCE(decisao, '') = ''
              AND motivo NOT LIKE '%referencia oficial ambigua%'
        """, (
            "Nome não pertence ao catálogo oficial. Mantido somente para "
            "auditoria; não entra no Excel operacional.",
        ))
        resolved = cursor.rowcount
        # Depois que todos os casos de um relatório foram encerrados, seu
        # estado volta a refletir o resultado operacional efetivo.
        conn.execute("""
            UPDATE relatorios
            SET estado_processamento = CASE
                    WHEN EXISTS (
                        SELECT 1 FROM precos p
                        WHERE p.id_relatorio = relatorios.id_relatorio
                    ) THEN 'extraido'
                    ELSE 'sem_preco_confirmado'
                END,
                mensagem_estado = CASE
                    WHEN EXISTS (
                        SELECT 1 FROM precos p
                        WHERE p.id_relatorio = relatorios.id_relatorio
                    ) THEN 'Preços seguros extraídos; itens fora do catálogo encerrados.'
                    ELSE 'Somente itens fora do catálogo; nenhum preço operacional.'
                END
            WHERE estado_processamento = 'revisao_manual'
              AND NOT EXISTS (
                  SELECT 1 FROM revisao_manual r
                  WHERE r.id_relatorio = relatorios.id_relatorio
                    AND COALESCE(r.decisao, '') = ''
              )
        """)
        return resolved


def _normalized_review_excerpt(value: str) -> str:
    return re.sub(r"\s+", "", value or "")


def deduplicate_auto_rejected_reviews() -> int:
    """Remove duplicatas automáticas já rejeitadas sem tocar decisões humanas."""
    with connection() as conn:
        rows = conn.execute("""
            SELECT id, id_relatorio, preco_yuan_ton, trecho_original, decisao
            FROM revisao_manual
            WHERE produto_sugerido = 'produto_desconhecido'
              AND decisao = 'Não incluir'
              AND responsavel LIKE 'Regra autom%'
            ORDER BY id
        """).fetchall()
        seen = set()
        duplicate_ids = []
        for row in rows:
            key = (
                row[1],
                round(row[2] or 0, 6),
                _normalized_review_excerpt(row[3]),
                row[4],
            )
            if key in seen:
                duplicate_ids.append(row[0])
            else:
                seen.add(key)
        if not duplicate_ids:
            return 0
        placeholders = ",".join("?" for _ in duplicate_ids)
        conn.execute(
            f"DELETE FROM revisao_manual WHERE id IN ({placeholders})",
            duplicate_ids,
        )
        return len(duplicate_ids)


def fetch_metadata() -> dict[str, str]:
    with connection() as conn:
        return dict(conn.execute("SELECT chave, valor FROM metadata").fetchall())


def quality_checks(catalog=None) -> list[dict]:
    """Executa alertas objetivos que acompanham cada publicação."""
    checks = []
    with connection() as conn:
        quote_without_price = conn.execute("""
            SELECT COUNT(*)
            FROM relatorios r
            WHERE r.texto_completo LIKE '%报价%'
              AND NOT EXISTS (
                  SELECT 1 FROM precos p
                  WHERE p.id_relatorio = r.id_relatorio
              )
        """).fetchone()[0]
        repeated_titles = conn.execute("""
            SELECT titulo, COUNT(*) quantidade
            FROM relatorios
            WHERE COALESCE(titulo, '') <> ''
            GROUP BY titulo
            HAVING COUNT(*) > 10
            ORDER BY quantidade DESC
        """).fetchall()
        short_texts = conn.execute("""
            SELECT COUNT(*) FROM relatorios
            WHERE LENGTH(texto_completo) < 200
        """).fetchone()[0]
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        duplicate_groups = conn.execute("""
            SELECT COUNT(*) FROM (
                SELECT id_relatorio, produto_chines, concentracao,
                       forma_preco, forma_original, segmento_preco,
                       preco_yuan_ton, posicao_texto, COUNT(*) quantidade
                FROM precos
                GROUP BY id_relatorio, produto_chines, concentracao,
                         forma_preco, forma_original, segmento_preco,
                         preco_yuan_ton, posicao_texto
                HAVING COUNT(*) > 1
            )
        """).fetchone()[0]
        extreme_prices = conn.execute("""
            SELECT COUNT(*) FROM precos WHERE preco_yuan_ton >= ?
        """, (EXTREME_PRICE_YUAN_TON,)).fetchone()[0]
        excessive_groups = conn.execute("""
            SELECT COUNT(*) FROM (
                SELECT id_relatorio, produto_chines, COUNT(*) quantidade
                FROM precos
                GROUP BY id_relatorio, produto_chines
                HAVING COUNT(*) > ?
            )
        """, (MAX_PRICES_PER_PRODUCT_REPORT,)).fetchone()[0]
        business_duplicate_groups = conn.execute("""
            SELECT COUNT(*) FROM (
                SELECT id_relatorio, produto_chines, concentracao,
                       forma_preco, forma_original, segmento_preco,
                       preco_yuan_ton,
                       REPLACE(REPLACE(trecho_original, ' ', ''), char(10), '')
                           trecho_normalizado,
                       COUNT(*) quantidade
                FROM precos
                GROUP BY id_relatorio, produto_chines, concentracao,
                         forma_preco, forma_original, segmento_preco,
                         preco_yuan_ton, trecho_normalizado
                HAVING COUNT(*) > 1
            )
        """).fetchone()[0]
        duplicate_without_excerpt_groups = conn.execute("""
            SELECT COUNT(*) FROM (
                SELECT id_relatorio, produto_chines, concentracao,
                       forma_preco, forma_original, segmento_preco,
                       preco_yuan_ton, COUNT(*) quantidade
                FROM precos
                GROUP BY id_relatorio, produto_chines, concentracao,
                         forma_preco, forma_original, segmento_preco,
                         preco_yuan_ton
                HAVING COUNT(*) > 1
            )
        """).fetchone()[0]
        divergent_groups = conn.execute("""
            SELECT COUNT(*) FROM (
                SELECT id_relatorio, produto_chines, concentracao,
                       forma_preco, segmento_preco,
                       COUNT(DISTINCT preco_yuan_ton) quantidade
                FROM precos
                GROUP BY id_relatorio, produto_chines, concentracao,
                         forma_preco, segmento_preco
                HAVING COUNT(DISTINCT preco_yuan_ton) > 1
            )
        """).fetchone()[0]
        high_auto_rejected = conn.execute("""
            SELECT COUNT(*)
            FROM revisao_manual
            WHERE produto_sugerido = 'produto_desconhecido'
              AND decisao = 'Não incluir'
              AND COALESCE(preco_yuan_ton, 0) >= 100000
        """).fetchone()[0]
        missing_concentration = conn.execute("""
            SELECT COUNT(*)
            FROM precos
            WHERE COALESCE(concentracao, '') = ''
              AND trecho_original LIKE '%含量%'
        """).fetchone()[0]
        product_price_lists = conn.execute("""
            SELECT COUNT(DISTINCT id_relatorio)
            FROM precos
            WHERE trecho_original LIKE '%、%'
              AND (
                  LENGTH(trecho_original)
                  - LENGTH(REPLACE(trecho_original, '报', ''))
              ) >= 2
        """).fetchone()[0]
        unknown_reviews = conn.execute("""
            SELECT id, trecho_original, preco_yuan_ton
            FROM revisao_manual
            WHERE produto_sugerido = 'produto_desconhecido'
              AND (
                  COALESCE(decisao, '') = ''
                  OR responsavel LIKE 'Regra autom%'
              )
        """).fetchall()

    unknown_with_alias = 0
    if catalog is not None:
        unknown_with_alias = sum(
            1 for _, excerpt, price_yuan in unknown_reviews
            if _review_catalog_assessment(
                catalog, excerpt, price_yuan
            )[0] != "none"
        )

    checks.extend([
        {
            "verificacao": "Relatórios com termo de cotação e zero preços",
            "resultado": quote_without_price,
            "status": "ATENÇÃO" if quote_without_price else "OK",
        },
        {
            "verificacao": "Relatórios com texto muito curto",
            "resultado": short_texts,
            "status": "ATENÇÃO" if short_texts else "OK",
        },
        {
            "verificacao": "Grupos de preços duplicados",
            "resultado": duplicate_groups,
            "status": "ATENÇÃO" if duplicate_groups else "OK",
        },
        {
            "verificacao": "Integridade do banco",
            "resultado": integrity,
            "status": "OK" if integrity == "ok" else "ERRO",
        },
        {
            "verificacao": "Preços acima do limite de alerta",
            "resultado": extreme_prices,
            "status": "ATENÇÃO" if extreme_prices else "OK",
        },
        {
            "verificacao": "Produto com preços demais no mesmo relatório",
            "resultado": excessive_groups,
            "status": "ATENÇÃO" if excessive_groups else "OK",
        },
        {
            "verificacao": "Produto desconhecido contendo alias oficial",
            "resultado": unknown_with_alias,
            "status": "ATENÇÃO" if unknown_with_alias else "OK",
        },
        {
            "verificacao": "Duplicidade operacional ignorando posição",
            "resultado": business_duplicate_groups,
            "status": "ATENÇÃO" if business_duplicate_groups else "OK",
        },
        {
            "verificacao": "Duplicidade operacional sem considerar trecho",
            "resultado": duplicate_without_excerpt_groups,
            "status": "MONITORAR" if duplicate_without_excerpt_groups else "OK",
        },
        {
            "verificacao": (
                "Mesmo produto, forma, concentração e segmento com preços divergentes"
            ),
            "resultado": divergent_groups,
            "status": "ATENÇÃO" if divergent_groups else "OK",
        },
        {
            "verificacao": "Revisões automáticas Não incluir com preço alto",
            "resultado": high_auto_rejected,
            "status": "ATENÇÃO" if high_auto_rejected else "OK",
        },
        {
            "verificacao": "Trechos com teor no texto e concentração vazia",
            "resultado": missing_concentration,
            "status": "ATENÇÃO" if missing_concentration else "OK",
        },
        {
            "verificacao": "Relatórios com possível lista de produtos e preços",
            "resultado": product_price_lists,
            "status": "ATENÇÃO" if product_price_lists else "OK",
        },
        {
            "verificacao": "Títulos repetidos mais de 10 vezes",
            "resultado": "; ".join(
                f"{title}: {count}" for title, count in repeated_titles
            ) or "Nenhum",
            "status": "ATENÇÃO" if repeated_titles else "OK",
        },
    ])
    return checks
