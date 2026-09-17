"""
Servidor Principal FastAPI - Sistema Oficial 'Padrão do Ano' (COMARA)
Processo Eleitoral Completo em 5 Fases e Controle de Vínculo DPTI
"""
import os
import sys
import hashlib
from datetime import datetime
from typing import List, Dict, Any, Optional

# Garante importação direta de módulos locais em ambientes de produção (aaPanel / Gunicorn / Docker)
_backend_dir = os.path.dirname(os.path.abspath(__file__))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from database import get_db_connection, init_db, registrar_log, obter_logs, hash_senha
from logic import (
    CATEGORIAS_OFICIAIS,
    NOMES_CLASSES,
    gerar_hash_eleitor,
    validar_indicacao_fase1,
    validar_selecao_fase2,
    apurar_vetos_fase3,
    apurar_votos_fase4
)
from test_suite import rodar_testes_e_obter_relatorio

init_db()

app = FastAPI(
    title="Sistema Oficial de Votação e Seleção - Padrão do Ano (COMARA)",
    version="3.0.0",
    description="Sistema oficial COMARA com fluxo em 5 fases e aprovação na DPTI."
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Modelos Pydantic
class AutoCadastroInput(BaseModel):
    nome_completo: str
    nome_guerra: str
    identificador: str # SARAM ou CPF
    tipo: str # MILITAR ou CIVIL
    posto_grad_cargo: str
    categoria: str # Graduados, Pracas, Civil
    divisao: str
    secao: str
    tempo_comara_meses: int = 0
    ldap_username: str
    senha: str

class DptiLiberarInput(BaseModel):
    usuario_id: int
    ldap_username: str
    papel: str # USUARIO_COMUM, CHEFE_SECAO, CHEFE_DIVISAO, CMDT_OM, ADMINISTRADOR
    divisao: str
    secao: str
    admin_username: str

class LoginLdapInput(BaseModel):
    ldap_username: str
    password: str

class AvancarFaseInput(BaseModel):
    nova_fase: str
    usuario_admin: str

class IndicarFase1Input(BaseModel):
    secao: str
    categoria: str
    candidato_id: int
    ldap_username: str

class SelecionarFase2Input(BaseModel):
    divisao: str
    categoria: str
    candidato_ids: List[int] # até 2 candidatos
    ldap_username: str

class VotarVetoFase3Input(BaseModel):
    candidato_id: int
    voto_veto: int # 1 = Veta, 0 = Não veta / Aprova
    ldap_username: str

class VotoGeralFase4Input(BaseModel):
    identificador: str # SARAM ou CPF
    votos: Dict[str, int] # {"Graduados": cid, "Pracas": cid, "Civil": cid}

class DecisaoComandoFase5Input(BaseModel):
    categoria: str
    candidato_mais_votado_id: int
    candidato_final_id: int
    acao_comando: str # 'HOMOLOGADO_ELEITO' ou 'INDICADO_DIRETO_CMDT'
    despacho: str
    comandante_nome: str
    comandante_saram: str
    ldap_username: str

# ----------------- 1. AUTO-CADASTRO E GESTÃO DPTI -----------------

@app.post("/api/auth/auto-cadastro")
def auto_cadastro_usuario(dados: AutoCadastroInput):
    """
    Auto-cadastro de militar ou civil.
    A conta é criada como USUARIO_COMUM com status PENDENTE_DPTI (bloqueada para login).
    """
    if dados.categoria not in CATEGORIAS_OFICIAIS:
        raise HTTPException(status_code=400, detail=f"Categoria inválida. Opções: {CATEGORIAS_OFICIAIS}")
        
    username = dados.ldap_username.strip().lower()
    shash = hash_senha(dados.senha)
    agora = datetime.now().isoformat()
    
    conn = get_db_connection()
    c = conn.cursor()
    
    # 1. Atualizar ou inserir no efetivo
    c.execute("""
    INSERT OR REPLACE INTO efetivo (nome, nome_guerra, identificador, tipo, posto_grad_cargo, categoria, divisao, secao, tempo_comara_meses)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (dados.nome_completo.strip(), dados.nome_guerra.strip(), dados.identificador.strip(),
          dados.tipo.strip().upper(), dados.posto_grad_cargo.strip(), dados.categoria,
          dados.divisao.strip(), dados.secao.strip(), dados.tempo_comara_meses))
          
    # 2. Inserir na fila de usuários LDAP com status PENDENTE_DPTI
    try:
        c.execute("""
        INSERT INTO usuarios_ldap (ldap_username, nome_completo, identificador, papel, divisao, secao, status, senha_hash, criado_em, ativo)
        VALUES (?, ?, ?, 'USUARIO_COMUM', ?, ?, 'PENDENTE_DPTI', ?, ?, 1)
        """, (username, dados.nome_completo.strip(), dados.identificador.strip(),
              dados.divisao.strip(), dados.secao.strip(), shash, agora))
        conn.commit()
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=400, detail=f"O login LDAP '{username}' ou identificador já possui cadastro pendente ou ativo no sistema.")

    conn.close()
    registrar_log("AUTO_CADASTRO_SUBMETIDO", username, dados.divisao, 
                  f"Auto-cadastro efetuado para {dados.posto_grad_cargo} {dados.nome_guerra}. Aguardando liberação na DPTI.")

    return {
        "sucesso": True,
        "mensagem": "Cadastro realizado com sucesso! Para começar a utilizar o sistema, compareça à DPTI para vincular sua conta de rede (LDAP) e liberar seu acesso."
    }

@app.get("/api/admin/dpti-fila")
def listar_fila_dpti():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
    SELECT id, ldap_username, nome_completo, identificador, papel, divisao, secao, status, criado_em, vinculado_por, vinculado_em
    FROM usuarios_ldap
    ORDER BY CASE WHEN status = 'PENDENTE_DPTI' THEN 0 ELSE 1 END, id DESC
    """)
    usuarios = [dict(r) for r in c.fetchall()]
    conn.close()
    return usuarios

@app.get("/api/efetivo")
def listar_efetivo(divisao: Optional[str] = None, categoria: Optional[str] = None):
    conn = get_db_connection()
    c = conn.cursor()
    query = "SELECT * FROM efetivo WHERE 1=1"
    params = []
    if divisao:
        query += " AND divisao = ?"
        params.append(divisao)
    if categoria:
        query += " AND categoria = ?"
        params.append(categoria)
    query += " ORDER BY divisao, secao, categoria, posto_grad_cargo"
    c.execute(query, params)
    registros = [dict(r) for r in c.fetchall()]
    conn.close()
    return registros

@app.post("/api/admin/dpti-liberar")
def liberar_cadastro_dpti(dados: DptiLiberarInput):
    """
    O Administrador da DPTI vincula a conta de rede LDAP do usuário e atribui seu modificador de acesso definitivo.
    """
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM usuarios_ldap WHERE id = ?", (dados.usuario_id,))
    u = c.fetchone()
    if not u:
        conn.close()
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")

    agora = datetime.now().isoformat()
    c.execute("""
    UPDATE usuarios_ldap
    SET ldap_username = ?, papel = ?, divisao = ?, secao = ?, status = 'ATIVO', 
        vinculado_por = ?, vinculado_em = ?
    WHERE id = ?
    """, (dados.ldap_username.strip().lower(), dados.papel, dados.divisao, dados.secao,
          dados.admin_username, agora, dados.usuario_id))
    conn.commit()
    conn.close()

    registrar_log("DPTI_LIBERACAO_CONTA", dados.admin_username, dados.divisao,
                  f"Conta ID {dados.usuario_id} liberada. LDAP: '{dados.ldap_username}', Papel: '{dados.papel}'")

    return {
        "sucesso": True,
        "mensagem": f"Cadastro liberado com sucesso pela DPTI! O usuário '{dados.ldap_username}' agora está ativo como {dados.papel}."
    }

# ----------------- 2. AUTENTICAÇÃO LDAP -----------------

@app.post("/api/auth/login-ldap")
def login_ldap(credenciais: LoginLdapInput):
    username = credenciais.ldap_username.strip().lower()
    shash = hash_senha(credenciais.password)
    
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM usuarios_ldap WHERE LOWER(ldap_username) = ?", (username,))
    u = c.fetchone()
    
    if not u or u["senha_hash"] != shash:
        conn.close()
        registrar_log("FALHA_LOGIN_LDAP", username, None, "Tentativa com credenciais inválidas.")
        raise HTTPException(status_code=401, detail="Usuário de rede (LDAP) ou senha incorretos.")
        
    # Bloqueio estrito: Se pendente de validação presencial na DPTI
    if u["status"] == "PENDENTE_DPTI":
        conn.close()
        registrar_log("BLOQUEIO_PENDENCIA_DPTI", username, u["divisao"], "Acesso negado: Conta aguarda liberação presencial na DPTI.")
        raise HTTPException(
            status_code=403,
            detail="Acesso Bloqueado: Seu cadastro foi realizado, mas ainda NÃO FOI LIBERADO pela DPTI. Compareça à DPTI para vincular sua conta LDAP e liberar o seu acesso."
        )

    if u["ativo"] != 1:
        conn.close()
        raise HTTPException(status_code=403, detail="Conta desativada pelo Administrador.")

    c.execute("SELECT posto_grad_cargo, nome_guerra, categoria FROM efetivo WHERE identificador = ?", (u["identificador"],))
    efetivo_info = c.fetchone()
    conn.close()

    registrar_log("LOGIN_SUCESSO", username, u["divisao"], f"Autenticado no sistema como {u['papel']}.")

    return {
        "sucesso": True,
        "ldap_username": u["ldap_username"],
        "nome_completo": u["nome_completo"],
        "identificador": u["identificador"],
        "papel": u["papel"],
        "divisao": u["divisao"],
        "secao": u["secao"],
        "posto_grad_cargo": efetivo_info["posto_grad_cargo"] if efetivo_info else "",
        "nome_guerra": efetivo_info["nome_guerra"] if efetivo_info else u["nome_completo"],
        "categoria": efetivo_info["categoria"] if efetivo_info else ""
    }

# ----------------- 3. CONTROLE DE FASES ELEITORAIS -----------------

FASES_ORDEM = ["FASE_1_SECAO", "FASE_2_DIVISAO", "FASE_3_VETO", "FASE_4_VOTACAO_GERAL", "FASE_5_COMANDANTE", "FINALIZADO"]

NOMES_FASES = {
    "FASE_1_SECAO": "Fase 1: Indicação pelos Chefes de Seção (1 por classe)",
    "FASE_2_DIVISAO": "Fase 2: Seleção pelos Chefes de Divisão (2 por classe da divisão)",
    "FASE_3_VETO": "Fase 3: Rodada de Veto pelos Chefes de Divisão",
    "FASE_4_VOTACAO_GERAL": "Fase 4: Votação Geral por Todo o Efetivo (Por Clique Direto)",
    "FASE_5_COMANDANTE": "Fase 5: Apreciação e Escolha Final do Presidente da COMARA",
    "FINALIZADO": "Processo Eleitoral Concluído e Publicado"
}

@app.get("/api/fases/status")
def obter_status_fases():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM controle_fases ORDER BY id DESC LIMIT 1")
    cf = c.fetchone()
    fase_atual = cf["fase_atual"] if cf else "FASE_1_SECAO"

    c.execute("SELECT COUNT(*) as total FROM indicacoes_fase1_secao")
    total_f1 = c.fetchone()["total"]

    c.execute("SELECT COUNT(*) as total FROM indicacoes_fase2_divisao")
    total_f2 = c.fetchone()["total"]

    c.execute("SELECT COUNT(*) as total FROM vetos_fase3")
    total_f3 = c.fetchone()["total"]

    c.execute("SELECT COUNT(*) as total FROM eleitores_votaram")
    total_votantes_f4 = c.fetchone()["total"]

    c.execute("SELECT COUNT(*) as total FROM decisao_fase5_comando")
    total_decisoes_f5 = c.fetchone()["total"]
    conn.close()

    return {
        "fase_atual": fase_atual,
        "fase_nome": NOMES_FASES.get(fase_atual, fase_atual),
        "fases_ordem": FASES_ORDEM,
        "totais": {
            "fase1_indicacoes": total_f1,
            "fase2_indicacoes": total_f2,
            "fase3_vetos": total_f3,
            "fase4_votantes": total_votantes_f4,
            "fase5_decisoes": total_decisoes_f5
        }
    }

@app.post("/api/fases/avancar")
def avancar_fase_eleitoral(dados: AvancarFaseInput):
    """Avança ou altera a fase do processo eleitoral (exclusivo Admin / Comandante)."""
    if dados.nova_fase not in FASES_ORDEM:
        raise HTTPException(status_code=400, detail=f"Fase inválida. Opções: {FASES_ORDEM}")
        
    agora = datetime.now().isoformat()
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
    INSERT INTO controle_fases (fase_atual, iniciado_em, atualizado_em, atualizado_por)
    VALUES (?, ?, ?, ?)
    """, (dados.nova_fase, agora, agora, dados.usuario_admin))
    conn.commit()
    conn.close()

    registrar_log("FASE_AVANCADA", dados.usuario_admin, "COMANDO", 
                  f"Processo avançado para a fase: {dados.nova_fase}")
    return {"sucesso": True, "fase_atual": dados.nova_fase, "nome": NOMES_FASES.get(dados.nova_fase)}

# ----------------- 4. FASE 1: INDICAÇÃO POR CHEFES DE SEÇÃO -----------------

@app.get("/api/fase1/meus-subordinados")
def listar_subordinados_secao(secao: str, ldap_username: Optional[str] = None):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM efetivo WHERE secao = ? ORDER BY categoria, posto_grad_cargo", (secao,))
    membros = [dict(r) for r in c.fetchall()]

    c.execute("SELECT categoria, candidato_id FROM indicacoes_fase1_secao WHERE secao = ?", (secao,))
    indicados = {r["categoria"]: r["candidato_id"] for r in c.fetchall()}
    conn.close()

    agrupados = {cat: [] for cat in CATEGORIAS_OFICIAIS}
    for m in membros:
        if m["categoria"] in agrupados:
            agrupados[m["categoria"]].append(m)

    return {
        "secao": secao,
        "membros_por_categoria": agrupados,
        "indicacoes_feitas": indicados
    }

@app.post("/api/fase1/indicar")
def salvar_indicacao_fase1(dados: IndicarFase1Input):
    """Chefe de Seção indica 1 subordinado por classe da sua seção."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM efetivo WHERE id = ?", (dados.candidato_id,))
    cand = c.fetchone()
    if not cand:
        conn.close()
        raise HTTPException(status_code=404, detail="Candidato não encontrado.")

    valido, msg = validar_indicacao_fase1(dict(cand), dados.secao, dados.categoria)
    if not valido:
        conn.close()
        raise HTTPException(status_code=400, detail=msg)

    agora = datetime.now().isoformat()
    c.execute("""
    INSERT OR REPLACE INTO indicacoes_fase1_secao (secao, divisao, categoria, candidato_id, indicado_por_ldap, data_hora)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (dados.secao, cand["divisao"], dados.categoria, dados.candidato_id, dados.ldap_username, agora))
    conn.commit()
    conn.close()

    registrar_log("FASE1_INDICACAO_SECAO", dados.ldap_username, dados.secao,
                  f"Chefe indicou {cand['posto_grad_cargo']} {cand['nome_guerra']} como representante da Seção {dados.secao} na classe {dados.categoria}.")
    return {"sucesso": True, "mensagem": f"{cand['posto_grad_cargo']} {cand['nome_guerra']} indicado com sucesso pela Seção {dados.secao}."}

# ----------------- 5. FASE 2: SELEÇÃO POR CHEFES DE DIVISÃO -----------------

@app.get("/api/fase2/indicados-secoes")
def listar_indicados_secoes_divisao(divisao: str):
    """Retorna os militares e civis indicados pelas seções subordinadas à divisão."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
    SELECT e.id, e.nome, e.nome_guerra, e.posto_grad_cargo, e.categoria, e.divisao, e.secao, e.tempo_comara_meses,
           i.secao as secao_origem, i.data_hora
    FROM indicacoes_fase1_secao i
    JOIN efetivo e ON i.candidato_id = e.id
    WHERE i.divisao = ?
    ORDER BY e.categoria, e.nome_guerra
    """, (divisao,))
    candidatos = [dict(r) for r in c.fetchall()]

    c.execute("SELECT categoria, candidato_id FROM indicacoes_fase2_divisao WHERE divisao = ?", (divisao,))
    selecionados_rows = c.fetchall()
    conn.close()

    selecionados = {cat: [] for cat in CATEGORIAS_OFICIAIS}
    for r in selecionados_rows:
        selecionados[r["categoria"]].append(r["candidato_id"])

    agrupados = {cat: [] for cat in CATEGORIAS_OFICIAIS}
    for cand in candidatos:
        if cand["categoria"] in agrupados:
            agrupados[cand["categoria"]].append(cand)

    return {
        "divisao": divisao,
        "indicados_por_categoria": agrupados,
        "selecionados_fase2": selecionados
    }

@app.post("/api/fase2/selecionar-divisao")
def salvar_selecao_fase2(dados: SelecionarFase2Input):
    """Chefe de Divisão seleciona até 2 indicados por classe para representar a divisão."""
    if len(dados.candidato_ids) > 2:
        raise HTTPException(status_code=400, detail="O Chefe de Divisão pode selecionar no máximo 2 candidatos por categoria.")

    conn = get_db_connection()
    c = conn.cursor()
    
    # Remove seleções anteriores da divisão nessa categoria
    c.execute("DELETE FROM indicacoes_fase2_divisao WHERE divisao = ? AND categoria = ?", (dados.divisao, dados.categoria))
    
    agora = datetime.now().isoformat()
    for cid in dados.candidato_ids:
        c.execute("""
        INSERT INTO indicacoes_fase2_divisao (divisao, categoria, candidato_id, indicado_por_ldap, data_hora)
        VALUES (?, ?, ?, ?, ?)
        """, (dados.divisao, dados.categoria, cid, dados.ldap_username, agora))
        
    conn.commit()
    conn.close()

    registrar_log("FASE2_SELECAO_DIVISAO", dados.ldap_username, dados.divisao,
                  f"Chefe de Divisão selecionou {len(dados.candidato_ids)} candidatos na categoria {dados.categoria}.")
    return {"sucesso": True, "mensagem": f"{len(dados.candidato_ids)} representantes da Divisão {dados.divisao} homologados para a Fase 3."}

# ----------------- 6. FASE 3: RODADA DE VETO PELOS CHEFES DE DIVISÃO -----------------

@app.get("/api/fase3/candidatos-veto")
def listar_candidatos_para_veto(chefe_ldap: Optional[str] = None):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
    SELECT DISTINCT e.id, e.nome, e.nome_guerra, e.posto_grad_cargo, e.categoria, e.divisao, e.secao, e.tempo_comara_meses
    FROM indicacoes_fase2_divisao i
    JOIN efetivo e ON i.candidato_id = e.id
    ORDER BY e.categoria, e.divisao, e.nome_guerra
    """)
    candidatos = [dict(r) for r in c.fetchall()]

    c.execute("SELECT candidato_id, chefe_divisao_ldap, voto_veto FROM vetos_fase3")
    vetos = [dict(r) for r in c.fetchall()]

    c.execute("SELECT COUNT(*) as total FROM divisoes")
    total_divisoes = c.fetchone()["total"]
    conn.close()

    apurados = apurar_vetos_fase3(candidatos, vetos, total_divisoes)

    # Mapear votos do chefe logado se fornecido
    meus_votos = {}
    if chefe_ldap:
        meus_votos = {v["candidato_id"]: v["voto_veto"] for v in vetos if v["chefe_divisao_ldap"] == chefe_ldap}

    agrupados = {cat: [] for cat in CATEGORIAS_OFICIAIS}
    for item in apurados:
        item["meu_voto"] = meus_votos.get(item["id"])
        if item["categoria"] in agrupados:
            agrupados[item["categoria"]].append(item)

    return {
        "total_chefes": total_divisoes,
        "candidatos_por_categoria": agrupados
    }

@app.post("/api/fase3/votar-veto")
def votar_veto_fase3(dados: VotarVetoFase3Input):
    agora = datetime.now().isoformat()
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
    INSERT OR REPLACE INTO vetos_fase3 (candidato_id, chefe_divisao_ldap, voto_veto, data_hora)
    VALUES (?, ?, ?, ?)
    """, (dados.candidato_id, dados.ldap_username, dados.voto_veto, agora))
    conn.commit()
    conn.close()

    acao = "VETOU" if dados.voto_veto == 1 else "NÃO VETOU (Aprovou)"
    registrar_log("FASE3_VOTO_VETO", dados.ldap_username, "CHEFIA", f"Chefe {dados.ldap_username} {acao} o candidato ID {dados.candidato_id}.")
    return {"sucesso": True, "mensagem": f"Voto de veto ({acao}) registrado com sucesso."}

# ----------------- 7. FASE 4: VOTAÇÃO GERAL POR CLIQUE (SEM NOTAS) -----------------

@app.get("/api/fase4/cedula-geral")
def obter_cedula_fase4():
    """Retorna candidatos aprovados na Fase 3 para votação por clique simples."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
    SELECT DISTINCT e.id, e.nome, e.nome_guerra, e.posto_grad_cargo, e.categoria, e.divisao, e.secao, e.tempo_comara_meses
    FROM indicacoes_fase2_divisao i
    JOIN efetivo e ON i.candidato_id = e.id
    ORDER BY e.categoria, e.divisao, e.nome_guerra
    """)
    candidatos = [dict(r) for r in c.fetchall()]

    c.execute("SELECT candidato_id, chefe_divisao_ldap, voto_veto FROM vetos_fase3")
    vetos = [dict(r) for r in c.fetchall()]

    c.execute("SELECT COUNT(*) as total FROM divisoes")
    total_divisoes = c.fetchone()["total"]
    conn.close()

    apurados = apurar_vetos_fase3(candidatos, vetos, total_divisoes)
    
    # Apenas os não-vetados
    aprovados = [c for c in apurados if c["status_veto"] == "APROVADO_PARA_VOTACAO"]

    agrupados = {cat: [] for cat in CATEGORIAS_OFICIAIS}
    for cand in aprovados:
        if cand["categoria"] in agrupados:
            agrupados[cand["categoria"]].append(cand)

    return {
        "classes": NOMES_CLASSES,
        "candidatos_cedula": agrupados
    }

@app.post("/api/fase4/votar")
def registrar_voto_fase4(dados: VotoGeralFase4Input):
    """Computa o voto individual por clique (sem atribuição de notas!)."""
    ident_limpo = dados.identificador.strip().replace(".", "").replace("-", "")
    conn = get_db_connection()
    c = conn.cursor()
    
    c.execute("SELECT id, nome, identificador, divisao FROM efetivo WHERE REPLACE(REPLACE(identificador, '.', ''), '-', '') = ?", (ident_limpo,))
    eleitor = c.fetchone()
    if not eleitor:
        conn.close()
        raise HTTPException(status_code=403, detail="Identificador não cadastrado no efetivo ativo da COMARA.")
        
    voter_hash = gerar_hash_eleitor(eleitor["identificador"])
    c.execute("SELECT voter_hash FROM eleitores_votaram WHERE voter_hash = ?", (voter_hash,))
    if c.fetchone():
        conn.close()
        registrar_log("BLOQUEIO_VOTO_DUPLICADO", "ANONIMO", eleitor["divisao"], "Tentativa de re-votação bloqueada.")
        raise HTTPException(status_code=400, detail="Voto já computado para este eleitor.")

    # Validar que votou em 1 de cada classe ativa
    for cat in CATEGORIAS_OFICIAIS:
        if cat not in dados.votos or not dados.votos[cat]:
            conn.close()
            raise HTTPException(status_code=400, detail=f"Voto obrigatório na classe '{NOMES_CLASSES[cat]}'.")
            
    agora = datetime.now().isoformat()
    try:
        for cat, cand_id in dados.votos.items():
            c.execute("""
            INSERT INTO votos_fase4 (voter_hash, categoria, candidato_id, data_hora)
            VALUES (?, ?, ?, ?)
            """, (voter_hash, cat, cand_id, agora))
            
        mascara = eleitor["identificador"][:3] + "***" + eleitor["identificador"][-2:]
        c.execute("""
        INSERT INTO eleitores_votaram (voter_hash, identificador_mascarado, data_hora)
        VALUES (?, ?, ?)
        """, (voter_hash, mascara, agora))
        conn.commit()
    except Exception as e:
        conn.rollback()
        conn.close()
        raise HTTPException(status_code=500, detail=f"Erro ao gravar voto: {str(e)}")
        
    conn.close()
    registrar_log("FASE4_VOTO_COMPUTADO", "ELEITOR", eleitor["divisao"], f"Voto por clique computado. Comprovante: {voter_hash[:12]}")
    return {
        "sucesso": True,
        "mensagem": "Voto computado com sucesso!",
        "comprovante_hash": voter_hash[:16].upper(),
        "data_hora": agora
    }

# ----------------- 8. FASE 5: APRECIAÇÃO E DECISÃO DO COMANDANTE DA OM -----------------

@app.get("/api/fase5/resultado-eleicao")
def obter_resultado_fase5():
    """Retorna a contagem de votos da Fase 4 e a decisão do Comandante."""
    conn = get_db_connection()
    c = conn.cursor()
    
    # Votos computados por candidato
    c.execute("SELECT candidato_id, COUNT(*) as total_votos FROM votos_fase4 GROUP BY candidato_id")
    contagem_votos = {r["candidato_id"]: r["total_votos"] for r in c.fetchall()}

    # Candidatos que participaram da votação
    c.execute("""
    SELECT DISTINCT e.id, e.nome, e.nome_guerra, e.posto_grad_cargo, e.categoria, e.divisao, e.secao, e.tempo_comara_meses
    FROM indicacoes_fase2_divisao i
    JOIN efetivo e ON i.candidato_id = e.id
    """)
    candidatos = [dict(r) for r in c.fetchall()]

    # Decisões do Comandante
    c.execute("""
    SELECT d.*, ef.nome_guerra as vencedor_nome_guerra, ef.posto_grad_cargo as vencedor_posto
    FROM decisao_fase5_comando d
    JOIN efetivo ef ON d.candidato_final_id = ef.id
    """)
    decisoes = {r["categoria"]: dict(r) for r in c.fetchall()}

    c.execute("SELECT COUNT(*) as total FROM eleitores_votaram")
    total_votantes = c.fetchone()["total"]
    conn.close()

    resultado = {}
    for cat in CATEGORIAS_OFICIAIS:
        cand_cat = [cand for cand in candidatos if cand["categoria"] == cat]
        apurados = apurar_votos_fase4(cand_cat, contagem_votos)
        resultado[cat] = {
            "classe_nome": NOMES_CLASSES[cat],
            "candidatos": apurados,
            "mais_votado": apurados[0] if apurados else None,
            "decisao_comando": decisoes.get(cat)
        }

    return {
        "total_votantes": total_votantes,
        "resultado_por_categoria": resultado,
        "concluido": len(decisoes) == len(CATEGORIAS_OFICIAIS)
    }

@app.post("/api/fase5/decisao-comandante")
def salvar_decisao_comandante(dados: DecisaoComandoFase5Input):
    """
    O Presidente da COMARA decide:
    - Se a favor: homologa o mais votado da classe.
    - Se contra: indica diretamente quem ele quer que seja o ganhador!
    """
    agora = datetime.now().isoformat()
    raw_sig = f"{dados.comandante_nome}|{dados.categoria}|{dados.candidato_final_id}|{dados.acao_comando}|{agora}"
    sig_hash = hashlib.sha256(raw_sig.encode("utf-8")).hexdigest()

    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
    INSERT OR REPLACE INTO decisao_fase5_comando (
        categoria, candidato_mais_votado_id, candidato_final_id, acao_comando, despacho, comandante_nome, comandante_saram, data_hora, assinatura_digital_hash
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (dados.categoria, dados.candidato_mais_votado_id, dados.candidato_final_id, dados.acao_comando,
          dados.despacho, dados.comandante_nome, dados.comandante_saram, agora, sig_hash))

    # Verifica se todas as 3 categorias foram decididas para finalizar o processo
    c.execute("SELECT COUNT(*) as total FROM decisao_fase5_comando")
    if c.fetchone()["total"] == len(CATEGORIAS_OFICIAIS):
        c.execute("""
        INSERT INTO controle_fases (fase_atual, iniciado_em, atualizado_em, atualizado_por)
        VALUES ('FINALIZADO', ?, ?, ?)
        """, (agora, agora, dados.ldap_username))

    conn.commit()
    conn.close()

    tipo_decisao = "HOMOLOGOU O MAIS VOTADO" if dados.acao_comando == "HOMOLOGADO_ELEITO" else f"INDICOU DIRETAMENTE O GANHADOR (ID {dados.candidato_final_id})"
    registrar_log("DECISAO_COMANDANTE_REGISTRADA", dados.comandante_nome, "COMANDO", 
                  f"Presidente da COMARA deliberou na classe {dados.categoria}: {tipo_decisao}.")

    return {
        "sucesso": True,
        "mensagem": f"Decisão do Presidente da COMARA para a classe '{NOMES_CLASSES[dados.categoria]}' formalizada com sucesso!",
        "assinatura_digital": sig_hash
    }

# ----------------- 9. AUDITORIA E TESTES -----------------

@app.get("/api/auditoria/logs")
def listar_logs_auditoria(limite: int = 50):
    return obter_logs(limite)

@app.post("/api/testes/executar")
def executar_bateria_testes():
    laudo = rodar_testes_e_obter_relatorio()
    registrar_log("EXECUCAO_SUITE_TESTES", "SISTEMA", "TESTES", 
                  f"Bateria de testes executada: {laudo['total_testes']} testes, {laudo['erros']} erros, {laudo['falhas']} falhas. Sucesso: {laudo['sucesso']}")
    return laudo

# Monta frontend
frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend")
app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
