#!/usr/bin/env python3
"""Envia um lote de emails pros melhores leads (ticket alto, capital com substância).

Pula quem já recebeu (tabela envios) e respeita um intervalo entre envios.
Uso: python scripts/enviar_lote.py [quantidade]
"""

import sys
import time
from datetime import datetime

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))

from src.etl.database import get_connection
from src.marketing import brevo
from src.marketing.templates import corpo_para_html, montar_email

QTD = int(sys.argv[1]) if len(sys.argv) > 1 else 20
INTERVALO = 1.0  # segundos entre envios (educado com o rate limit do Brevo)

# Nichos de ticket alto: saúde, imobiliário, construção, contabilidade,
# atacado, veículos, educação, transporte.
NICHOS_ALTO = ("86", "68", "41", "42", "43", "69", "46", "45", "85", "49")

ok, msg = brevo.config_ok()
if not ok:
    print(f"Brevo não configurado: {msg}")
    sys.exit(1)

conn = get_connection()
placeholders = ",".join("?" * len(NICHOS_ALTO))
leads = conn.execute(
    f"""
    SELECT e.cnpj_basico || e.cnpj_ordem || e.cnpj_dv AS cnpj,
           emp.razao_social, e.nome_fantasia, e.cnae_fiscal_principal, e.email
    FROM estabelecimentos e
    JOIN empresas emp ON emp.cnpj_basico = e.cnpj_basico
    WHERE e.situacao_cadastral = '02' AND e.email != ''
      AND CAST(REPLACE(emp.capital_social, ',', '.') AS REAL) BETWEEN 50000 AND 2000000
      AND substr(e.cnae_fiscal_principal, 1, 2) IN ({placeholders})
      AND (e.cnpj_basico || e.cnpj_ordem || e.cnpj_dv) NOT IN (SELECT cnpj FROM envios)
    ORDER BY CAST(REPLACE(emp.capital_social, ',', '.') AS REAL) DESC
    LIMIT ?
    """,
    (*NICHOS_ALTO, QTD),
).fetchall()

print(f"Enviando {len(leads)} email(s)...\n")
enviados = 0
for cnpj, razao, fantasia, cnae, email in leads:
    lead = {"razao_social": razao, "nome_fantasia": fantasia,
            "cnae_fiscal_principal": cnae, "email": email, "cnpj": cnpj}
    e = montar_email(lead)
    sucesso, info = brevo.enviar(email, e["assunto"], e["corpo"], corpo_para_html(e["corpo"]))
    if sucesso:
        conn.execute(
            "INSERT OR REPLACE INTO envios VALUES (?,?,?,?,?,?)",
            (cnpj, email, e["nicho"], "enviado", "brevo",
             datetime.now().isoformat(timespec="seconds")),
        )
        conn.commit()
        enviados += 1
        print(f"  ✓ {email:40s} [{e['nicho']}]")
    else:
        print(f"  ✗ {email:40s} ERRO: {info}")
    time.sleep(INTERVALO)

conn.close()
print(f"\nConcluído: {enviados}/{len(leads)} enviados.")
