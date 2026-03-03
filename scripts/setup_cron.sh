#!/usr/bin/env bash
# Configura cron jobs para coleta automática de empresas.
# Uso: bash scripts/setup_cron.sh

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CRON_TAG="# empresas-brasil-me"

echo "Diretório do projeto: $PROJECT_DIR"
echo ""

# Cria diretório de logs
mkdir -p "$PROJECT_DIR/data/logs"

# Remove entradas anteriores deste projeto
EXISTING_CRON=$(crontab -l 2>/dev/null || true)
CLEAN_CRON=$(echo "$EXISTING_CRON" | grep -v "$CRON_TAG" || true)

# Define novos jobs
NEW_JOBS=$(cat <<EOF

# === Coleta automática de empresas brasileiras === $CRON_TAG
# Diário 6h - busca novas empresas via API Casa dos Dados $CRON_TAG
0 6 * * * cd $PROJECT_DIR && uv run python scripts/cron_novas_empresas.py --dias 1 >> data/logs/diario.log 2>&1 $CRON_TAG

# Mensal dia 15 às 3h - download + importação completa RF $CRON_TAG
0 3 15 * * cd $PROJECT_DIR && uv run python scripts/cron_bulk_mensal.py >> data/logs/mensal.log 2>&1 $CRON_TAG
EOF
)

# Instala crontab
echo "$CLEAN_CRON$NEW_JOBS" | crontab -

echo "Cron jobs instalados com sucesso!"
echo ""
echo "Jobs configurados:"
echo "  - Diário às 06:00  → busca novas empresas (API)"
echo "  - Mensal dia 15 às 03:00 → download + importação RF"
echo ""
echo "Verificar: crontab -l"
echo "Logs em: $PROJECT_DIR/data/logs/"
echo ""
echo "Para remover: crontab -l | grep -v '$CRON_TAG' | crontab -"
