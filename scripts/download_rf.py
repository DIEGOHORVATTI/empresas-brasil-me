#!/usr/bin/env python3
"""Baixa os arquivos de dados abertos de CNPJ da Receita Federal."""

import asyncio
import sys

import click

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))

from src.config import RF_FILES
from src.etl.downloader import download_all


@click.command()
@click.option("--period", "-p", default=None, help="Período YYYY-MM (auto-detecta se omitido)")
@click.option("--tipo", "-t", multiple=True, help="Tipos: empresas, estabelecimentos, socios, simples, cnaes, etc.")
@click.option("--limit", "-l", default=0, type=int, help="Limitar nº de arquivos (0=todos)")
@click.option("--concurrent", "-c", default=3, type=int, help="Downloads simultâneos")
def main(period: str | None, tipo: tuple[str, ...], limit: int, concurrent: int):
    """Baixa dados abertos de CNPJ da Receita Federal."""
    # Seleciona arquivos
    if tipo:
        file_names = []
        for t in tipo:
            if t in RF_FILES:
                file_names.extend(RF_FILES[t])
            else:
                click.echo(f"Tipo desconhecido: {t}. Opções: {', '.join(RF_FILES.keys())}")
                return
    else:
        file_names = [f for files in RF_FILES.values() for f in files]

    if limit:
        file_names = file_names[:limit]

    click.echo(f"Baixando {len(file_names)} arquivo(s)...")

    paths = asyncio.run(download_all(file_names, period, concurrent))
    click.echo(f"\nConcluído! {len(paths)} arquivo(s) baixado(s).")


if __name__ == "__main__":
    main()
