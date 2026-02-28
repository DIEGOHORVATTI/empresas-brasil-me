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

### Tabelas principais

| Tabela | Campos-chave | Descrição |
|--------|-------------|-----------|
| **empresas** | `cnpj_basico` (PK), razao_social, porte_empresa, capital_social, natureza_juridica | Dados cadastrais da empresa |
| **estabelecimentos** | `cnpj_basico + cnpj_ordem + cnpj_dv` (PK), nome_fantasia, cnae_fiscal_principal, uf, email, telefone_1, situacao_cadastral | Matriz/filiais com endereço, contato e atividade |
| **socios** | cnpj_basico, nome_socio, cnpj_cpf_socio, qualificacao_socio, data_entrada | Sócios e administradores |
| **simples** | `cnpj_basico` (PK), opcao_simples, opcao_mei | Regime tributário Simples/MEI |

### Tabelas de referência

| Tabela | Exemplo |
|--------|---------|
| **cnaes** | `6201501` → Desenvolvimento de software |
| **qualificacoes** | `49` → Sócio-Administrador |
| **naturezas** | `2062` → Sociedade Empresária Limitada |
| **municipios** | `7107` → São Paulo |
| **motivos** | `01` → Extinção por encerramento |
| **paises** | `105` → Brasil |

### Códigos de referência rápida

**Porte da empresa** (`empresas.porte_empresa`):

| Código | Tipo |
|--------|------|
| `00` | Não informado |
| `01` | ME (Microempresa) |
| `03` | EPP (Empresa de Pequeno Porte) |
| `05` | Demais |

**Situação cadastral** (`estabelecimentos.situacao_cadastral`):

| Código | Status | Qtd registros |
|--------|--------|--------------|
| `01` | Nula | 106.477 |
| `02` | Ativa | 28.186.448 |
| `03` | Suspensa | 304.347 |
| `04` | Inapta | 8.574.258 |
| `08` | Baixada | 32.710.800 |

**MEI**: Identificado na tabela `simples` pelo campo `opcao_mei = 'S'`.

**Matriz/Filial** (`estabelecimentos.matriz_filial`): `1` = Matriz, `2` = Filial.

---

## Guia de Consultas SQL

O banco SQLite está em `data/db/empresas.db` (~32 GB, ~70M estabelecimentos).

```bash
sqlite3 data/db/empresas.db
```

### Cruzamento entre tabelas

As tabelas se conectam pelo campo `cnpj_basico` (8 primeiros dígitos do CNPJ):

```
empresas.cnpj_basico ──┬── estabelecimentos.cnpj_basico
                       ├── socios.cnpj_basico
                       └── simples.cnpj_basico
```

O CNPJ completo (14 dígitos) é montado assim: `cnpj_basico || cnpj_ordem || cnpj_dv`.

### 1. Listar empresas ativas com email, filtradas por CNAE

```sql
-- Empresas de desenvolvimento de software (CNAE 6201-5) ativas em SP com email
SELECT
    e.cnpj_basico || est.cnpj_ordem || est.cnpj_dv AS cnpj,
    e.razao_social,
    est.nome_fantasia,
    est.email,
    est.ddd_1 || est.telefone_1 AS telefone,
    est.uf,
    c.descricao AS atividade
FROM estabelecimentos est
JOIN empresas e ON e.cnpj_basico = est.cnpj_basico
JOIN cnaes c ON c.codigo = est.cnae_fiscal_principal
WHERE est.situacao_cadastral = '02'        -- ativas
  AND est.cnae_fiscal_principal LIKE '6201%' -- desenvolvimento de software
  AND est.uf = 'SP'
  AND est.email <> ''
LIMIT 100;
```

### 2. Buscar sócios + email da empresa (para envio de email ao sócio via empresa)

```sql
-- Sócios-administradores de empresas ativas com email disponível
SELECT
    e.cnpj_basico || est.cnpj_ordem || est.cnpj_dv AS cnpj,
    e.razao_social,
    s.nome_socio,
    q.descricao AS cargo,
    s.data_entrada,
    est.email AS email_empresa,
    est.ddd_1 || est.telefone_1 AS telefone
FROM socios s
JOIN empresas e ON e.cnpj_basico = s.cnpj_basico
JOIN estabelecimentos est ON est.cnpj_basico = s.cnpj_basico
    AND est.matriz_filial = '1'            -- só matriz
JOIN qualificacoes q ON q.codigo = s.qualificacao_socio
WHERE est.situacao_cadastral = '02'        -- ativas
  AND est.email <> ''
  AND s.qualificacao_socio = '49'          -- sócio-administrador
LIMIT 100;
```

### 3. Filtrar por porte + CNAE + UF (segmentação de mercado)

```sql
-- Microempresas de alimentação ativas no RJ
SELECT
    e.cnpj_basico || est.cnpj_ordem || est.cnpj_dv AS cnpj,
    e.razao_social,
    est.nome_fantasia,
    est.email,
    est.ddd_1 || est.telefone_1 AS telefone,
    c.descricao AS atividade,
    e.capital_social
FROM estabelecimentos est
JOIN empresas e ON e.cnpj_basico = est.cnpj_basico
JOIN cnaes c ON c.codigo = est.cnae_fiscal_principal
WHERE est.situacao_cadastral = '02'
  AND e.porte_empresa = '01'               -- ME
  AND est.cnae_fiscal_principal LIKE '56%'  -- alimentação
  AND est.uf = 'RJ'
  AND est.email <> ''
LIMIT 100;
```

### 4. Empresas MEI ativas com email

```sql
SELECT
    e.cnpj_basico || est.cnpj_ordem || est.cnpj_dv AS cnpj,
    e.razao_social,
    est.email,
    est.uf,
    c.descricao AS atividade
FROM estabelecimentos est
JOIN empresas e ON e.cnpj_basico = est.cnpj_basico
JOIN simples si ON si.cnpj_basico = est.cnpj_basico
JOIN cnaes c ON c.codigo = est.cnae_fiscal_principal
WHERE est.situacao_cadastral = '02'
  AND si.opcao_mei = 'S'
  AND est.email <> ''
LIMIT 100;
```

### 5. Todos os sócios de uma empresa específica

```sql
SELECT
    s.nome_socio,
    s.cnpj_cpf_socio,
    q.descricao AS cargo,
    s.data_entrada,
    s.faixa_etaria
FROM socios s
JOIN qualificacoes q ON q.codigo = s.qualificacao_socio
WHERE s.cnpj_basico = '00000000'           -- 8 primeiros dígitos do CNPJ
ORDER BY s.data_entrada;
```

### 6. Exportar lista de emails para CSV

```sql
.mode csv
.headers on
.output emails_software_sp.csv

SELECT
    e.cnpj_basico || est.cnpj_ordem || est.cnpj_dv AS cnpj,
    e.razao_social,
    est.nome_fantasia,
    est.email,
    est.ddd_1 || est.telefone_1 AS telefone,
    est.uf,
    est.municipio
FROM estabelecimentos est
JOIN empresas e ON e.cnpj_basico = est.cnpj_basico
WHERE est.situacao_cadastral = '02'
  AND est.cnae_fiscal_principal LIKE '6201%'
  AND est.email <> '';

.output stdout
```

### 7. Exportar sócios + contato da empresa para CSV

```sql
.mode csv
.headers on
.output socios_com_email.csv

SELECT
    e.cnpj_basico || est.cnpj_ordem || est.cnpj_dv AS cnpj,
    e.razao_social,
    s.nome_socio,
    q.descricao AS cargo,
    est.email AS email_empresa,
    est.ddd_1 || est.telefone_1 AS telefone,
    est.uf
FROM socios s
JOIN empresas e ON e.cnpj_basico = s.cnpj_basico
JOIN estabelecimentos est ON est.cnpj_basico = s.cnpj_basico
    AND est.matriz_filial = '1'
JOIN qualificacoes q ON q.codigo = s.qualificacao_socio
WHERE est.situacao_cadastral = '02'
  AND est.email <> '';

.output stdout
```

### Filtros úteis (combinação livre)

| Filtro | SQL |
|--------|-----|
| Por UF | `est.uf = 'SP'` |
| Por cidade | `est.municipio = '7107'` (consulte tabela `municipios`) |
| Por CNAE | `est.cnae_fiscal_principal LIKE '6201%'` |
| Por CNAE secundário | `est.cnae_fiscal_secundaria LIKE '%6201%'` |
| Só ativas | `est.situacao_cadastral = '02'` |
| Só matrizes | `est.matriz_filial = '1'` |
| Com email | `est.email <> ''` |
| Com telefone | `est.telefone_1 <> ''` |
| Por porte | `e.porte_empresa = '01'` (ME) |
| Só MEI | `si.opcao_mei = 'S'` (JOIN simples) |
| Só Simples | `si.opcao_simples = 'S'` (JOIN simples) |
| Capital social | `CAST(REPLACE(e.capital_social, ',', '.') AS REAL) > 100000` |
| Abertas após data | `est.data_inicio_atividade > '20230101'` |
| Cargo do sócio | `s.qualificacao_socio = '49'` (sócio-administrador) |

### CNAEs mais comuns (para referência)

| Prefixo | Setor |
|---------|-------|
| `47` | Comércio varejista |
| `56` | Alimentação |
| `62` | Tecnologia da informação |
| `69` | Contabilidade e consultoria |
| `86` | Saúde |
| `85` | Educação |
| `41` | Construção |
| `49` | Transporte |
| `96` | Serviços pessoais |

### Qualificações de sócios mais comuns

| Código | Cargo |
|--------|-------|
| `49` | Sócio-Administrador |
| `22` | Sócio |
| `05` | Administrador |
| `10` | Diretor |
| `16` | Presidente |
