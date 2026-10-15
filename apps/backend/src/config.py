from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
DB_DIR = DATA_DIR / "db"
DB_PATH = DB_DIR / "empresas.db"
LOG_DIR = DATA_DIR / "logs"

# Receita Federal - Dados Abertos CNPJ
# Mirror Casa dos Dados (CDN rápido, atualização mensal)
RF_BASE_URL = "http://dados-abertos-rf-cnpj.casadosdados.com.br/arquivos"
# Index da Casa dos Dados para descobrir períodos
RF_INDEX_URL = "http://dados-abertos-rf-cnpj.casadosdados.com.br/arquivos/"

# Arquivos da RF (37 total)
RF_FILES = {
    "empresas": [f"Empresas{i}.zip" for i in range(10)],
    "estabelecimentos": [f"Estabelecimentos{i}.zip" for i in range(10)],
    "socios": [f"Socios{i}.zip" for i in range(10)],
    "simples": ["Simples.zip"],
    "cnaes": ["Cnaes.zip"],
    "motivos": ["Motivos.zip"],
    "municipios": ["Municipios.zip"],
    "naturezas": ["Naturezas.zip"],
    "paises": ["Paises.zip"],
    "qualificacoes": ["Qualificacoes.zip"],
}

# APIs públicas
OPENCNPJ_BASE_URL = "https://api.opencnpj.org"
MINHARECEITA_BASE_URL = "https://minhareceita.org"

# Códigos de porte
PORTE_NAO_INFORMADO = "00"
PORTE_ME = "01"
PORTE_EPP = "03"
PORTE_DEMAIS = "05"

# Situação cadastral
SITUACAO_ATIVA = "02"
SITUACAO_SUSPENSA = "03"
SITUACAO_INAPTA = "04"
SITUACAO_BAIXADA = "08"
