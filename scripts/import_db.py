#!/usr/bin/env python3
"""Importa dados baixados da RF para o banco SQLite."""

import sys

import click
from tqdm import tqdm

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))

from src.config import RAW_DIR, RF_FILES
from src.etl.database import get_connection, init_db, insert_batch, insert_reference
from src.etl.parser import parse_reference_zip, parse_zip

# Tabelas principais e seus tipos no parser
MAIN_TABLES = ["empresas", "estabelecimentos", "socios", "simples"]
REF_TABLES = ["cnaes", "motivos", "municipios", "naturezas", "paises", "qualificacoes"]


@click.command()
@click.option("--period", "-p", required=True, help="Período YYYY-MM dos dados baixados")
@click.option("--tipo", "-t", multiple=True, help="Tipos específicos para importar")
@click.option("--batch-size", "-b", default=10_000, type=int, help="Tamanho do batch de inserção")
def main(period: str, tipo: tuple[str, ...], batch_size: int):
    """Importa dados da RF para SQLite."""
    data_dir = RAW_DIR / period

    if not data_dir.exists():
        click.echo(f"Diretório não encontrado: {data_dir}")
        click.echo(f"Execute primeiro: python scripts/download_rf.py -p {period}")
        return

    conn = get_connection()
    init_db(conn)

    tipos_to_process = list(tipo) if tipo else MAIN_TABLES + REF_TABLES

    for table_type in tipos_to_process:
        if table_type not in RF_FILES:
            click.echo(f"Tipo desconhecido: {table_type}")
            continue

        files = RF_FILES[table_type]
        click.echo(f"\n--- Importando: {table_type} ({len(files)} arquivo(s)) ---")

        for fname in tqdm(files, desc=table_type):
            zip_path = data_dir / fname
            if not zip_path.exists():
                click.echo(f"  Arquivo não encontrado: {zip_path}")
                continue

            if table_type in MAIN_TABLES:
                records = parse_zip(zip_path, table_type)
                count = insert_batch(conn, table_type, records, batch_size)
            else:
                records = parse_reference_zip(zip_path)
                count = insert_reference(conn, table_type, records)

            tqdm.write(f"  {fname}: {count:,} registros")

    conn.close()
    click.echo("\nImportação concluída!")


if __name__ == "__main__":
    main()
