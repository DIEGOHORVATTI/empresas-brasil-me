import sqlite3
from collections.abc import Iterable
from pathlib import Path

from src.config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS empresas (
    cnpj_basico TEXT PRIMARY KEY,
    razao_social TEXT,
    natureza_juridica TEXT,
    qualificacao_responsavel TEXT,
    capital_social TEXT,
    porte_empresa TEXT,
    ente_federativo TEXT
);

CREATE TABLE IF NOT EXISTS estabelecimentos (
    cnpj_basico TEXT,
    cnpj_ordem TEXT,
    cnpj_dv TEXT,
    matriz_filial TEXT,
    nome_fantasia TEXT,
    situacao_cadastral TEXT,
    data_situacao_cadastral TEXT,
    motivo_situacao_cadastral TEXT,
    cidade_exterior TEXT,
    pais TEXT,
    data_inicio_atividade TEXT,
    cnae_fiscal_principal TEXT,
    cnae_fiscal_secundaria TEXT,
    tipo_logradouro TEXT,
    logradouro TEXT,
    numero TEXT,
    complemento TEXT,
    bairro TEXT,
    cep TEXT,
    uf TEXT,
    municipio TEXT,
    ddd_1 TEXT,
    telefone_1 TEXT,
    ddd_2 TEXT,
    telefone_2 TEXT,
    ddd_fax TEXT,
    fax TEXT,
    email TEXT,
    situacao_especial TEXT,
    data_situacao_especial TEXT,
    PRIMARY KEY (cnpj_basico, cnpj_ordem, cnpj_dv)
);

CREATE TABLE IF NOT EXISTS socios (
    cnpj_basico TEXT,
    identificador_socio TEXT,
    nome_socio TEXT,
    cnpj_cpf_socio TEXT,
    qualificacao_socio TEXT,
    data_entrada TEXT,
    pais TEXT,
    representante_legal TEXT,
    nome_representante TEXT,
    qualificacao_representante TEXT,
    faixa_etaria TEXT
);

CREATE TABLE IF NOT EXISTS simples (
    cnpj_basico TEXT PRIMARY KEY,
    opcao_simples TEXT,
    data_opcao_simples TEXT,
    data_exclusao_simples TEXT,
    opcao_mei TEXT,
    data_opcao_mei TEXT,
    data_exclusao_mei TEXT
);

CREATE TABLE IF NOT EXISTS cnaes (
    codigo TEXT PRIMARY KEY,
    descricao TEXT
);

CREATE TABLE IF NOT EXISTS motivos (
    codigo TEXT PRIMARY KEY,
    descricao TEXT
);

CREATE TABLE IF NOT EXISTS municipios (
    codigo TEXT PRIMARY KEY,
    descricao TEXT
);

CREATE TABLE IF NOT EXISTS naturezas (
    codigo TEXT PRIMARY KEY,
    descricao TEXT
);

CREATE TABLE IF NOT EXISTS paises (
    codigo TEXT PRIMARY KEY,
    descricao TEXT
);

CREATE TABLE IF NOT EXISTS qualificacoes (
    codigo TEXT PRIMARY KEY,
    descricao TEXT
);

CREATE INDEX IF NOT EXISTS idx_estabelecimentos_uf ON estabelecimentos(uf);
CREATE INDEX IF NOT EXISTS idx_estabelecimentos_cnae ON estabelecimentos(cnae_fiscal_principal);
CREATE INDEX IF NOT EXISTS idx_estabelecimentos_situacao ON estabelecimentos(situacao_cadastral);
CREATE INDEX IF NOT EXISTS idx_empresas_porte ON empresas(porte_empresa);
CREATE INDEX IF NOT EXISTS idx_socios_cnpj ON socios(cnpj_basico);
CREATE INDEX IF NOT EXISTS idx_simples_mei ON simples(opcao_mei);
"""


def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-64000")  # 64MB cache
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)


def insert_batch(
    conn: sqlite3.Connection,
    table: str,
    records: Iterable[dict],
    batch_size: int = 10_000,
) -> int:
    """Insere registros em batch com INSERT OR IGNORE."""
    total = 0
    batch: list[dict] = []

    for record in records:
        batch.append(record)
        if len(batch) >= batch_size:
            _flush(conn, table, batch)
            total += len(batch)
            batch.clear()

    if batch:
        _flush(conn, table, batch)
        total += len(batch)

    return total


def _flush(conn: sqlite3.Connection, table: str, batch: list[dict]) -> None:
    if not batch:
        return
    cols = list(batch[0].keys())
    placeholders = ", ".join("?" for _ in cols)
    col_names = ", ".join(cols)
    sql = f"INSERT OR IGNORE INTO {table} ({col_names}) VALUES ({placeholders})"
    conn.executemany(sql, [tuple(r[c] for c in cols) for r in batch])
    conn.commit()


def insert_reference(
    conn: sqlite3.Connection,
    table: str,
    records: Iterable[tuple[str, str]],
) -> int:
    total = 0
    batch: list[tuple[str, str]] = []
    for code, desc in records:
        batch.append((code, desc))
        if len(batch) >= 5_000:
            conn.executemany(
                f"INSERT OR IGNORE INTO {table} (codigo, descricao) VALUES (?, ?)",
                batch,
            )
            conn.commit()
            total += len(batch)
            batch.clear()

    if batch:
        conn.executemany(
            f"INSERT OR IGNORE INTO {table} (codigo, descricao) VALUES (?, ?)",
            batch,
        )
        conn.commit()
        total += len(batch)

    return total


def query_empresas(
    conn: sqlite3.Connection,
    uf: str | None = None,
    porte: str | None = None,
    cnae: str | None = None,
    situacao: str | None = None,
    limit: int = 100,
) -> list[dict]:
    """Consulta empresas com filtros opcionais."""
    sql = """
        SELECT e.*, es.nome_fantasia, es.uf, es.municipio, es.cnae_fiscal_principal,
               es.situacao_cadastral, es.email, es.logradouro, es.numero, es.bairro,
               es.cep, es.ddd_1, es.telefone_1,
               s.opcao_simples, s.opcao_mei
        FROM empresas e
        JOIN estabelecimentos es ON e.cnpj_basico = es.cnpj_basico
        LEFT JOIN simples s ON e.cnpj_basico = s.cnpj_basico
        WHERE es.matriz_filial = '1'
    """
    params: list[str] = []

    if uf:
        sql += " AND es.uf = ?"
        params.append(uf)
    if porte:
        sql += " AND e.porte_empresa = ?"
        params.append(porte)
    if cnae:
        sql += " AND es.cnae_fiscal_principal = ?"
        params.append(cnae)
    if situacao:
        sql += " AND es.situacao_cadastral = ?"
        params.append(situacao)

    sql += " LIMIT ?"
    params.append(str(limit))

    conn.row_factory = sqlite3.Row
    rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]
