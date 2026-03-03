#!/usr/bin/env python3
"""Busca novas empresas e insere/exporta do SQLite.

Fontes (em ordem de prioridade):
1. API Casa dos Dados (requer CASADOSDADOS_API_KEY no ambiente)
2. Banco local SQLite (dados do último bulk RF)

O cron diário faz mais sentido com o banco local atualizado mensalmente:
- Busca empresas por data_inicio_atividade recente
- Exporta relatório das novas encontradas
"""

import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta

import click
import httpx

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))

from src.config import LOG_DIR
from src.etl.database import get_connection, init_db, insert_batch

# Setup logging
LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "novas_empresas.log"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)

CASADOSDADOS_URL = "https://api.casadosdados.com.br/v4/public/cnpj/search"


# ── Fonte 1: API Casa dos Dados (se tiver API key) ──────────────────────


def buscar_casadosdados(
    api_key: str,
    data_inicio: str,
    data_fim: str,
    uf: list[str] | None = None,
    cnae: list[str] | None = None,
    situacao: str = "ATIVA",
    excluir_mei: bool = False,
    com_email: bool = False,
    max_paginas: int = 100,
) -> list[dict]:
    """Busca empresas na API Casa dos Dados v4 com filtro por data de abertura."""
    client = httpx.Client(timeout=30)
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    todas: list[dict] = []

    for page in range(1, max_paginas + 1):
        payload = {
            "query": {
                "termo": [],
                "atividade_principal": cnae or [],
                "natureza_juridica": [],
                "uf": uf or [],
                "municipio": [],
                "situacao_cadastral": situacao,
                "cep": [],
                "ddd": [],
            },
            "range_query": {
                "data_abertura": {"gte": data_inicio, "lte": data_fim},
                "capital_social": {"lte": None, "gte": None},
            },
            "extras": {
                "somente_mei": False,
                "excluir_mei": excluir_mei,
                "com_email": com_email,
                "incluir_atividade_secundaria": False,
                "com_contato_telefonico": False,
                "somente_fixo": False,
                "somente_celular": False,
                "somente_matriz": False,
                "somente_filial": False,
            },
            "page": page,
        }

        try:
            resp = client.post(CASADOSDADOS_URL, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPStatusError as e:
            log.error(f"Erro HTTP {e.response.status_code} na API Casa dos Dados")
            break
        except Exception as e:
            log.error(f"Erro na requisição: {e}")
            break

        empresas = data.get("data", {}).get("cnpj", [])
        if not empresas:
            break

        todas.extend(empresas)
        log.info(f"  Página {page}: +{len(empresas)} (total: {len(todas)})")
        time.sleep(1.0)

    client.close()
    return todas


def mapear_api_para_empresa(item: dict) -> dict:
    """Mapeia resposta da API Casa dos Dados para tabela 'empresas'."""
    cnpj = item.get("cnpj", "").replace(".", "").replace("/", "").replace("-", "")
    porte_map = {"MICRO EMPRESA": "01", "EMPRESA DE PEQUENO PORTE": "03", "DEMAIS": "05"}
    nj = item.get("natureza_juridica", "")
    nj_code = nj.get("id", "") if isinstance(nj, dict) else str(nj)
    return {
        "cnpj_basico": cnpj[:8],
        "razao_social": item.get("razao_social", ""),
        "natureza_juridica": nj_code,
        "qualificacao_responsavel": "",
        "capital_social": str(item.get("capital_social", "0")),
        "porte_empresa": porte_map.get(item.get("porte", ""), "00"),
        "ente_federativo": "",
    }


def mapear_api_para_estabelecimento(item: dict) -> dict:
    """Mapeia resposta da API Casa dos Dados para tabela 'estabelecimentos'."""
    cnpj = item.get("cnpj", "").replace(".", "").replace("/", "").replace("-", "")
    data_abertura = (item.get("data_abertura", "") or "").replace("-", "")
    situacao_map = {"ATIVA": "02", "SUSPENSA": "03", "INAPTA": "04", "BAIXADA": "08"}
    cnae_data = item.get("atividade_principal", {})
    cnae_principal = cnae_data.get("id", "") if isinstance(cnae_data, dict) else str(cnae_data or "")
    return {
        "cnpj_basico": cnpj[:8],
        "cnpj_ordem": cnpj[8:12] if len(cnpj) >= 12 else "0001",
        "cnpj_dv": cnpj[12:14] if len(cnpj) >= 14 else "",
        "matriz_filial": "1",
        "nome_fantasia": item.get("nome_fantasia", ""),
        "situacao_cadastral": situacao_map.get(item.get("situacao_cadastral", ""), "02"),
        "data_situacao_cadastral": "",
        "motivo_situacao_cadastral": "",
        "cidade_exterior": "",
        "pais": "",
        "data_inicio_atividade": data_abertura,
        "cnae_fiscal_principal": cnae_principal,
        "cnae_fiscal_secundaria": "",
        "tipo_logradouro": "",
        "logradouro": item.get("logradouro", ""),
        "numero": item.get("numero", ""),
        "complemento": item.get("complemento", ""),
        "bairro": item.get("bairro", ""),
        "cep": item.get("cep", ""),
        "uf": item.get("uf", ""),
        "municipio": item.get("municipio", ""),
        "ddd_1": "",
        "telefone_1": item.get("telefone", ""),
        "ddd_2": "",
        "telefone_2": "",
        "ddd_fax": "",
        "fax": "",
        "email": item.get("email", "") or "",
        "situacao_especial": "",
        "data_situacao_especial": "",
    }


# ── Fonte 2: Banco local SQLite ─────────────────────────────────────────


def buscar_local(
    data_inicio: str,
    data_fim: str,
    uf: list[str] | None = None,
    cnae: str | None = None,
    situacao: str | None = None,
    limit: int = 10000,
) -> list[dict]:
    """Busca novas empresas no banco local por data_inicio_atividade."""
    conn = get_connection()
    conn.row_factory = __import__("sqlite3").Row

    # Converter datas para formato RF (YYYYMMDD)
    dt_inicio = data_inicio.replace("-", "")
    dt_fim = data_fim.replace("-", "")

    sql = """
        SELECT e.cnpj_basico, e.razao_social, e.natureza_juridica,
               e.qualificacao_responsavel, e.capital_social, e.porte_empresa,
               e.ente_federativo,
               es.cnpj_ordem, es.cnpj_dv, es.nome_fantasia, es.uf,
               es.municipio, es.cnae_fiscal_principal, es.situacao_cadastral,
               es.email, es.logradouro, es.numero, es.bairro, es.cep,
               es.ddd_1, es.telefone_1, es.data_inicio_atividade
        FROM estabelecimentos es
        JOIN empresas e ON e.cnpj_basico = es.cnpj_basico
        WHERE es.data_inicio_atividade BETWEEN ? AND ?
          AND es.matriz_filial = '1'
    """
    params: list[str] = [dt_inicio, dt_fim]

    if uf:
        placeholders = ",".join("?" for _ in uf)
        sql += f" AND es.uf IN ({placeholders})"
        params.extend(uf)
    if cnae:
        sql += " AND es.cnae_fiscal_principal = ?"
        params.append(cnae)
    if situacao:
        sql += " AND es.situacao_cadastral = ?"
        params.append(situacao)

    sql += " ORDER BY es.data_inicio_atividade DESC LIMIT ?"
    params.append(str(limit))

    rows = conn.execute(sql, params).fetchall()
    result = [dict(r) for r in rows]
    conn.close()
    return result


# ── CLI ──────────────────────────────────────────────────────────────────


@click.command()
@click.option("--dias", "-d", default=1, type=int, help="Buscar últimos N dias (default: 1)")
@click.option("--uf", "-u", multiple=True, help="Filtrar por UF (ex: SP, RJ)")
@click.option("--cnae", "-c", default=None, help="Filtrar por CNAE principal")
@click.option("--max-paginas", "-m", default=100, type=int, help="Máximo de páginas (API)")
@click.option("--limit", "-l", default=10000, type=int, help="Máximo de resultados (local)")
@click.option("--com-email", is_flag=True, help="Apenas empresas com e-mail (API)")
@click.option("--excluir-mei", is_flag=True, help="Excluir MEI (API)")
@click.option("--fonte", "-f", type=click.Choice(["auto", "api", "local"]), default="auto", help="Fonte de dados")
@click.option("--exportar", "-e", default=None, help="Exportar resultados para arquivo JSON")
@click.option("--dry-run", is_flag=True, help="Apenas buscar, não inserir no banco")
def main(
    dias: int,
    uf: tuple[str, ...],
    cnae: str | None,
    max_paginas: int,
    limit: int,
    com_email: bool,
    excluir_mei: bool,
    fonte: str,
    exportar: str | None,
    dry_run: bool,
):
    """Busca novas empresas abertas nos últimos N dias."""
    hoje = datetime.now()
    data_inicio = (hoje - timedelta(days=dias)).strftime("%Y-%m-%d")
    data_fim = hoje.strftime("%Y-%m-%d")

    log.info(f"Buscando empresas abertas entre {data_inicio} e {data_fim}")
    if uf:
        log.info(f"  Filtro UF: {', '.join(uf)}")
    if cnae:
        log.info(f"  Filtro CNAE: {cnae}")

    api_key = os.environ.get("CASADOSDADOS_API_KEY", "")
    usar_api = fonte == "api" or (fonte == "auto" and api_key)
    usar_local = fonte == "local" or (fonte == "auto" and not api_key)

    empresas: list[dict] = []
    source = ""

    # Tentar API Casa dos Dados (se tiver key)
    if usar_api:
        if not api_key:
            log.error("CASADOSDADOS_API_KEY não definida. Use --fonte local ou defina a variável.")
            return

        log.info("Buscando via API Casa dos Dados...")
        source = "api"
        empresas = buscar_casadosdados(
            api_key=api_key,
            data_inicio=data_inicio,
            data_fim=data_fim,
            uf=list(uf) if uf else None,
            cnae=[cnae] if cnae else None,
            excluir_mei=excluir_mei,
            com_email=com_email,
            max_paginas=max_paginas,
        )

    # Buscar no banco local
    if usar_local:
        log.info("Buscando no banco local...")
        source = "local"
        empresas = buscar_local(
            data_inicio=data_inicio,
            data_fim=data_fim,
            uf=list(uf) if uf else None,
            cnae=cnae,
            limit=limit,
        )

    log.info(f"Fonte: {source} | Total: {len(empresas)} empresas encontradas")

    if not empresas:
        log.info("Nenhuma empresa nova encontrada.")
        return

    # Exportar JSON se solicitado
    if exportar:
        with open(exportar, "w", encoding="utf-8") as f:
            json.dump(empresas, f, ensure_ascii=False, indent=2, default=str)
        log.info(f"Exportado para {exportar}")

    # Mostrar amostra
    log.info("Primeiras empresas encontradas:")
    for emp in empresas[:10]:
        if source == "api":
            log.info(f"  {emp.get('cnpj', '?')} - {emp.get('razao_social', '?')} ({emp.get('data_abertura', '?')})")
        else:
            cnpj = f"{emp['cnpj_basico']}{emp.get('cnpj_ordem', '')}{emp.get('cnpj_dv', '')}"
            log.info(f"  {cnpj} - {emp.get('razao_social', '?')} ({emp.get('data_inicio_atividade', '?')})")
    if len(empresas) > 10:
        log.info(f"  ... e mais {len(empresas) - 10}")

    # Inserir no banco (apenas para dados da API que ainda não estão no banco)
    if source == "api" and not dry_run:
        conn = get_connection()
        init_db(conn)
        emp_records = [mapear_api_para_empresa(item) for item in empresas]
        est_records = [mapear_api_para_estabelecimento(item) for item in empresas]
        inseridos_emp = insert_batch(conn, "empresas", emp_records)
        inseridos_est = insert_batch(conn, "estabelecimentos", est_records)
        conn.close()
        log.info(f"Inseridas {inseridos_emp} empresas, {inseridos_est} estabelecimentos")

    log.info("Concluído!")


if __name__ == "__main__":
    main()
