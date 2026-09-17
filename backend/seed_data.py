"""
Módulo de Inicialização de Dados - Sistema 'Padrão do Ano' (COMARA)
Organograma RICA 21-209, Contas LDAP com 5 Modificadores de Acesso e Controle de Fases
"""
import os
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from database import get_db_connection, init_db, registrar_log, hash_senha

# Divisões Oficiais RICA 21-209 / ROCA 21-55
DIVISOES_OFICIAIS = [
    {"sigla": "DE", "nome": "Divisão de Engenharia", "chefe_nome": "Maj Eng Luís Mauro Moreira de Sá", "chefe_saram_cpf": "3800007", "chefe_ldap": "moreira.cde"},
    {"sigla": "DL", "nome": "Divisão de Logística", "chefe_nome": "Ten Cel Int Antonio José de Jesus Belém Leitão Junior", "chefe_saram_cpf": "3800005", "chefe_ldap": "leitao.cdl"},
    {"sigla": "DA", "nome": "Divisão de Apoio", "chefe_nome": "Ten Cel Av Adenirson Levy Santos da Cruz", "chefe_saram_cpf": "3800004", "chefe_ldap": "levy.cda"},
    {"sigla": "DPC", "nome": "Divisão de Planejamento e Coordenação", "chefe_nome": "Cel Av Siqueira", "chefe_saram_cpf": "3567812", "chefe_ldap": "siqueira.cdpc"},
    {"sigla": "DACO-MN", "nome": "Destacamento de Apoio da COMARA em Manaus", "chefe_nome": "Ten Cel Av Rocha", "chefe_saram_cpf": "3910293", "chefe_ldap": "rocha.cdaco"},
    {"sigla": "VP", "nome": "Vice-Presidência e Assessorias", "chefe_nome": "Cel Av Baptista", "chefe_saram_cpf": "3109283", "chefe_ldap": "baptista.vp"}
]

# Seções e Subdivisões Oficiais RICA 21-209 (principais chefias)
SECOES_OFICIAIS = [
    # DE
    {"sigla": "DEPL", "nome": "Seção de Planejamento", "divisao_sigla": "DE", "subdivisao": "SDPO", "chefe_nome": "Cap Eng Rios", "chefe_ldap": "secao.depl"},
    {"sigla": "DEPJ", "nome": "Seção de Projetos", "divisao_sigla": "DE", "subdivisao": "SDPJ", "chefe_nome": "Cap Eng Lacerda", "chefe_ldap": "secao.depj"},
    {"sigla": "DEOR", "nome": "Seção de Orçamento", "divisao_sigla": "DE", "subdivisao": "SDPO", "chefe_nome": "Cap Eng Sampaio", "chefe_ldap": "secao.deor"},
    {"sigla": "DEAC", "nome": "Seção de Acompanhamento de Obras", "divisao_sigla": "DE", "subdivisao": "SDO", "chefe_nome": "Cap Eng Alencar", "chefe_ldap": "secao.deac"},
    {"sigla": "DECO", "nome": "Destacamentos de Engenharia", "divisao_sigla": "DE", "subdivisao": "SDO", "chefe_nome": "Maj Eng Ferraz", "chefe_ldap": "secao.deco"},
    {"sigla": "DEMC", "nome": "Seção de Manutenção e Conservação", "divisao_sigla": "DE", "subdivisao": "SDSG", "chefe_nome": "1T QOCon Melo", "chefe_ldap": "secao.demc"},
    {"sigla": "DECA", "nome": "Seção de Cadastro", "divisao_sigla": "DE", "subdivisao": "SDPA", "chefe_nome": "Cap Eng Abreu", "chefe_ldap": "secao.deca"},
    {"sigla": "DELP", "nome": "Seção de Laboratório e Pavimentação", "divisao_sigla": "DE", "subdivisao": "SDPJ", "chefe_nome": "Cap Eng Medeiros", "chefe_ldap": "secao.delp"},
    {"sigla": "DEOF", "nome": "Seção de Oficinas", "divisao_sigla": "DE", "subdivisao": "SDSG", "chefe_nome": "SO Mecânico Lima", "chefe_ldap": "secao.deof"},

    # DA
    {"sigla": "DAPM", "nome": "Seção de Pessoal Militar", "divisao_sigla": "DA", "subdivisao": "SDRH", "chefe_nome": "1T QOCon Ramos", "chefe_ldap": "secao.dapm"},
    {"sigla": "DAPC", "nome": "Seção de Pessoal Civil", "divisao_sigla": "DA", "subdivisao": "SDRH", "chefe_nome": "Cap Esp Silva", "chefe_ldap": "secao.dapc"},
    {"sigla": "DASD", "nome": "Seção de Segurança e Defesa", "divisao_sigla": "DA", "subdivisao": "SDAP", "chefe_nome": "Cap Inf Toledo", "chefe_ldap": "secao.dasd"},
    {"sigla": "DAPR", "nome": "Seção de Provisões", "divisao_sigla": "DA", "subdivisao": "SDI", "chefe_nome": "Cap Int Moura", "chefe_ldap": "secao.dapr"},
    {"sigla": "DAPP", "nome": "Seção de Pagamento de Pessoal", "divisao_sigla": "DA", "subdivisao": "SDI", "chefe_nome": "Cap Int Prado", "chefe_ldap": "secao.dapp"},
    {"sigla": "DACC", "nome": "Seção de Contabilidade de Custos", "divisao_sigla": "DA", "subdivisao": "SDI", "chefe_nome": "1T Int Viana", "chefe_ldap": "secao.dacc"},
    {"sigla": "DACO-TT", "nome": "Destacamento de Apoio em Tabatinga", "divisao_sigla": "DA", "subdivisao": "DA", "chefe_nome": "Cap Av Guimarães", "chefe_ldap": "secao.dacott"},
    {"sigla": "DACO-UA", "nome": "Destacamento em São Gabriel da Cachoeira", "divisao_sigla": "DA", "subdivisao": "DA", "chefe_nome": "Cap Int Teles", "chefe_ldap": "secao.dacoua"},

    # DL
    {"sigla": "DLTR", "nome": "Seção de Transporte de Superfície", "divisao_sigla": "DL", "subdivisao": "SDT", "chefe_nome": "Cap Esp Garcez", "chefe_ldap": "secao.dltr"},
    {"sigla": "DLAQ", "nome": "Seção de Aquaviário", "divisao_sigla": "DL", "subdivisao": "SDT", "chefe_nome": "Cap QOCon Fontoura", "chefe_ldap": "secao.dlaq"},
    {"sigla": "DLMV", "nome": "Seção de Manutenção de Veículos", "divisao_sigla": "DL", "subdivisao": "SDM", "chefe_nome": "Cap Esp Brandão", "chefe_ldap": "secao.dlmv"},
    {"sigla": "DLCP", "nome": "Seção de Compras", "divisao_sigla": "DL", "subdivisao": "SDS", "chefe_nome": "Cap Int Rezende", "chefe_ldap": "secao.dlcp"},
    {"sigla": "DLCE", "nome": "Seção de Controle de Estoque", "divisao_sigla": "DL", "subdivisao": "SDS", "chefe_nome": "1T Int Paiva", "chefe_ldap": "secao.dlce"},
    {"sigla": "DLAL", "nome": "Seção de Almoxarifado", "divisao_sigla": "DL", "subdivisao": "SDS", "chefe_nome": "Cap Int Pacheco", "chefe_ldap": "secao.dlal"},
    {"sigla": "DACO-OW", "nome": "Destacamento de Apoio em Moura", "divisao_sigla": "DL", "subdivisao": "DL", "chefe_nome": "Cap Av Macedo", "chefe_ldap": "secao.dacoow"},

    # DPC
    {"sigla": "DPTI", "nome": "Subdivisão de Tecnologia da Informação", "divisao_sigla": "DPC", "subdivisao": "DPC", "chefe_nome": "Cap Eng Linhares", "chefe_ldap": "secao.dpti"},
    {"sigla": "SDCO", "nome": "Subdivisão de Controle e Organização", "divisao_sigla": "DPC", "subdivisao": "DPC", "chefe_nome": "Maj Av Nogueira", "chefe_ldap": "secao.sdco"},
    {"sigla": "SDPP", "nome": "Subdivisão de Projetos e Processos", "divisao_sigla": "DPC", "subdivisao": "DPC", "chefe_nome": "Maj Eng Fonseca", "chefe_ldap": "secao.sdpp"},
    {"sigla": "SDC", "nome": "Subdivisão de Capacitação de RH", "divisao_sigla": "DPC", "subdivisao": "DPC", "chefe_nome": "Cap QOCon Dias", "chefe_ldap": "secao.sdc"},
    {"sigla": "DPCI", "nome": "Seção Contraincêndio", "divisao_sigla": "DPC", "subdivisao": "SESMT", "chefe_nome": "1S Bombeiro Castro", "chefe_ldap": "secao.dpci"},

    # DACO-MN
    {"sigla": "SINFRA", "nome": "Seção de Infraestrutura", "divisao_sigla": "DACO-MN", "subdivisao": "DACO-MN", "chefe_nome": "Cap Eng Coutinho", "chefe_ldap": "secao.sinfra"},
    {"sigla": "SLOG", "nome": "Seção de Logística", "divisao_sigla": "DACO-MN", "subdivisao": "DACO-MN", "chefe_nome": "Cap Int Seixas", "chefe_ldap": "secao.slog"},
    {"sigla": "SAP", "nome": "Seção de Apoio", "divisao_sigla": "DACO-MN", "subdivisao": "DACO-MN", "chefe_nome": "Cap QOCon Tavares", "chefe_ldap": "secao.sap"},
    {"sigla": "SADM", "nome": "Seção Administrativa", "divisao_sigla": "DACO-MN", "subdivisao": "DACO-MN", "chefe_nome": "Cap Int Valente", "chefe_ldap": "secao.sadm"},

    # VP
    {"sigla": "ACI", "nome": "Assessoria de Controle Interno", "divisao_sigla": "VP", "subdivisao": "VP", "chefe_nome": "Maj Int Castelo Branco", "chefe_ldap": "secao.aci"},
    {"sigla": "AJUR", "nome": "Assessoria Jurídica", "divisao_sigla": "VP", "subdivisao": "VP", "chefe_nome": "Cap QOCon Assunção", "chefe_ldap": "secao.ajur"},
    {"sigla": "SCS", "nome": "Seção de Comunicação Social", "divisao_sigla": "VP", "subdivisao": "VP", "chefe_nome": "Cap QOCon Letícia", "chefe_ldap": "secao.scs"},
    {"sigla": "APOG", "nome": "Assessoria de Planejamento e Orçamento", "divisao_sigla": "VP", "subdivisao": "VP", "chefe_nome": "Maj Int Albuquerque", "chefe_ldap": "secao.apog"}
]

# Efetivo Completo Inicial da COMARA
EFETIVO_INICIAL = [
    # --- DE (Divisão de Engenharia) ---
    {"nome": "Carlos Eduardo Lima", "nome_guerra": "Lima", "identificador": "6012341", "tipo": "MILITAR", "posto_grad_cargo": "1S", "categoria": "Graduados", "divisao": "DE", "secao": "DEPL", "tempo_comara_meses": 48},
    {"nome": "Roberto Silva Santos", "nome_guerra": "R. Santos", "identificador": "6012342", "tipo": "MILITAR", "posto_grad_cargo": "2S", "categoria": "Graduados", "divisao": "DE", "secao": "DEOR", "tempo_comara_meses": 36},
    {"nome": "Marcelo Vieira Costa", "nome_guerra": "Vieira", "identificador": "6012343", "tipo": "MILITAR", "posto_grad_cargo": "3S", "categoria": "Graduados", "divisao": "DE", "secao": "DELP", "tempo_comara_meses": 24},
    {"nome": "Antonio Carlos Prado", "nome_guerra": "Prado", "identificador": "6012344", "tipo": "MILITAR", "posto_grad_cargo": "SO", "categoria": "Graduados", "divisao": "DE", "secao": "DEOF", "tempo_comara_meses": 60},
    {"nome": "Fernando Souza Dias", "nome_guerra": "F. Souza", "identificador": "6012345", "tipo": "MILITAR", "posto_grad_cargo": "2S", "categoria": "Graduados", "divisao": "DE", "secao": "DEAC", "tempo_comara_meses": 30},
    {"nome": "Lucas Martins Gomes", "nome_guerra": "Martins", "identificador": "7012341", "tipo": "MILITAR", "posto_grad_cargo": "CB", "categoria": "Pracas", "divisao": "DE", "secao": "DECO", "tempo_comara_meses": 24},
    {"nome": "Diego Barbosa Ribeiro", "nome_guerra": "Barbosa", "identificador": "7012342", "tipo": "MILITAR", "posto_grad_cargo": "S1", "categoria": "Pracas", "divisao": "DE", "secao": "DEMC", "tempo_comara_meses": 18},
    {"nome": "Gabriel Alves Rocha", "nome_guerra": "Alves", "identificador": "7012343", "tipo": "MILITAR", "posto_grad_cargo": "S2", "categoria": "Pracas", "divisao": "DE", "secao": "DEOF", "tempo_comara_meses": 12},
    {"nome": "Ana Paula Nogueira", "nome_guerra": "Ana Paula", "identificador": "111.222.333-44", "tipo": "CIVIL", "posto_grad_cargo": "SPTF", "categoria": "Civil", "divisao": "DE", "secao": "DEPJ", "tempo_comara_meses": 72},
    {"nome": "Marcos Paulo Ferreira", "nome_guerra": "Ferreira", "identificador": "222.333.444-55", "tipo": "CIVIL", "posto_grad_cargo": "SPPF", "categoria": "Civil", "divisao": "DE", "secao": "DECA", "tempo_comara_meses": 50},

    # --- DL (Divisão de Logística) ---
    {"nome": "Alexandre Guimarães", "nome_guerra": "Guimarães", "identificador": "6022341", "tipo": "MILITAR", "posto_grad_cargo": "1S", "categoria": "Graduados", "divisao": "DL", "secao": "DLTR", "tempo_comara_meses": 42},
    {"nome": "Fabiano Teodoro Ramos", "nome_guerra": "Teodoro", "identificador": "6022342", "tipo": "MILITAR", "posto_grad_cargo": "2S", "categoria": "Graduados", "divisao": "DL", "secao": "DLMV", "tempo_comara_meses": 28},
    {"nome": "Leandro Castro Silva", "nome_guerra": "L. Castro", "identificador": "6022343", "tipo": "MILITAR", "posto_grad_cargo": "3S", "categoria": "Graduados", "divisao": "DL", "secao": "DLAQ", "tempo_comara_meses": 20},
    {"nome": "Bruno Henrique Neves", "nome_guerra": "Neves", "identificador": "7022341", "tipo": "MILITAR", "posto_grad_cargo": "CB", "categoria": "Pracas", "divisao": "DL", "secao": "DLAL", "tempo_comara_meses": 30},
    {"nome": "Felipe Augusto Melo", "nome_guerra": "Melo", "identificador": "7022342", "tipo": "MILITAR", "posto_grad_cargo": "S1", "categoria": "Pracas", "divisao": "DL", "secao": "DLCP", "tempo_comara_meses": 15},
    {"nome": "Juliana Mendes Cardoso", "nome_guerra": "Juliana", "identificador": "333.444.555-66", "tipo": "CIVIL", "posto_grad_cargo": "SPTF", "categoria": "Civil", "divisao": "DL", "secao": "DLCE", "tempo_comara_meses": 64},

    # --- DA (Divisão de Apoio) ---
    {"nome": "Renato Carvalho Cunha", "nome_guerra": "Carvalho", "identificador": "6032341", "tipo": "MILITAR", "posto_grad_cargo": "SO", "categoria": "Graduados", "divisao": "DA", "secao": "DAPR", "tempo_comara_meses": 80},
    {"nome": "Wellington Paiva Costa", "nome_guerra": "Paiva", "identificador": "6032342", "tipo": "MILITAR", "posto_grad_cargo": "2S", "categoria": "Graduados", "divisao": "DA", "secao": "DAPP", "tempo_comara_meses": 32},
    {"nome": "Vinicius Moreira Bento", "nome_guerra": "Vinicius", "identificador": "7032341", "tipo": "MILITAR", "posto_grad_cargo": "CB", "categoria": "Pracas", "divisao": "DA", "secao": "DASD", "tempo_comara_meses": 26},
    {"nome": "Samuel Dantas Freire", "nome_guerra": "Dantas", "identificador": "7032342", "tipo": "MILITAR", "posto_grad_cargo": "S1", "categoria": "Pracas", "divisao": "DA", "secao": "DAPM", "tempo_comara_meses": 14},
    {"nome": "Claudio Valério Teles", "nome_guerra": "Valério", "identificador": "444.555.666-77", "tipo": "CIVIL", "posto_grad_cargo": "SPPF", "categoria": "Civil", "divisao": "DA", "secao": "DAPC", "tempo_comara_meses": 90},
    {"nome": "Patrícia Bezerra Lima", "nome_guerra": "Patrícia", "identificador": "555.666.777-88", "tipo": "CIVIL", "posto_grad_cargo": "SPTF", "categoria": "Civil", "divisao": "DA", "secao": "DACC", "tempo_comara_meses": 45},

    # --- DPC (Divisão de Planejamento e Coordenação) ---
    {"nome": "Danilo Fontes Macedo", "nome_guerra": "Macedo", "identificador": "6042341", "tipo": "MILITAR", "posto_grad_cargo": "1S", "categoria": "Graduados", "divisao": "DPC", "secao": "DPTI", "tempo_comara_meses": 52},
    {"nome": "Thiago Brandão Sales", "nome_guerra": "Brandão", "identificador": "6042342", "tipo": "MILITAR", "posto_grad_cargo": "3S", "categoria": "Graduados", "divisao": "DPC", "secao": "SDPP", "tempo_comara_meses": 22},
    {"nome": "Rodrigo Paz Albuquerque", "nome_guerra": "Paz", "identificador": "7042341", "tipo": "MILITAR", "posto_grad_cargo": "CB", "categoria": "Pracas", "divisao": "DPC", "secao": "DPCI", "tempo_comara_meses": 20},
    {"nome": "Gustavo Farias Prado", "nome_guerra": "Farias", "identificador": "7042342", "tipo": "MILITAR", "posto_grad_cargo": "S1", "categoria": "Pracas", "divisao": "DPC", "secao": "SDCO", "tempo_comara_meses": 16},
    {"nome": "Helena Viana Campos", "nome_guerra": "Helena", "identificador": "666.777.888-99", "tipo": "CIVIL", "posto_grad_cargo": "SPPF", "categoria": "Civil", "divisao": "DPC", "secao": "SDC", "tempo_comara_meses": 58},

    # --- DACO-MN (Destacamento de Apoio da COMARA em Manaus) ---
    {"nome": "Marcio Aurelio Santana", "nome_guerra": "Santana", "identificador": "6052341", "tipo": "MILITAR", "posto_grad_cargo": "SO", "categoria": "Graduados", "divisao": "DACO-MN", "secao": "SLOG", "tempo_comara_meses": 70},
    {"nome": "Igor Camargo Pires", "nome_guerra": "Camargo", "identificador": "7052341", "tipo": "MILITAR", "posto_grad_cargo": "CB", "categoria": "Pracas", "divisao": "DACO-MN", "secao": "SINFRA", "tempo_comara_meses": 25},
    {"nome": "Eduardo Ramos Teixeira", "nome_guerra": "Teixeira", "identificador": "777.888.999-00", "tipo": "CIVIL", "posto_grad_cargo": "SPTF", "categoria": "Civil", "divisao": "DACO-MN", "secao": "SADM", "tempo_comara_meses": 40},

    # --- VP (Vice-Presidência e Assessorias) ---
    {"nome": "Wagner Antunes Ribeiro", "nome_guerra": "W. Ribeiro", "identificador": "6062341", "tipo": "MILITAR", "posto_grad_cargo": "1S", "categoria": "Graduados", "divisao": "VP", "secao": "ACI", "tempo_comara_meses": 65},
    {"nome": "Pedro Henrique Batista", "nome_guerra": "P. Batista", "identificador": "7062341", "tipo": "MILITAR", "posto_grad_cargo": "CB", "categoria": "Pracas", "divisao": "VP", "secao": "SCS", "tempo_comara_meses": 22},
    {"nome": "Beatriz Mendes Souza", "nome_guerra": "Beatriz", "identificador": "888.999.000-11", "tipo": "CIVIL", "posto_grad_cargo": "SPPF", "categoria": "Civil", "divisao": "VP", "secao": "AJUR", "tempo_comara_meses": 85}
]

# Contas LDAP Iniciais para Demonstração e Homologação
CONTAS_LDAP_INICIAIS = [
    # 1. ADMINISTRADOR
    {"ldap_username": "admin.dpti", "nome_completo": "Cap Eng Linhares", "identificador": "4509123", "papel": "ADMINISTRADOR", "divisao": "DPC", "secao": "DPTI", "status": "ATIVO", "vinculado_por": "SISTEMA", "senha": "comara"},
    # 2. CMDT_OM (Presidente da COMARA)
    {"ldap_username": "trigueiro.cmdt", "nome_completo": "Cel Av Antonio Carlos Neves Trigueiro", "identificador": "3800000", "papel": "CMDT_OM", "divisao": "VP", "secao": "CMDO", "status": "ATIVO", "vinculado_por": "admin.dpti", "senha": "comara"},
    # 3. CHEFES DE DIVISÃO
    {"ldap_username": "moreira.cde", "nome_completo": "Maj Eng Luís Mauro Moreira de Sá", "identificador": "3800007", "papel": "CHEFE_DIVISAO", "divisao": "DE", "secao": "DEPJ", "status": "ATIVO", "vinculado_por": "admin.dpti", "senha": "comara"},
    {"ldap_username": "leitao.cdl", "nome_completo": "Ten Cel Int Antonio José de Jesus Belém Leitão Junior", "identificador": "3800005", "papel": "CHEFE_DIVISAO", "divisao": "DL", "secao": "DLCP", "status": "ATIVO", "vinculado_por": "admin.dpti", "senha": "comara"},
    {"ldap_username": "levy.cda", "nome_completo": "Ten Cel Av Adenirson Levy Santos da Cruz", "identificador": "3800004", "papel": "CHEFE_DIVISAO", "divisao": "DA", "secao": "DASD", "status": "ATIVO", "vinculado_por": "admin.dpti", "senha": "comara"},
    {"ldap_username": "siqueira.cdpc", "nome_completo": "Cel Av Siqueira", "identificador": "3567812", "papel": "CHEFE_DIVISAO", "divisao": "DPC", "secao": "DPC", "status": "ATIVO", "vinculado_por": "admin.dpti", "senha": "comara"},
    {"ldap_username": "rocha.cdaco", "nome_completo": "Ten Cel Av Rocha", "identificador": "3910293", "papel": "CHEFE_DIVISAO", "divisao": "DACO-MN", "secao": "DACO-MN", "status": "ATIVO", "vinculado_por": "admin.dpti", "senha": "comara"},
    {"ldap_username": "baptista.vp", "nome_completo": "Cel Av Baptista", "identificador": "3109283", "papel": "CHEFE_DIVISAO", "divisao": "VP", "secao": "VP", "status": "ATIVO", "vinculado_por": "admin.dpti", "senha": "comara"},
    # 4. CHEFES DE SEÇÃO (OFICIAIS)
    {"ldap_username": "secao.depl", "nome_completo": "1T Eng Anthony Belo Vasconcelos Santos", "identificador": "3800018", "papel": "CHEFE_SECAO", "divisao": "DE", "secao": "DEPL", "status": "ATIVO", "vinculado_por": "admin.dpti", "senha": "comara"},
    {"ldap_username": "secao.depj", "nome_completo": "Cap Eng Lacerda", "identificador": "4910294", "papel": "CHEFE_SECAO", "divisao": "DE", "secao": "DEPJ", "status": "ATIVO", "vinculado_por": "admin.dpti", "senha": "comara"},
    {"ldap_username": "secao.dapc", "nome_completo": "Cap Esp Silva", "identificador": "4321098", "papel": "CHEFE_SECAO", "divisao": "DA", "secao": "DAPC", "status": "ATIVO", "vinculado_por": "admin.dpti", "senha": "comara"},
    {"ldap_username": "secao.dapm", "nome_completo": "1T QOCon Ramos", "identificador": "4321099", "papel": "CHEFE_SECAO", "divisao": "DA", "secao": "DAPM", "status": "ATIVO", "vinculado_por": "admin.dpti", "senha": "comara"},
    {"ldap_username": "secao.dltr", "nome_completo": "Cap Esp Garcez", "identificador": "4810291", "papel": "CHEFE_SECAO", "divisao": "DL", "secao": "DLTR", "status": "ATIVO", "vinculado_por": "admin.dpti", "senha": "comara"},
    {"ldap_username": "secao.dpti", "nome_completo": "1S Macedo (Danilo Macedo)", "identificador": "6042341", "papel": "CHEFE_SECAO", "divisao": "DPC", "secao": "DPTI", "status": "ATIVO", "vinculado_por": "admin.dpti", "senha": "comara"},
    # 5. USUÁRIO COMUM (ELEITOR OFICIAL)
    {"ldap_username": "guedes.so", "nome_completo": "SO BCO Rosivaldo Guedes de Souza", "identificador": "6000060", "papel": "USUARIO_COMUM", "divisao": "DE", "secao": "DELP", "status": "ATIVO", "vinculado_por": "admin.dpti", "senha": "comara"}
]

def seed_database():
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()

    # Inserir Divisões
    for d in DIVISOES_OFICIAIS:
        cursor.execute("""
        INSERT OR REPLACE INTO divisoes (sigla, nome, chefe_nome, chefe_saram_cpf, chefe_ldap)
        VALUES (?, ?, ?, ?, ?)
        """, (d["sigla"], d["nome"], d["chefe_nome"], d["chefe_saram_cpf"], d["chefe_ldap"]))

    # Inserir Seções
    for s in SECOES_OFICIAIS:
        cursor.execute("""
        INSERT OR REPLACE INTO secoes (sigla, nome, divisao_sigla, subdivisao, chefe_nome, chefe_ldap)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (s["sigla"], s["nome"], s["divisao_sigla"], s["subdivisao"], s["chefe_nome"], s["chefe_ldap"]))

    # Inserir Efetivo Inicial apenas se a base estiver zerada
    cursor.execute("SELECT COUNT(*) as total FROM efetivo")
    if cursor.fetchone()["total"] == 0:
        for e in EFETIVO_INICIAL:
            cursor.execute("""
            INSERT INTO efetivo (nome, nome_guerra, identificador, tipo, posto_grad_cargo, categoria, divisao, secao, tempo_comara_meses)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (e["nome"], e["nome_guerra"], e["identificador"], e["tipo"], e["posto_grad_cargo"],
                  e["categoria"], e["divisao"], e["secao"], e["tempo_comara_meses"]))

    # Inserir Contas LDAP Iniciais sem sobrescrever contas já modificadas
    agora = "2026-09-16T12:00:00"
    for u in CONTAS_LDAP_INICIAIS:
        cursor.execute("SELECT id FROM usuarios_ldap WHERE ldap_username = ?", (u["ldap_username"],))
        if not cursor.fetchone():
            shash = hash_senha(u["senha"])
            vinculado_em = agora if u["status"] == "ATIVO" else None
            cursor.execute("""
            INSERT INTO usuarios_ldap (ldap_username, nome_completo, identificador, papel, divisao, secao, status, vinculado_por, vinculado_em, senha_hash, criado_em, ativo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """, (u["ldap_username"], u["nome_completo"], u["identificador"], u["papel"], u["divisao"], u["secao"],
                  u["status"], u["vinculado_por"], vinculado_em, shash, agora))

    # Inicializar Controle de Fases
    cursor.execute("SELECT id FROM controle_fases LIMIT 1")
    if not cursor.fetchone():
        cursor.execute("""
        INSERT INTO controle_fases (fase_atual, iniciado_em, atualizado_em, atualizado_por)
        VALUES ('FASE_1_SECAO', ?, ?, 'admin.dpti')
        """, (agora, agora))

    conn.commit()
    conn.close()

    registrar_log("CARGA_NOVO_FLUXO", "ADMINISTRADOR", "GERAL", "Estrutura e banco inicial provisionados para o fluxo de 5 fases e DPTI.")
    print("Banco de dados atualizado com o fluxo em 5 fases e controle de aprovação DPTI.")

if __name__ == "__main__":
    seed_database()
