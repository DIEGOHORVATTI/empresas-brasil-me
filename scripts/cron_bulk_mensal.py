#!/usr/bin/env python3
"""Cron mensal: baixa dados RF + importa para SQLite num único comando."""

import asyncio
import logging
import sys

import click
from tqdm import tqdm

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))

from src.config import LOG_DIR, RAW_DIR, RF_FILES
from src.etl.database import get_connection, init_db, insert_batch, insert_reference
from src.etl.downloader import download_all
from src.etl.parser import parse_reference_zip, parse_zip

MAIN_TABLES = ["empresas", "estabelecimentos", "socios", "simples"]
REF_TABLES = ["cnaes", "motivos", "municipios", "naturezas", "paises", "qualificacoes"]

# Setup logging
LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "bulk_mensal.log"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)


@click.command()
@click.option("--period", "-p", default=None, help="Período YYYY-MM (auto-detecta se omitido)")
@click.option("--concurrent", "-c", default=3, type=int, help="Downloads simultâneos")
@click.option("--batch-size", "-b", default=10_000, type=int, help="Tamanho do batch de inserção")
@click.option("--skip-download", is_flag=True, help="Pular download (usar dados já baixados)")
@click.option("--skip-import", is_flag=True, help="Pular importação (apenas download)")
def main(
    period: str | None,
    concurrent: int,
    batch_size: int,
    skip_download: bool,
    skip_import: bool,
):
    """Executa pipeline completo: download RF + importação SQLite."""
    log.info("=== Início do pipeline mensal ===")

    # --- DOWNLOAD ---
    if not skip_download:
        log.info("Fase 1: Download dos dados da Receita Federal")
        file_names = [f for files in RF_FILES.values() for f in files]
        log.info(f"Baixando {len(file_names)} arquivos...")

        paths = asyncio.run(download_all(file_names, period, concurrent))
        log.info(f"Download concluído: {len(paths)} arquivos")

        # Descobrir o período usado (extrair do path)
        if paths and not period:
            period = paths[0].parent.name
            log.info(f"Período detectado: {period}")
    else:
        log.info("Download pulado (--skip-download)")

    if skip_import:
        log.info("Importação pulada (--skip-import)")
        log.info("=== Pipeline concluído ===")
        return

    # --- IMPORTAÇÃO ---
    if not period:
        # Tentar usar o diretório mais recente
        dirs = sorted(RAW_DIR.iterdir()) if RAW_DIR.exists() else []
        if dirs:
            period = dirs[-1].name
            log.info(f"Usando período mais recente: {period}")
        else:
            log.error("Nenhum dado disponível para importação. Execute o download primeiro.")
            return

    data_dir = RAW_DIR / period
    if not data_dir.exists():
        log.error(f"Diretório não encontrado: {data_dir}")
        return

    log.info(f"Fase 2: Importação dos dados ({period})")
    conn = get_connection()
    init_db(conn)

    for table_type in MAIN_TABLES + REF_TABLES:
        files = RF_FILES[table_type]
        log.info(f"Importando: {table_type} ({len(files)} arquivo(s))")

        for fname in tqdm(files, desc=table_type):
            zip_path = data_dir / fname
            if not zip_path.exists():
                log.warning(f"Arquivo não encontrado: {zip_path}")
                continue

            if table_type in MAIN_TABLES:
                records = parse_zip(zip_path, table_type)
                count = insert_batch(conn, table_type, records, batch_size)
            else:
                records = parse_reference_zip(zip_path)
                count = insert_reference(conn, table_type, records)

            log.info(f"  {fname}: {count:,} registros")

    conn.close()
    log.info("=== Pipeline concluído com sucesso ===")


if __name__ == "__main__":
    main()
