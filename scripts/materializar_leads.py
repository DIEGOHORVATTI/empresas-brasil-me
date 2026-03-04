"""
Materializa tabela leads_pool com DuckDB (leitura) → SQLite (escrita).
DuckDB faz scan colunar paralelo do SQLite, 10-50x mais rápido que SQLite puro.

Uso:
  uv run python scripts/materializar_leads.py
  uv run python scripts/materializar_leads.py --force
  uv run python scripts/materializar_leads.py --sem-socio   # pula sócios (mais rápido)
"""

import sqlite3
import sys
import time
from pathlib import Path

import click
import duckdb

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.config import DB_PATH

LEADS_POOL_DDL = """
DROP TABLE IF EXISTS leads_pool;
CREATE TABLE leads_pool (
    cnpj TEXT PRIMARY KEY,
    cnpj_basico TEXT,
    razao_social TEXT,
    nome_fantasia TEXT,
    email TEXT,
    telefone TEXT,
    telefone_2 TEXT,
    decisor TEXT,
    cargo_decisor TEXT,
    cnae TEXT,
    cnae_descricao TEXT,
    porte TEXT,
    capital_social REAL,
    uf TEXT,
    municipio_cod TEXT,
    cidade TEXT,
    bairro TEXT,
    endereco TEXT,
    cep TEXT,
    data_inicio TEXT,
    dias_abertura INTEGER,
    opcao_simples TEXT,
    opcao_mei TEXT,
    tem_email INTEGER,
    tem_telefone INTEGER,
    tem_decisor INTEGER
);
"""

LEADS_POOL_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_lp_cnae_uf ON leads_pool(cnae, uf);",
    "CREATE INDEX IF NOT EXISTS idx_lp_uf_cnae ON leads_pool(uf, cnae);",
    "CREATE INDEX IF NOT EXISTS idx_lp_municipio ON leads_pool(municipio_cod);",
    "CREATE INDEX IF NOT EXISTS idx_lp_data ON leads_pool(data_inicio);",
    "CREATE INDEX IF NOT EXISTS idx_lp_porte ON leads_pool(porte);",
    "CREATE INDEX IF NOT EXISTS idx_lp_flags ON leads_pool(tem_email, tem_telefone);",
    "CREATE INDEX IF NOT EXISTS idx_lp_cnpj_basico ON leads_pool(cnpj_basico);",
]

# DuckDB query: lê SQLite via extension, faz JOINs com scan colunar paralelo
DUCKDB_EXTRACT_SQL = """
SELECT
    est.cnpj_basico || est.cnpj_ordem || est.cnpj_dv AS cnpj,
    est.cnpj_basico,
    e.razao_social,
    est.nome_fantasia,
    est.email,
    CASE WHEN est.telefone_1 <> '' THEN est.ddd_1 || est.telefone_1 ELSE '' END AS telefone,
    CASE WHEN est.telefone_2 <> '' THEN est.ddd_2 || est.telefone_2 ELSE '' END AS telefone_2,
    est.cnae_fiscal_principal AS cnae,
    c.descricao AS cnae_descricao,
    e.porte_empresa AS porte,
    TRY_CAST(REPLACE(e.capital_social, ',', '.') AS DOUBLE) AS capital_social,
    est.uf,
    est.municipio AS municipio_cod,
    m.descricao AS cidade,
    est.bairro,
    TRIM(est.tipo_logradouro || ' ' || est.logradouro || ', ' || est.numero) AS endereco,
    est.cep,
    est.data_inicio_atividade AS data_inicio,
    CAST(DATEDIFF('day',
        TRY_CAST(est.data_inicio_atividade[1:4] || '-' || est.data_inicio_atividade[5:6] || '-' || est.data_inicio_atividade[7:8] AS DATE),
        CURRENT_DATE
    ) AS INTEGER) AS dias_abertura,
    si.opcao_simples,
    si.opcao_mei,
    CASE WHEN est.email <> '' THEN 1 ELSE 0 END AS tem_email,
    CASE WHEN est.telefone_1 <> '' THEN 1 ELSE 0 END AS tem_telefone
FROM sqlite_scan('{db_path}', 'estabelecimentos') est
JOIN sqlite_scan('{db_path}', 'empresas') e ON e.cnpj_basico = est.cnpj_basico
LEFT JOIN sqlite_scan('{db_path}', 'cnaes') c ON c.codigo = est.cnae_fiscal_principal
LEFT JOIN sqlite_scan('{db_path}', 'municipios') m ON m.codigo = est.municipio
LEFT JOIN sqlite_scan('{db_path}', 'simples') si ON si.cnpj_basico = est.cnpj_basico
WHERE est.situacao_cadastral = '02'
  AND est.matriz_filial = '1';
"""

DUCKDB_SOCIOS_SQL = """
SELECT cnpj_basico, nome_socio, qualificacao_socio
FROM (
    SELECT
        cnpj_basico, nome_socio, qualificacao_socio,
        ROW_NUMBER() OVER (
            PARTITION BY cnpj_basico
            ORDER BY CASE qualificacao_socio
                WHEN '49' THEN 1 WHEN '05' THEN 2 WHEN '22' THEN 3 ELSE 99
            END
        ) AS rn
    FROM sqlite_scan('{db_path}', 'socios')
    WHERE qualificacao_socio IN ('49', '05', '22')
)
WHERE rn = 1;
"""

BATCH_SIZE = 50_000


def get_sqlite_conn() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise SystemExit(f"Banco não encontrado: {DB_PATH}")
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA cache_size=-256000")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


@click.command()
@click.option("--force", is_flag=True, help="Re-gerar mesmo se tabela existe")
@click.option("--sem-socio", is_flag=True, help="Pula sócios (mais rápido)")
def main(force: bool, sem_socio: bool) -> None:
    """Materializa leads_pool via DuckDB (scan paralelo) → SQLite."""
    sqlite_conn = get_sqlite_conn()

    # Checa se já existe
    exists = sqlite_conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='leads_pool'"
    ).fetchone()[0]
    if exists and not force:
        total = sqlite_conn.execute("SELECT COUNT(*) FROM leads_pool").fetchone()[0]
        click.echo(f"leads_pool já existe com {total:,} registros. Use --force pra re-gerar.")
        sqlite_conn.close()
        return

    t0 = time.time()
    db_path_str = str(DB_PATH)

    # [1] Recria tabela no SQLite
    click.echo("[1/5] Recriando tabela leads_pool...")
    sqlite_conn.executescript(LEADS_POOL_DDL)
    sqlite_conn.commit()

    # [2] DuckDB: lê estabelecimentos + JOINs via scan colunar paralelo
    click.echo("[2/5] DuckDB: extraindo leads (scan paralelo)...")
    t1 = time.time()

    duck = duckdb.connect()
    duck.execute("INSTALL sqlite; LOAD sqlite;")

    sql = DUCKDB_EXTRACT_SQL.format(db_path=db_path_str)
    result = duck.execute(sql)

    # Inserir em batches no SQLite
    cols_count = 24  # número de colunas no SELECT
    placeholders = ", ".join("?" * cols_count)
    insert_sql = f"INSERT OR IGNORE INTO leads_pool (cnpj, cnpj_basico, razao_social, nome_fantasia, email, telefone, telefone_2, cnae, cnae_descricao, porte, capital_social, uf, municipio_cod, cidade, bairro, endereco, cep, data_inicio, dias_abertura, opcao_simples, opcao_mei, tem_email, tem_telefone, tem_decisor) VALUES ({placeholders})"

    total = 0
    while True:
        batch = result.fetchmany(BATCH_SIZE)
        if not batch:
            break
        # Adiciona tem_decisor=0 a cada row
        rows = [tuple(row) + (0,) for row in batch]
        sqlite_conn.executemany(insert_sql, rows)
        sqlite_conn.commit()
        total += len(rows)
        click.echo(f"      {total:>10,} leads inseridos...")

    click.echo(f"      TOTAL: {total:,} leads em {time.time() - t1:.0f}s")

    # [3] Sócios via DuckDB
    if not sem_socio:
        click.echo("[3/5] DuckDB: calculando melhor sócio por empresa...")
        t2 = time.time()

        socios_sql = DUCKDB_SOCIOS_SQL.format(db_path=db_path_str)
        socios_result = duck.execute(socios_sql)

        # Criar tabela temp no SQLite pra bulk update
        sqlite_conn.execute("CREATE TEMP TABLE _best_socio (cnpj_basico TEXT PRIMARY KEY, nome_socio TEXT, qualificacao_socio TEXT)")

        socios_total = 0
        while True:
            batch = socios_result.fetchmany(BATCH_SIZE)
            if not batch:
                break
            sqlite_conn.executemany(
                "INSERT OR IGNORE INTO _best_socio VALUES (?, ?, ?)",
                batch,
            )
            socios_total += len(batch)

        sqlite_conn.commit()
        click.echo(f"      {socios_total:,} sócios em {time.time() - t2:.0f}s")

        click.echo("[4/5] Atualizando decisores (com índice)...")
        t3 = time.time()
        # Índice no cnpj_basico da leads_pool ANTES do UPDATE (evita full scan / OOM)
        sqlite_conn.execute("CREATE INDEX IF NOT EXISTS _idx_lp_cb ON leads_pool(cnpj_basico)")
        sqlite_conn.commit()
        click.echo(f"      Índice leads_pool.cnpj_basico: {time.time() - t3:.0f}s")

        t3b = time.time()
        sqlite_conn.execute("""
            UPDATE leads_pool
            SET decisor = bs.nome_socio,
                cargo_decisor = q.descricao,
                tem_decisor = 1
            FROM _best_socio bs
            LEFT JOIN qualificacoes q ON q.codigo = bs.qualificacao_socio
            WHERE leads_pool.cnpj_basico = bs.cnpj_basico
        """)
        sqlite_conn.commit()
        sqlite_conn.execute("DROP TABLE IF EXISTS _best_socio")
        sqlite_conn.execute("DROP INDEX IF EXISTS _idx_lp_cb")
        click.echo(f"      Update: {time.time() - t3b:.0f}s")
    else:
        click.echo("[3-4/5] Sócios: PULADO (--sem-socio)")

    duck.close()

    # [5] Índices
    click.echo("[5/5] Criando índices...")
    t4 = time.time()
    for idx_sql in LEADS_POOL_INDEXES:
        sqlite_conn.execute(idx_sql)
    sqlite_conn.commit()
    click.echo(f"      Índices: {time.time() - t4:.0f}s")

    # Stats
    stats = sqlite_conn.execute("""
        SELECT
            COUNT(*) AS total,
            SUM(tem_email) AS com_email,
            SUM(tem_telefone) AS com_telefone,
            SUM(tem_decisor) AS com_decisor,
            SUM(CASE WHEN porte = '01' THEN 1 ELSE 0 END) AS me,
            SUM(CASE WHEN porte = '03' THEN 1 ELSE 0 END) AS epp,
            SUM(CASE WHEN porte = '05' THEN 1 ELSE 0 END) AS demais
        FROM leads_pool
    """).fetchone()

    click.echo(f"\n{'='*50}")
    click.echo(f"leads_pool materializada em {time.time() - t0:.0f}s")
    click.echo(f"{'='*50}")
    click.echo(f"  Total:       {stats[0]:>12,}")
    click.echo(f"  Com email:   {stats[1]:>12,} ({100*stats[1]//max(stats[0],1)}%)")
    click.echo(f"  Com telefone:{stats[2]:>12,} ({100*stats[2]//max(stats[0],1)}%)")
    click.echo(f"  Com decisor: {stats[3]:>12,} ({100*stats[3]//max(stats[0],1)}%)")
    click.echo(f"  ME:          {stats[4]:>12,}")
    click.echo(f"  EPP:         {stats[5]:>12,}")
    click.echo(f"  Demais:      {stats[6]:>12,}")

    sqlite_conn.close()


if __name__ == "__main__":
    main()
