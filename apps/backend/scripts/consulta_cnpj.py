#!/usr/bin/env python3
"""Consulta dados de empresa por CNPJ via APIs públicas ou banco local."""

import json
import sys

import click

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))


@click.command()
@click.argument("cnpj")
@click.option("--fonte", "-f", type=click.Choice(["opencnpj", "minhareceita", "local"]), default="opencnpj")
@click.option("--uf", help="Filtro por UF (apenas fonte=local)")
@click.option("--porte", help="Filtro por porte: 01=ME, 03=EPP, 05=Demais (apenas fonte=local)")
def main(cnpj: str, fonte: str, uf: str | None, porte: str | None):
    """Consulta dados de empresa por CNPJ."""
    if fonte == "opencnpj":
        from src.api.opencnpj import OpenCNPJClient

        with OpenCNPJClient() as client:
            data = client.consulta(cnpj)

    elif fonte == "minhareceita":
        from src.api.minhareceita import MinhaReceitaClient

        with MinhaReceitaClient() as client:
            data = client.consulta(cnpj)

    elif fonte == "local":
        from src.config import DB_PATH

        if not DB_PATH.exists():
            click.echo("Banco local não encontrado. Execute import_db.py primeiro.")
            return

        from src.etl.database import get_connection, query_empresas

        conn = get_connection()
        cnpj_basico = cnpj.replace(".", "").replace("/", "").replace("-", "")[:8]
        results = query_empresas(conn, uf=uf, porte=porte, limit=10)
        data = {"cnpj_basico": cnpj_basico, "resultados": results}
        conn.close()

    click.echo(json.dumps(data, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
