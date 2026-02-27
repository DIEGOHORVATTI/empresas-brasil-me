# empresas-brasil-me

Coleta de dados de **todas as empresas brasileiras** (~60 milhões) a partir dos dados abertos da Receita Federal e APIs públicas.

## Fontes de Dados

| Fonte | Tipo | Descrição |
|-------|------|-----------|
| [Dados Abertos RF](https://dadosabertos.rfb.gov.br/CNPJ/) | ETL (bulk) | 37 ZIPs com CSVs de todas as empresas, sócios e MEI/Simples |
| [OpenCNPJ](https://opencnpj.org/) | API | Consulta por CNPJ, sem auth, 50 req/s |
| [Minha Receita](https://docs.minhareceita.org/) | API | Consulta e busca com filtros, sem auth |

## Setup

```bash
uv sync
```

## Uso

### 1. Download dos dados da RF

```bash
# Baixa todos os 37 arquivos (auto-detecta período mais recente)
uv run python scripts/download_rf.py

# Baixa apenas empresas e simples
uv run python scripts/download_rf.py -t empresas -t simples

# Baixa 1 arquivo para teste
uv run python scripts/download_rf.py --limit 1
```

### 2. Importar para SQLite

```bash
uv run python scripts/import_db.py -p 2025-10
```

### 3. Consultar empresa por CNPJ

```bash
# Via OpenCNPJ
uv run python scripts/consulta_cnpj.py 00000000000191

# Via Minha Receita
uv run python scripts/consulta_cnpj.py 00000000000191 -f minhareceita

# Via banco local
uv run python scripts/consulta_cnpj.py 00000000000191 -f local
```

## Estrutura dos Dados

### Tipos de Empresa (campo `porte_empresa`)

| Código | Tipo |
|--------|------|
| `00` | Não informado |
| `01` | ME (Microempresa) |
| `03` | EPP (Empresa de Pequeno Porte) |
| `05` | Demais |

### MEI

Identificado na tabela `simples` pelo campo `opcao_mei = 'S'`.

### Tabelas

- **empresas** — razão social, porte, capital social, natureza jurídica
- **estabelecimentos** — endereço, CNAE, telefones, email, situação cadastral, UF
- **socios** — nome, CPF/CNPJ, qualificação, data de entrada
- **simples** — opção Simples Nacional e MEI com datas
- Tabelas de referência: cnaes, municípios, naturezas, países, qualificações, motivos
