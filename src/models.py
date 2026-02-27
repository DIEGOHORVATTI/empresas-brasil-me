from dataclasses import dataclass


@dataclass
class Empresa:
    cnpj_basico: str  # 8 dígitos raiz
    razao_social: str
    natureza_juridica: str
    qualificacao_responsavel: str
    capital_social: str
    porte_empresa: str  # 00=N/I, 01=ME, 03=EPP, 05=Demais
    ente_federativo: str


@dataclass
class Estabelecimento:
    cnpj_basico: str
    cnpj_ordem: str  # 4 dígitos
    cnpj_dv: str  # 2 dígitos
    matriz_filial: str  # 1=Matriz, 2=Filial
    nome_fantasia: str
    situacao_cadastral: str
    data_situacao_cadastral: str
    motivo_situacao_cadastral: str
    cidade_exterior: str
    pais: str
    data_inicio_atividade: str
    cnae_fiscal_principal: str
    cnae_fiscal_secundaria: str
    tipo_logradouro: str
    logradouro: str
    numero: str
    complemento: str
    bairro: str
    cep: str
    uf: str
    municipio: str
    ddd_1: str
    telefone_1: str
    ddd_2: str
    telefone_2: str
    ddd_fax: str
    fax: str
    email: str
    situacao_especial: str
    data_situacao_especial: str

    @property
    def cnpj_completo(self) -> str:
        return f"{self.cnpj_basico}{self.cnpj_ordem}{self.cnpj_dv}"


@dataclass
class Socio:
    cnpj_basico: str
    identificador_socio: str  # 1=PJ, 2=PF, 3=Estrangeiro
    nome_socio: str
    cnpj_cpf_socio: str
    qualificacao_socio: str
    data_entrada: str
    pais: str
    representante_legal: str
    nome_representante: str
    qualificacao_representante: str
    faixa_etaria: str


@dataclass
class Simples:
    cnpj_basico: str
    opcao_simples: str  # S/N
    data_opcao_simples: str
    data_exclusao_simples: str
    opcao_mei: str  # S/N
    data_opcao_mei: str
    data_exclusao_mei: str
