#!/usr/bin/env python3
"""Importa apenas empresas abertas a partir de uma data (leads recentes).

Muito mais leve que o import completo: varre os zips em streaming e guarda só
estabelecimentos com data_inicio_atividade >= corte, mais as empresas e o
Simples correspondentes. Bom pra rodar mensalmente quando sai lote novo.

Uso: python scripts/import_recentes.py -p 2026-06-14 --desde 20260101
"""

import csv
import io
import sys
import zipfile

import click

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))

from src.config import RAW_DIR, RF_FILES
from src.etl.database import get_connection, init_db, insert_reference
from src.etl.parser import parse_reference_zip

BATCH = 20_000


def _rows(zip_path):
    z = zipfile.ZipFile(zip_path)
    with z.open(z.namelist()[0]) as fh:
        yield from csv.reader(io.TextIOWrapper(fh, encoding="latin-1"), delimiter=";")


def _insert(conn, table, cols, rows):
    ph = ",".join("?" * cols)
    total = 0
    batch = []
    for r in rows:
        batch.append(r)
        if len(batch) >= BATCH:
            conn.executemany(f"INSERT OR REPLACE INTO {table} VALUES ({ph})", batch)
            total += len(batch)
            batch = []
    if batch:
        conn.executemany(f"INSERT OR REPLACE INTO {table} VALUES ({ph})", batch)
        total += len(batch)
    return total


@click.command()
@click.option("--period", "-p", required=True, help="Período YYYY-MM-DD do lote baixado")
@click.option("--desde", default="20260101", help="Data de corte YYYYMMDD (inclusive)")
def main(period: str, desde: str):
    data_dir = RAW_DIR / period
    if not data_dir.exists():
        click.echo(f"Diretório não encontrado: {data_dir}")
        return

    conn = get_connection()
    init_db(conn)

    # 1) Estabelecimentos: filtra por data_inicio_atividade (coluna 10) e coleta as raízes
    raizes: set[str] = set()

    def estab_filtrados():
        for fname in RF_FILES["estabelecimentos"]:
            zp = data_dir / fname
            if not zp.exists():
                continue
            click.echo(f"  varrendo {fname}...")
            for r in _rows(zp):
                if len(r) >= 11 and r[10] >= desde:
                    raizes.add(r[0])
                    yield r

    n_estab = _insert(conn, "estabelecimentos", 30, estab_filtrados())
    conn.commit()
    click.echo(f"Estabelecimentos (>= {desde}): {n_estab:,} | raízes: {len(raizes):,}")

    # 2) Empresas e Simples: só as raízes coletadas
    def filtra_por_raiz(kind):
        for fname in RF_FILES[kind]:
            zp = data_dir / fname
            if not zp.exists():
                continue
            for r in _rows(zp):
                if r and r[0] in raizes:
                    yield r

    n_emp = _insert(conn, "empresas", 7, filtra_por_raiz("empresas"))
    n_simp = _insert(conn, "simples", 7, filtra_por_raiz("simples"))
    conn.commit()
    click.echo(f"Empresas: {n_emp:,} | Simples: {n_simp:,}")

    # 3) Tabelas de referência (cnaes etc), idempotente
    for ref in ("cnaes", "motivos", "municipios", "naturezas", "paises", "qualificacoes"):
        zp = data_dir / RF_FILES[ref][0]
        if zp.exists():
            insert_reference(conn, ref, parse_reference_zip(zp))
    conn.commit()

    conn.close()
    click.echo("Concluído.")


if __name__ == "__main__":
    main()
