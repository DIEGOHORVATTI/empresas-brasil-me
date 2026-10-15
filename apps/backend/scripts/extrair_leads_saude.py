"""
Extrai leads de clínicas ME/EPP de ticket alto (saúde, odonto, estética, psico).

Uso:
  uv run python scripts/extrair_leads_saude.py --floripa --dias 365
  uv run python scripts/extrair_leads_saude.py --floripa --dias 90 --ticket-alto
  uv run python scripts/extrair_leads_saude.py --uf SP --dias 180
  uv run python scripts/extrair_leads_saude.py --distribuicao --floripa
  uv run python scripts/extrair_leads_saude.py --municipio 8105 --municipio 8233 --uf SC

Municípios (Grande Florianópolis):
  8105=Florianópolis  8233=Palhoça  8327=São José  8045=Biguaçu
"""

import csv
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

import click

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.config import DB_PATH

SEGMENTOS = {
    "8630504": "Odontologia",
    "8630501": "Medicina amb. cirúrgica",
    "8630502": "Medicina amb. exames",
    "8630503": "Medicina amb. consultas",
    "8650003": "Psicologia/Psicanálise",
    "9602502": "Estética",
    "8690999": "Outras saúde humana",
    "8630506": "Vacinação",
    "8650004": "Fisioterapia",
    "8650006": "Fonoaudiologia",
    "8650002": "Nutrição",
}

# Ordem = prioridade de prospecção (ticket mais alto primeiro)
CNAES_TICKET_ALTO = ["8630504", "9602502", "8650003", "8630503", "8630501", "8630502"]
PRIORIDADE_CNAE = {cnae: i for i, cnae in enumerate(CNAES_TICKET_ALTO)}
# CNAEs fora da lista de ticket alto ficam no final
for _c in SEGMENTOS:
    PRIORIDADE_CNAE.setdefault(_c, 99)
CNAES_TODOS = list(SEGMENTOS.keys())
MUNICIPIOS_FLORIPA = ["8105", "8233", "8327", "8045"]


def get_conn() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise SystemExit(f"Banco não encontrado: {DB_PATH}")
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA cache_size=-64000")
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.row_factory = sqlite3.Row
    return conn


def _where_base(cnaes: list[str], municipios: tuple[str, ...], ufs: tuple[str, ...]) -> tuple[str, list[str]]:
    """Monta WHERE otimizado: filtra só em estabelecimentos (usa índice composto)."""
    cnaes_ph = ", ".join("?" for _ in cnaes)
    where = f"""
        est.cnae_fiscal_principal IN ({cnaes_ph})
        AND est.situacao_cadastral = '02'
        AND est.matriz_filial = '1'
    """
    params: list[str] = list(cnaes)

    if municipios:
        mun_ph = ", ".join("?" for _ in municipios)
        where += f" AND est.municipio IN ({mun_ph})"
        params.extend(municipios)

    if ufs:
        uf_ph = ", ".join("?" for _ in ufs)
        where += f" AND est.uf IN ({uf_ph})"
        params.extend(ufs)

    return where, params


def mostrar_distribuicao(
    conn: sqlite3.Connection,
    ufs: tuple[str, ...],
    municipios: tuple[str, ...],
) -> None:
    """Distribuição em 1 única query — agrupa por CNAE e faixa de idade."""
    where_base, base_params = _where_base(CNAES_TODOS, municipios, ufs)

    # Limites das faixas em formato YYYYMMDD
    now = datetime.now()
    limites = [30, 60, 90, 180, 365, 730]
    datas = [(now - timedelta(days=d)).strftime("%Y%m%d") for d in limites]

    # 1 query pra tudo: conta por CNAE com CASE pra faixas de idade
    cases_total = []
    cases_email = []
    cases_tel = []
    for i, d in enumerate(datas):
        prev = datas[i - 1] if i > 0 else now.strftime("%Y%m%d")
        cases_total.append(f"SUM(CASE WHEN est.data_inicio_atividade BETWEEN '{d}' AND '{prev}' THEN 1 ELSE 0 END) AS faixa_{i}")
        cases_email.append(f"SUM(CASE WHEN est.data_inicio_atividade BETWEEN '{d}' AND '{prev}' AND est.email <> '' THEN 1 ELSE 0 END) AS faixa_e_{i}")
        cases_tel.append(f"SUM(CASE WHEN est.data_inicio_atividade BETWEEN '{d}' AND '{prev}' AND est.telefone_1 <> '' THEN 1 ELSE 0 END) AS faixa_t_{i}")
    # Faixa 730d+
    cases_total.append(f"SUM(CASE WHEN est.data_inicio_atividade < '{datas[-1]}' THEN 1 ELSE 0 END) AS faixa_{len(datas)}")
    cases_email.append(f"SUM(CASE WHEN est.data_inicio_atividade < '{datas[-1]}' AND est.email <> '' THEN 1 ELSE 0 END) AS faixa_e_{len(datas)}")
    cases_tel.append(f"SUM(CASE WHEN est.data_inicio_atividade < '{datas[-1]}' AND est.telefone_1 <> '' THEN 1 ELSE 0 END) AS faixa_t_{len(datas)}")

    all_cases = ", ".join(cases_total + cases_email + cases_tel)

    sql = f"""
        SELECT est.cnae_fiscal_principal AS cnae, COUNT(*) AS total,
               COALESCE(SUM(CASE WHEN est.email <> '' THEN 1 ELSE 0 END), 0) AS com_email,
               COALESCE(SUM(CASE WHEN est.telefone_1 <> '' THEN 1 ELSE 0 END), 0) AS com_tel,
               {all_cases}
        FROM estabelecimentos est
        JOIN empresas e ON e.cnpj_basico = est.cnpj_basico AND e.porte_empresa IN ('01', '03')
        WHERE {where_base}
        GROUP BY est.cnae_fiscal_principal
    """

    rows = conn.execute(sql, base_params).fetchall()

    # Agregar por faixa
    labels = ["0-30d", "30-60d", "60-90d", "90-180d", "180-365d", "365-730d", "730d+"]
    n_faixas = len(labels)
    totais = [0] * n_faixas
    emails = [0] * n_faixas
    tels = [0] * n_faixas

    for row in rows:
        for i in range(n_faixas):
            totais[i] += row[f"faixa_{i}"] or 0
            emails[i] += row[f"faixa_e_{i}"] or 0
            tels[i] += row[f"faixa_t_{i}"] or 0

    click.echo(f"\n{'Faixa':<15} {'Qtd':>8} {'Email':>8} {'Tel':>8}")
    click.echo("-" * 43)
    for i, label in enumerate(labels):
        click.echo(f"{label:<15} {totais[i]:>8,} {emails[i]:>8,} {tels[i]:>8,}")

    click.echo(f"\n{'CNAE':<8} {'Segmento':<35} {'Total':>8} {'Email':>8} {'Tel':>8}")
    click.echo("-" * 71)
    for row in sorted(rows, key=lambda r: r["total"], reverse=True):
        desc = SEGMENTOS.get(row["cnae"], row["cnae"])
        click.echo(f"{row['cnae']:<8} {desc:<35} {row['total']:>8,} {row['com_email']:>8,} {row['com_tel']:>8,}")


@click.command()
@click.option("--dias", default=365, help="Criadas nos últimos N dias")
@click.option("--uf", multiple=True, help="UF (repetível)")
@click.option("--municipio", multiple=True, help="Código município (repetível)")
@click.option("--floripa", is_flag=True, help="Atalho: Grande Florianópolis")
@click.option("--ticket-alto", is_flag=True, help="Só CNAEs de ticket alto")
@click.option("--sem-telefone", is_flag=True, help="Incluir sem telefone/email")
@click.option("--distribuicao", is_flag=True, help="Só mostra distribuição")
@click.option("--limit", default=0, help="Máximo de resultados")
@click.option("-o", "--output", default="leads_saude.csv", help="CSV de saída")
def main(
    dias: int,
    uf: tuple[str, ...],
    municipio: tuple[str, ...],
    floripa: bool,
    ticket_alto: bool,
    sem_telefone: bool,
    distribuicao: bool,
    limit: int,
    output: str,
) -> None:
    """Extrai leads ME/EPP de saúde com ticket alto."""
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

    cnaes = CNAES_TICKET_ALTO if ticket_alto else CNAES_TODOS
    where_base, params = _where_base(cnaes, municipios_tuple, uf)
    data_limite = (datetime.now() - timedelta(days=dias)).strftime("%Y%m%d")

    # Query otimizada: filtra estabelecimentos primeiro (usa índice), depois JOINs leves
    sql = f"""
        SELECT
            -- Segmento e prioridade
            c.descricao AS segmento,
            est.cnae_fiscal_principal AS cnae,
            -- Contato (o que mais importa pra prospecção)
            est.nome_fantasia,
            s.nome_socio AS decisor,
            q.descricao AS cargo,
            est.email,
            CASE WHEN est.telefone_1 <> '' THEN est.ddd_1 || est.telefone_1 ELSE '' END AS telefone,
            CASE WHEN est.telefone_2 <> '' THEN est.ddd_2 || est.telefone_2 ELSE '' END AS telefone_2,
            -- Empresa
            e.razao_social,
            est.cnpj_basico || est.cnpj_ordem || est.cnpj_dv AS cnpj,
            e.porte_empresa AS porte,
            REPLACE(e.capital_social, ',', '.') AS capital_social,
            -- Tempo
            CAST(julianday('now') - julianday(
                substr(est.data_inicio_atividade,1,4)||'-'||
                substr(est.data_inicio_atividade,5,2)||'-'||
                substr(est.data_inicio_atividade,7,2)
            ) AS INTEGER) AS dias_abertura,
            est.data_inicio_atividade,
            -- Localização
            m.descricao AS cidade,
            est.uf,
            est.bairro,
            TRIM(est.tipo_logradouro || ' ' || est.logradouro || ', ' || est.numero) AS endereco,
            est.cep
        FROM estabelecimentos est
        JOIN empresas e ON e.cnpj_basico = est.cnpj_basico
            AND e.porte_empresa IN ('01', '03')
        LEFT JOIN cnaes c ON c.codigo = est.cnae_fiscal_principal
        LEFT JOIN municipios m ON m.codigo = est.municipio
        LEFT JOIN socios s ON s.cnpj_basico = est.cnpj_basico
            AND s.qualificacao_socio IN ('49', '22', '05')
        LEFT JOIN qualificacoes q ON q.codigo = s.qualificacao_socio
        WHERE {where_base}
          AND est.data_inicio_atividade >= ?
    """
    params.append(data_limite)

    if not sem_telefone:
        sql += " AND (est.email <> '' OR est.telefone_1 <> '')"

    # Ordenar por prioridade do segmento (ticket alto primeiro), depois mais novas
    prioridade_case = " ".join(
        f"WHEN '{cnae}' THEN {pri}" for cnae, pri in PRIORIDADE_CNAE.items()
    )
    sql += f"""
        GROUP BY est.cnpj_basico, est.cnpj_ordem, est.cnpj_dv
        ORDER BY CASE est.cnae_fiscal_principal {prioridade_case} ELSE 99 END,
                 est.data_inicio_atividade DESC
    """

    if limit > 0:
        sql += f" LIMIT {limit}"

    click.echo(f"Filtros: dias={dias} UFs={uf or 'todas'} municipios={municipios_tuple or 'todos'} ticket_alto={ticket_alto}")
    click.echo(f"CNAEs: {', '.join(cnaes)}")
    click.echo(f"Data mínima: {data_limite}\n")

    rows = conn.execute(sql, params).fetchall()

    if not rows:
        click.echo("Nenhum resultado.")
        conn.close()
        return

    output_path = Path(output)
    cols = rows[0].keys()
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for row in rows:
            w.writerow(dict(row))

    total = len(rows)
    com_email = sum(1 for r in rows if r["email"])
    com_tel = sum(1 for r in rows if r["telefone"])
    com_ambos = sum(1 for r in rows if r["email"] and r["telefone"])

    click.echo(f"Total: {total:,}")
    click.echo(f"  Email:    {com_email:,} ({100*com_email//total}%)")
    click.echo(f"  Telefone: {com_tel:,} ({100*com_tel//total}%)")
    click.echo(f"  Ambos:    {com_ambos:,} ({100*com_ambos//total}%)\n")

    from collections import Counter
    click.echo("Segmentos (em ordem de prioridade):")
    for code, n in sorted(Counter(r["cnae"] for r in rows).items(), key=lambda x: PRIORIDADE_CNAE.get(x[0], 99)):
        click.echo(f"  {SEGMENTOS.get(code, code)}: {n:,}")

    click.echo("\nCidades:")
    for city, n in Counter(r["cidade"] for r in rows).most_common(10):
        click.echo(f"  {city}: {n:,}")

    click.echo(f"\nSalvo: {output_path.absolute()}")
    conn.close()


if __name__ == "__main__":
    main()
