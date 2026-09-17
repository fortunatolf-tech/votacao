"""
Módulo de Banco de Dados SQLite e Auditoria Criptográfica
Sistema 'Padrão do Ano' - COMARA
Processo em 5 Fases: Seção -> Divisão -> Veto -> Votação Geral -> Decisão do Comandante
"""
import sqlite3
import os
import hashlib
from datetime import datetime
from typing import Optional, List, Dict, Any

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "comara_padrao.db")

def get_db_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Tabela de Divisões Oficiais da COMARA (RICA 21-209)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS divisoes (
        sigla TEXT PRIMARY KEY,
        nome TEXT NOT NULL,
        chefe_nome TEXT NOT NULL,
        chefe_saram_cpf TEXT NOT NULL,
        chefe_ldap TEXT
    )
    """)

    # 2. Tabela de Subdivisões e Seções (RICA 21-209 Anexos A-F)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS secoes (
        sigla TEXT PRIMARY KEY,
        nome TEXT NOT NULL,
        divisao_sigla TEXT NOT NULL,
        subdivisao TEXT,
        chefe_nome TEXT,
        chefe_ldap TEXT,
        FOREIGN KEY (divisao_sigla) REFERENCES divisoes (sigla)
    )
    """)

    # 3. Tabela de Usuários com Vínculo LDAP e Status DPTI
    # Papéis: 'ADMINISTRADOR', 'CMDT_OM', 'CHEFE_DIVISAO', 'CHEFE_SECAO', 'USUARIO_COMUM'
    # Status: 'PENDENTE_DPTI', 'ATIVO'
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS usuarios_ldap (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ldap_username TEXT UNIQUE NOT NULL,
        nome_completo TEXT NOT NULL,
        identificador TEXT NOT NULL, -- SARAM ou CPF
        papel TEXT NOT NULL DEFAULT 'USUARIO_COMUM',
        divisao TEXT,
        secao TEXT,
        status TEXT NOT NULL DEFAULT 'PENDENTE_DPTI', -- 'PENDENTE_DPTI' ou 'ATIVO'
        vinculado_por TEXT,
        vinculado_em TEXT,
        senha_hash TEXT NOT NULL,
        criado_em TEXT NOT NULL,
        ativo INTEGER NOT NULL DEFAULT 1
    )
    """)

    # 4. Tabela do Efetivo Completo (Militares e Civis)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS efetivo (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        nome_guerra TEXT NOT NULL,
        identificador TEXT UNIQUE NOT NULL, -- SARAM para militar, CPF para civil
        tipo TEXT NOT NULL, -- 'MILITAR' ou 'CIVIL'
        posto_grad_cargo TEXT NOT NULL,
        categoria TEXT NOT NULL, -- 'Civil', 'Pracas', 'Graduados'
        divisao TEXT NOT NULL,
        secao TEXT NOT NULL,
        tempo_comara_meses INTEGER NOT NULL DEFAULT 0,
        ativo INTEGER NOT NULL DEFAULT 1,
        FOREIGN KEY (divisao) REFERENCES divisoes (sigla)
    )
    """)

    # 5. Controle da Fase do Processo Eleitoral
    # Fases: 'FASE_1_SECAO', 'FASE_2_DIVISAO', 'FASE_3_VETO', 'FASE_4_VOTACAO_GERAL', 'FASE_5_COMANDANTE', 'FINALIZADO'
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS controle_fases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fase_atual TEXT NOT NULL DEFAULT 'FASE_1_SECAO',
        iniciado_em TEXT NOT NULL,
        atualizado_em TEXT NOT NULL,
        atualizado_por TEXT NOT NULL
    )
    """)

    # 6. Fase 1: Indicação por Chefes de Seção (1 subordinado por classe da seção)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS indicacoes_fase1_secao (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        secao TEXT NOT NULL,
        divisao TEXT NOT NULL,
        categoria TEXT NOT NULL, -- 'Civil', 'Pracas', 'Graduados'
        candidato_id INTEGER NOT NULL,
        indicado_por_ldap TEXT NOT NULL,
        data_hora TEXT NOT NULL,
        UNIQUE(secao, categoria),
        FOREIGN KEY (candidato_id) REFERENCES efetivo (id)
    )
    """)

    # 7. Fase 2: Seleção por Chefes de Divisão (2 por classe da divisão entre os indicados pelas seções)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS indicacoes_fase2_divisao (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        divisao TEXT NOT NULL,
        categoria TEXT NOT NULL,
        candidato_id INTEGER NOT NULL,
        indicado_por_ldap TEXT NOT NULL,
        data_hora TEXT NOT NULL,
        UNIQUE(divisao, categoria, candidato_id),
        FOREIGN KEY (candidato_id) REFERENCES efetivo (id)
    )
    """)

    # 8. Fase 3: Rodada de Veto pelos Chefes de Divisão
    # voto_veto: 1 = VETA, 0 = NÃO VETA (APROVA)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS vetos_fase3 (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        candidato_id INTEGER NOT NULL,
        chefe_divisao_ldap TEXT NOT NULL,
        voto_veto INTEGER NOT NULL DEFAULT 0, -- 0 = Não veta, 1 = Veta
        data_hora TEXT NOT NULL,
        UNIQUE(candidato_id, chefe_divisao_ldap),
        FOREIGN KEY (candidato_id) REFERENCES efetivo (id)
    )
    """)

    # 9. Fase 4: Votação Geral por Todo o Efetivo (Por Clique Sem Notas)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS votos_fase4 (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        voter_hash TEXT NOT NULL,
        categoria TEXT NOT NULL,
        candidato_id INTEGER NOT NULL,
        data_hora TEXT NOT NULL,
        UNIQUE(voter_hash, categoria),
        FOREIGN KEY (candidato_id) REFERENCES efetivo (id)
    )
    """)

    # 10. Controle de Eleitores que Votaram na Fase 4
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS eleitores_votaram (
        voter_hash TEXT PRIMARY KEY,
        identificador_mascarado TEXT NOT NULL,
        data_hora TEXT NOT NULL,
        efetivo_id INTEGER
    )
    """)

    # Migration: Adicionar coluna efetivo_id se tabela já existir sem ela
    cursor.execute("PRAGMA table_info(eleitores_votaram)")
    colunas_eleitores = [row[1] for row in cursor.fetchall()]
    if "efetivo_id" not in colunas_eleitores:
        cursor.execute("ALTER TABLE eleitores_votaram ADD COLUMN efetivo_id INTEGER")

    # 11. Fase 5: Apreciação e Decisão do Presidente da COMARA
    # acao_comando: 'HOMOLOGADO_ELEITO' ou 'INDICADO_DIRETO_CMDT'
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS decisao_fase5_comando (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        categoria TEXT NOT NULL,
        candidato_mais_votado_id INTEGER NOT NULL,
        candidato_final_id INTEGER NOT NULL,
        acao_comando TEXT NOT NULL, -- 'HOMOLOGADO_ELEITO' ou 'INDICADO_DIRETO_CMDT'
        despacho TEXT NOT NULL,
        comandante_nome TEXT NOT NULL,
        comandante_saram TEXT NOT NULL,
        data_hora TEXT NOT NULL,
        assinatura_digital_hash TEXT NOT NULL,
        UNIQUE(categoria),
        FOREIGN KEY (candidato_final_id) REFERENCES efetivo (id)
    )
    """)

    # 12. Trilha de Auditoria Imutável com Hash SHA-256 Encadeado
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS logs_auditoria (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        tipo_evento TEXT NOT NULL,
        usuario TEXT NOT NULL,
        divisao TEXT,
        detalhes TEXT NOT NULL,
        hash_registro TEXT NOT NULL,
        hash_anterior TEXT
    )
    """)

    conn.commit()
    conn.close()

def hash_senha(senha: str) -> str:
    return hashlib.sha256(f"COMARA_SALT_2026:{senha}".encode("utf-8")).hexdigest()

def registrar_log(tipo_evento: str, usuario: str, divisao: Optional[str], detalhes: str) -> str:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT hash_registro FROM logs_auditoria ORDER BY id DESC LIMIT 1")
    row = cursor.fetchone()
    hash_anterior = row["hash_registro"] if row else "GENESIS_HASH_COMARA_PADRAO_ANO_2026"
    
    timestamp = datetime.now().isoformat()
    raw_str = f"{hash_anterior}|{timestamp}|{tipo_evento}|{usuario}|{divisao or ''}|{detalhes}"
    hash_registro = hashlib.sha256(raw_str.encode("utf-8")).hexdigest()
    
    cursor.execute("""
    INSERT INTO logs_auditoria (timestamp, tipo_evento, usuario, divisao, detalhes, hash_registro, hash_anterior)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (timestamp, tipo_evento, usuario, divisao, detalhes, hash_registro, hash_anterior))
    conn.commit()
    conn.close()
    return hash_registro

def obter_logs(limite: int = 100) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM logs_auditoria ORDER BY id DESC LIMIT ?", (limite,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]
