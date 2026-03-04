"""
Extrai leads da tabela materializada leads_pool (queries < 1s).

Uso:
  uv run python scripts/extrair_leads.py --distribuicao
  uv run python scripts/extrair_leads.py --nicho advocacia --uf SP --com-email
  uv run python scripts/extrair_leads.py --nicho imobiliario --floripa --dias 365
  uv run python scripts/extrair_leads.py --nicho contabilidade --porte 03
  uv run python scripts/extrair_leads.py --cnae 6911701 --uf SC
  uv run python scripts/extrair_leads.py --nicho saude --floripa --dias 90

Nichos disponíveis:
  advocacia, imobiliario, contabilidade, construtoras, ecommerce,
  educacao, academias, saude, hotelaria, marketing
"""

import csv
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

import click

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.config import DB_PATH

NICHOS = {
    "advocacia": {
        "cnaes": ["6911701", "6911702", "6911703"],
        "nome": "Escritórios de Advocacia",
    },
    "imobiliario": {
        "cnaes": ["6810201", "6810202", "6821801", "6821802"],
        "nome": "Imobiliárias e Corretores",
    },
    "contabilidade": {
        "cnaes": ["6920601", "6920602"],
        "nome": "Escritórios de Contabilidade",
    },
    "construtoras": {
        "cnaes": ["4110700", "4120400", "4299501"],
        "nome": "Construtoras e Incorporadoras",
    },
    "ecommerce": {
        "cnaes": ["4751201", "4789099", "4789001"],
        "nome": "E-commerce e Lojas Online",
    },
    "educacao": {
        "cnaes": ["8512100", "8513900", "8520100"],
        "nome": "Escolas e Cursos Privados",
    },
    "academias": {
        "cnaes": ["9313100"],
        "nome": "Academias e Studios",
    },
    "saude": {
        "cnaes": [
            "8630504", "8630501", "8630502", "8630503",
            "8650003", "9602502", "8690999", "8630506",
            "8650004", "8650006", "8650002",
        ],
        "nome": "Saúde e Estética",
    },
    "hotelaria": {
        "cnaes": ["5510801", "5590601", "5590603"],
        "nome": "Hotelaria e Turismo",
    },
    "marketing": {
        "cnaes": ["7311400", "7312200"],
        "nome": "Agências de Marketing",
    },
}

MUNICIPIOS_FLORIPA = ["8105", "8233", "8327", "8045"]

COLS_CSV = [
    "cnae_descricao", "cnae", "nome_fantasia", "decisor", "cargo_decisor",
    "email", "telefone", "telefone_2", "razao_social", "cnpj", "porte",
    "capital_social", "dias_abertura", "data_inicio", "cidade", "uf",
    "bairro", "endereco", "cep",
]


def get_conn() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise SystemExit(f"Banco não encontrado: {DB_PATH}")
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA cache_size=-64000")
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.row_factory = sqlite3.Row
    # Verifica se leads_pool existe
    exists = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='leads_pool'"
    ).fetchone()[0]
    if not exists:
        raise SystemExit(
            "Tabela leads_pool não encontrada. Rode primeiro:\n"
            "  uv run python scripts/materializar_leads.py"
        )
    return conn


def mostrar_distribuicao(
    conn: sqlite3.Connection,
    ufs: tuple[str, ...],
    municipios: tuple[str, ...],
) -> None:
    """Mostra distribuição por nicho e UF."""
    where_parts = []
    params: list[str] = []

    if municipios:
        mun_ph = ", ".join("?" for _ in municipios)
        where_parts.append(f"municipio_cod IN ({mun_ph})")
        params.extend(municipios)
    if ufs:
        uf_ph = ", ".join("?" for _ in ufs)
        where_parts.append(f"uf IN ({uf_ph})")
        params.extend(ufs)

    where = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""

    # Por nicho
    click.echo(f"\n{'Nicho':<30} {'Total':>10} {'Email':>10} {'Tel':>10} {'Decisor':>10}")
    click.echo("-" * 75)

    total_geral = 0
    for slug, info in NICHOS.items():
        cnaes_ph = ", ".join("?" for _ in info["cnaes"])
        cnae_where = f"cnae IN ({cnaes_ph})"
        full_where = f"WHERE {cnae_where}" + (f" AND {' AND '.join(where_parts)}" if where_parts else "")

        row = conn.execute(f"""
            SELECT COUNT(*) AS total,
                   SUM(tem_email) AS email,
                   SUM(tem_telefone) AS tel,
                   SUM(tem_decisor) AS decisor
            FROM leads_pool {full_where}
        """, info["cnaes"] + params).fetchone()

        total = row["total"]
        total_geral += total
        if total > 0:
            click.echo(
                f"{info['nome']:<30} {total:>10,} {row['email']:>10,} "
                f"{row['tel']:>10,} {row['decisor']:>10,}"
            )

    click.echo(f"\n{'TOTAL':.<30} {total_geral:>10,}")

    # Por porte
    click.echo(f"\n{'Porte':<20} {'Total':>10}")
    click.echo("-" * 32)
    for row in conn.execute(f"""
        SELECT porte,
               CASE porte WHEN '01' THEN 'ME' WHEN '03' THEN 'EPP' WHEN '05' THEN 'Demais' ELSE porte END AS nome,
               COUNT(*) AS total
        FROM leads_pool {where}
        GROUP BY porte ORDER BY total DESC
    """, params).fetchall():
        click.echo(f"{row['nome']:<20} {row['total']:>10,}")

    # Top 10 UFs
    click.echo(f"\n{'UF':<6} {'Total':>10} {'Email':>10}")
    click.echo("-" * 28)
    for row in conn.execute(f"""
        SELECT uf, COUNT(*) AS total, SUM(tem_email) AS email
        FROM leads_pool {where}
        GROUP BY uf ORDER BY total DESC LIMIT 10
    """, params).fetchall():
        click.echo(f"{row['uf']:<6} {row['total']:>10,} {row['email']:>10,}")


@click.command()
@click.option("--nicho", type=click.Choice(list(NICHOS.keys())), help="Nicho pré-definido")
@click.option("--cnae", multiple=True, help="CNAE customizado (repetível)")
@click.option("--dias", default=0, help="Criadas nos últimos N dias (0=todas)")
@click.option("--uf", multiple=True, help="UF (repetível)")
@click.option("--municipio", multiple=True, help="Código município (repetível)")
@click.option("--floripa", is_flag=True, help="Atalho: Grande Florianópolis")
@click.option("--porte", multiple=True, help="Porte: 01=ME, 03=EPP, 05=Demais (repetível)")
@click.option("--com-email", is_flag=True, help="Só com email")
@click.option("--com-telefone", is_flag=True, help="Só com telefone")
@click.option("--com-decisor", is_flag=True, help="Só com sócio/decisor")
@click.option("--limit", default=0, help="Máximo de resultados")
@click.option("-o", "--output", default="", help="CSV de saída (auto-gerado se vazio)")
@click.option("--distribuicao", is_flag=True, help="Só mostra distribuição por nicho")
def main(
    nicho: str | None,
    cnae: tuple[str, ...],
    dias: int,
    uf: tuple[str, ...],
    municipio: tuple[str, ...],
    floripa: bool,
    porte: tuple[str, ...],
    com_email: bool,
    com_telefone: bool,
    com_decisor: bool,
    limit: int,
    output: str,
    distribuicao: bool,
) -> None:
    """Extrai leads da leads_pool materializada."""
    municipios = list(municipio)
    if floripa:
        municipios.extend(MUNICIPIOS_FLORIPA)
        if not uf:
            uf = ("SC",)

    municipios_tuple = tuple(set(municipios))
    conn = get_conn()

    if distribuicao:
        mostrar_distribuicao(conn, uf, municipios_tuple)
        conn.close()
        return

    # Montar filtros
    cnaes: list[str] = []
    nicho_nome = ""
    if nicho:
        cnaes = NICHOS[nicho]["cnaes"]
        nicho_nome = NICHOS[nicho]["nome"]
    if cnae:
        cnaes.extend(cnae)
        nicho_nome = nicho_nome or "Custom"

    if not cnaes:
        click.echo("Erro: informe --nicho ou --cnae")
        click.echo(f"\nNichos disponíveis: {', '.join(NICHOS.keys())}")
        conn.close()
        return

    where_parts = []
    params: list[str] = []

    # CNAE
    cnaes_ph = ", ".join("?" for _ in cnaes)
    where_parts.append(f"cnae IN ({cnaes_ph})")
    params.extend(cnaes)

    # Localização
    if municipios_tuple:
        mun_ph = ", ".join("?" for _ in municipios_tuple)
        where_parts.append(f"municipio_cod IN ({mun_ph})")
        params.extend(municipios_tuple)
    if uf:
        uf_ph = ", ".join("?" for _ in uf)
        where_parts.append(f"uf IN ({uf_ph})")
        params.extend(uf)

    # Porte
    if porte:
        p_ph = ", ".join("?" for _ in porte)
        where_parts.append(f"porte IN ({p_ph})")
        params.extend(porte)

    # Temporal
    if dias > 0:
        data_limite = (datetime.now() - timedelta(days=dias)).strftime("%Y%m%d")
        where_parts.append("data_inicio >= ?")
        params.append(data_limite)

    # Flags
    if com_email:
        where_parts.append("tem_email = 1")
    if com_telefone:
        where_parts.append("tem_telefone = 1")
    if com_decisor:
        where_parts.append("tem_decisor = 1")

    where_sql = " AND ".join(where_parts)

    sql = f"""
        SELECT {', '.join(COLS_CSV)}
        FROM leads_pool
        WHERE {where_sql}
        ORDER BY data_inicio DESC
    """
    if limit > 0:
        sql += f" LIMIT {limit}"

    # Info
    filtros = f"nicho={nicho_nome} UFs={uf or 'todas'} municipios={municipios_tuple or 'todos'}"
    if dias:
        filtros += f" dias={dias}"
    if porte:
        filtros += f" porte={porte}"
    click.echo(f"Filtros: {filtros}")
    click.echo(f"CNAEs: {', '.join(cnaes)}\n")

    rows = conn.execute(sql, params).fetchall()

    if not rows:
        click.echo("Nenhum resultado.")
        conn.close()
        return

    # Auto-gerar nome do output
    if not output:
        parts = [f"leads_{nicho or 'custom'}"]
        if uf:
            parts.append("_".join(uf).lower())
        if floripa:
            parts.append("floripa")
        if dias:
            parts.append(f"{dias}d")
        output = "_".join(parts) + ".csv"

    output_path = Path(output)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS_CSV)
        w.writeheader()
        for row in rows:
            w.writerow(dict(row))

    total = len(rows)
    com_email_n = sum(1 for r in rows if r["email"])
    com_tel_n = sum(1 for r in rows if r["telefone"])
    com_ambos = sum(1 for r in rows if r["email"] and r["telefone"])

    click.echo(f"Total: {total:,}")
    click.echo(f"  Email:    {com_email_n:,} ({100*com_email_n//max(total,1)}%)")
    click.echo(f"  Telefone: {com_tel_n:,} ({100*com_tel_n//max(total,1)}%)")
    click.echo(f"  Ambos:    {com_ambos:,} ({100*com_ambos//max(total,1)}%)")

    # Segmentos
    click.echo("\nSegmentos:")
    for cnae_code, n in Counter(r["cnae"] for r in rows).most_common():
        desc = r["cnae_descricao"] if (r := next((x for x in rows if x["cnae"] == cnae_code), None)) else cnae_code
        click.echo(f"  {desc}: {n:,}")

    # Cidades top 10
    click.echo("\nCidades:")
    for city, n in Counter(r["cidade"] for r in rows).most_common(10):
        click.echo(f"  {city}: {n:,}")

    click.echo(f"\nSalvo: {output_path.absolute()}")
    conn.close()


if __name__ == "__main__":
    main()
