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

import re
import base64
import hmac
import time
import json
import httpx
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Request, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, Response
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

@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response

# Chave criptográfica para assinatura de Tokens JWT do Processo Eleitoral COMARA
COMARA_JWT_SECRET = os.getenv("COMARA_JWT_SECRET", "COMARA_SECRET_KEY_PROCESSO_ELEITORAL_2026_FAB_SIGILO_ESTRITO")
ACTIVE_DIRECTORY_DOMAIN = "comara.intraer"

def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode('utf-8').rstrip('=')

def _b64decode(s: str) -> bytes:
    padding = '=' * (4 - len(s) % 4)
    return base64.urlsafe_b64decode(s + padding)

def criar_token_jwt(payload: dict, expires_in_seconds: int = 86400) -> str:
    """Gera um token JWT padrão assinado com HMAC-SHA256 e expiração."""
    header = {"alg": "HS256", "typ": "JWT"}
    payload_copy = payload.copy()
    now = int(time.time())
    payload_copy["iat"] = now
    payload_copy["exp"] = now + expires_in_seconds
    
    header_b64 = _b64encode(json.dumps(header, separators=(',', ':')).encode('utf-8'))
    payload_b64 = _b64encode(json.dumps(payload_copy, separators=(',', ':')).encode('utf-8'))
    
    signing_input = f"{header_b64}.{payload_b64}".encode('utf-8')
    signature = hmac.new(COMARA_JWT_SECRET.encode('utf-8'), signing_input, hashlib.sha256).digest()
    sig_b64 = _b64encode(signature)
    
    return f"{header_b64}.{payload_b64}.{sig_b64}"

def decodificar_token_jwt(token: str) -> Optional[dict]:
    """Valida a assinatura criptográfica, formato e expiração do JWT com comparação em tempo constante."""
    try:
        parts = token.strip().split('.')
        if len(parts) != 3:
            return None
        header_b64, payload_b64, sig_b64 = parts
        signing_input = f"{header_b64}.{payload_b64}".encode('utf-8')
        expected_sig = hmac.new(COMARA_JWT_SECRET.encode('utf-8'), signing_input, hashlib.sha256).digest()
        provided_sig = _b64decode(sig_b64)
        if not hmac.compare_digest(expected_sig, provided_sig):
            return None
        payload = json.loads(_b64decode(payload_b64).decode('utf-8'))
        if "exp" in payload and payload["exp"] < time.time():
            return None
        return payload
    except Exception:
        return None

def obter_usuario_autenticado(authorization: Optional[str] = Header(None)) -> Optional[dict]:
    """Extrai e autentica o usuário a partir do cabeçalho HTTP Authorization (Bearer token)."""
    if not authorization:
        return None
    token = authorization.strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    
    payload = decodificar_token_jwt(token)
    if not payload or "sub" not in payload:
        return None
        
    username = str(payload["sub"])
    papel = payload.get("papel", "USUARIO_COMUM")
    
    conn = get_db_connection()
    c = conn.cursor()
    digitos = re.sub(r"\D", "", username)
    c.execute("""
    SELECT id, ldap_username, nome_completo, identificador, papel, divisao, secao, status, ativo
    FROM usuarios_ldap
    WHERE (LOWER(ldap_username) = ? 
        OR identificador = ? 
        OR (? != '' AND REPLACE(REPLACE(REPLACE(identificador, '.', ''), '-', ''), ' ', '') = ?))
      AND ativo = 1 AND status = 'ATIVO'
    LIMIT 1
    """, (username.lower(), username, digitos, digitos))
    row = c.fetchone()
    conn.close()
    
    if row:
        return dict(row)
        
    return None

def exigir_autenticacao(user: Optional[dict] = Depends(obter_usuario_autenticado)) -> dict:
    """Garante que a requisição contenha um token JWT válido de usuário ativo."""
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Sessão não autenticada ou token expirado. Efetue login novamente."
        )
    return user

def exigir_papeis(papeis_permitidos: List[str]):
    """Garante que o usuário autenticado possua um dos papéis de acesso autorizados."""
    def validador(user: dict = Depends(exigir_autenticacao)):
        if user["papel"] not in papeis_permitidos:
            raise HTTPException(
                status_code=403,
                detail=f"Acesso negado: Perfil '{user['papel']}' não possui permissão para esta operação. Perfis autorizados: {', '.join(papeis_permitidos)}"
            )
        return user
    return validador

# Configurações do serviço de Fotos (SIGPES / Cache Local / Fallback SVG)
SIGPES_API_HOMOLOG = os.getenv("SIGPES_API_HOMOLOG", "http://api.servicos.homolog.ccarj.intraer/sigpesApi")
SIGPES_API_PROD = os.getenv("SIGPES_API_PROD", "http://api.servicos.ccarj.intraer/sigpesApi")
CACHE_FOTOS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "cache_fotos"))
MANUAL_FOTOS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "fotos"))
os.makedirs(CACHE_FOTOS_DIR, exist_ok=True)
os.makedirs(MANUAL_FOTOS_DIR, exist_ok=True)

def gerar_avatar_svg(nome: str = "", tipo: str = "MILITAR", subtexto: str = "") -> str:
    """Gera um avatar vetorial elegante no padrão visual da FAB/COMARA para fotos indisponíveis."""
    iniciais = "".join([part[0] for part in nome.split() if part][:2]).upper() or ("MIL" if tipo == "MILITAR" else "CIV")
    cor_bg1 = "#002855" if tipo == "MILITAR" else "#1e293b"
    cor_bg2 = "#004f9f" if tipo == "MILITAR" else "#334155"
    titulo = "COMARA" if tipo == "MILITAR" else "SERVIDOR CIVIL"
    sub = subtexto or ("MILITAR" if tipo == "MILITAR" else "CIVIL")
    
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 150 200" width="150" height="200">
  <defs>
    <linearGradient id="bgGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="{cor_bg1}" />
      <stop offset="100%" stop-color="{cor_bg2}" />
    </linearGradient>
  </defs>
  <rect width="150" height="200" fill="url(#bgGrad)" rx="6"/>
  <rect x="4" y="4" width="142" height="192" fill="none" stroke="rgba(255,255,255,0.15)" stroke-width="1.5" rx="4"/>
  <g fill="rgba(255, 255, 255, 0.22)" transform="translate(0, 5)">
    <circle cx="75" cy="72" r="28" />
    <path d="M 32 145 C 32 112, 52 104, 75 104 C 98 104, 118 112, 118 145 L 118 160 L 32 160 Z" />
    <polygon points="75,108 67,126 75,138 83,126" fill="rgba(212, 175, 55, 0.45)" />
  </g>
  <circle cx="75" cy="72" r="24" fill="rgba(255,255,255,0.12)" stroke="rgba(212,175,55,0.6)" stroke-width="1.5"/>
  <text x="75" y="79" font-family="'Segoe UI', Roboto, sans-serif" font-size="16" font-weight="bold" fill="#f8fafc" text-anchor="middle">{iniciais}</text>
  <rect x="4" y="162" width="142" height="34" fill="rgba(0, 0, 0, 0.35)" />
  <text x="75" y="176" font-family="'Segoe UI', Roboto, sans-serif" font-size="9" font-weight="bold" fill="#d4af37" text-anchor="middle" letter-spacing="1">{titulo}</text>
  <text x="75" y="188" font-family="'Segoe UI', Roboto, sans-serif" font-size="8" fill="#94a3b8" text-anchor="middle">{sub}</text>
</svg>"""

def normalizar_divisao(div: Optional[str]) -> Optional[str]:
    """Garante compatibilidade caso ainda venha a sigla descontinuada VP."""
    if not div:
        return div
    d = div.strip()
    if d.upper() in ["VP", "VICE-PRESIDÊNCIA", "VICE-PRESIDENCIA"]:
        return "PRESIDENCIA"
    return d

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

# ----------------- SERVIÇO DE FOTOS (SIGPES / CACHE / FALLBACK) -----------------

@app.get("/api/foto/{identificador}")
async def obter_foto_integrante(identificador: str, saram: Optional[str] = None, nome: Optional[str] = None, tipo: Optional[str] = None):
    """
    Recupera a foto oficial do integrante indicado.
    1. Resolve o integrante na base de dados (efetivo) se identificador for ID ou SARAM/CPF.
    2. Tenta carregar de data/fotos/ (fotos customizadas locais) ou data/cache_fotos/.
    3. Consulta a API SIGPES homolog (http://api.servicos.homolog.ccarj.intraer/sigpesApi/fotoes/{saram_7}):
       - Se for SARAM (5 a 8 dígitos), formata para 7 dígitos com zero à esquerda (ex.: 0804460).
       - Se for CPF (11 dígitos), consulta /pesfisComgeps/search/findByNrCpf para obter o nrOrdem do militar/civil.
       - Decodifica base64 da foto e armazena em cache local para consultas subsequentes instantâneas.
    4. Se for civil sem foto no SIGPES ou ocorrer falha de rede, gera e retorna avatar vetorial SVG oficial da FAB/COMARA.
    """
    alvo = (saram or identificador or "").strip()
    if not alvo or ".." in alvo or "/" in alvo or "\\" in alvo:
        raise HTTPException(status_code=400, detail="Identificador inválido.")

    # 1. Tentar resolver dados oficiais na tabela efetivo (por id numérico ou identificador)
    nome_candidato = nome or ""
    tipo_candidato = (tipo or "").upper()
    identificador_oficial = alvo
    
    try:
        conn = get_db_connection()
        c = conn.cursor()
        row_ef = None
        if alvo.isdigit():
            c.execute("SELECT * FROM efetivo WHERE id = ? LIMIT 1", (int(alvo),))
            row_ef = c.fetchone()
        if not row_ef:
            c.execute("""
            SELECT * FROM efetivo 
            WHERE identificador = ? 
               OR REPLACE(REPLACE(REPLACE(identificador, '.', ''), '-', ''), ' ', '') = ?
            LIMIT 1
            """, (alvo, re.sub(r"\D", "", alvo) or alvo))
            row_ef = c.fetchone()
        conn.close()

        if row_ef:
            identificador_oficial = row_ef["identificador"] or alvo
            nome_candidato = nome_candidato or row_ef["nome_guerra"] or row_ef["nome"]
            tipo_candidato = tipo_candidato or row_ef["tipo"]
    except Exception:
        pass

    digitos = re.sub(r"\D", "", identificador_oficial)
    alvo_seguro = re.sub(r"[^\w\.\-]", "", identificador_oficial)
    saram_7 = digitos.zfill(7) if (digitos and len(digitos) <= 7) else ""

    # 2. Verificar fotos manuais em data/fotos/
    chaves_busca = [k for k in [saram_7, digitos, alvo_seguro, alvo] if k]
    for ext in ["jpg", "jpeg", "png", "webp"]:
        for k in chaves_busca:
            path_manual = os.path.abspath(os.path.join(MANUAL_FOTOS_DIR, f"{k}.{ext}"))
            if path_manual.startswith(MANUAL_FOTOS_DIR) and os.path.exists(path_manual):
                mime = "image/png" if ext == "png" else "image/jpeg"
                return FileResponse(path_manual, media_type=mime, headers={"Cache-Control": "public, max-age=86400"})

    # 3. Verificar cache em disco data/cache_fotos/
    for k in chaves_busca:
        cache_file = os.path.join(CACHE_FOTOS_DIR, f"{k}.jpg")
        if os.path.exists(cache_file):
            return FileResponse(cache_file, media_type="image/jpeg", headers={"Cache-Control": "public, max-age=86400"})

    # 4. Consulta à API SIGPES Homolog (ccarj.intraer/sigpesApi)
    nr_ordem_alvo = None
    if digitos:
        if len(digitos) == 11:
            # CPF: busca nrOrdem via pesfisComgeps
            try:
                async with httpx.AsyncClient(timeout=4.0, follow_redirects=True) as client:
                    resp_cpf = await client.get(f"{SIGPES_API_HOMOLOG}/pesfisComgeps/search/findByNrCpf?nrCpf={digitos}")
                    if 200 <= resp_cpf.status_code < 300:
                        data_cpf = resp_cpf.json()
                        embedded = data_cpf.get("_embedded", {}).get("pesfisComgeps", [])
                        if embedded and embedded[0].get("nrOrdem"):
                            nr_ordem_alvo = str(embedded[0]["nrOrdem"]).strip().zfill(7)
            except Exception:
                pass
        elif len(digitos) <= 8:
            nr_ordem_alvo = digitos.zfill(7)

    if nr_ordem_alvo:
        urls = [
            f"{SIGPES_API_HOMOLOG}/fotoes/{nr_ordem_alvo}",
        ]
        if nr_ordem_alvo != digitos and len(digitos) >= 5:
            urls.append(f"{SIGPES_API_HOMOLOG}/fotoes/{digitos}")

        for url in urls:
            try:
                async with httpx.AsyncClient(timeout=6.0, follow_redirects=True) as client:
                    resp = await client.get(url)
                    if 200 <= resp.status_code < 300:
                        data = resp.json()
                        base64_str = None
                        if "_embedded" in data and "fotoes" in data["_embedded"] and len(data["_embedded"]["fotoes"]) > 0:
                            base64_str = data["_embedded"]["fotoes"][0].get("imFoto")
                        elif "imFoto" in data:
                            base64_str = data.get("imFoto")

                        if base64_str:
                            if "," in base64_str:
                                base64_str = base64_str.split(",", 1)[1]
                            base64_str = base64_str.strip().replace("\n", "").replace("\r", "")
                            foto_bytes = base64.b64decode(base64_str)
                            
                            for k in set([nr_ordem_alvo, digitos, saram_7]):
                                if k:
                                    cpath = os.path.join(CACHE_FOTOS_DIR, f"{k}.jpg")
                                    with open(cpath, "wb") as f:
                                        f.write(foto_bytes)

                            mime_type = data.get("tpArq") or "image/jpeg"
                            return Response(
                                content=foto_bytes,
                                media_type=mime_type,
                                headers={"Cache-Control": "public, max-age=86400"}
                            )
            except Exception:
                pass

    # 5. Fallback: Avatar vetorial oficial FAB/COMARA
    sub = f"ID {identificador_oficial}" if identificador_oficial else "COMARA"
    svg_avatar = gerar_avatar_svg(
        nome=nome_candidato or "INTEGRANTE",
        tipo=tipo_candidato or "MILITAR",
        subtexto=sub
    )
    return Response(content=svg_avatar, media_type="image/svg+xml", headers={"Cache-Control": "public, max-age=3600"})

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
    
    div_norm = normalizar_divisao(dados.divisao)

    conn = get_db_connection()
    c = conn.cursor()
    
    # 1. Atualizar ou inserir no efetivo
    c.execute("""
    INSERT OR REPLACE INTO efetivo (nome, nome_guerra, identificador, tipo, posto_grad_cargo, categoria, divisao, secao, tempo_comara_meses)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (dados.nome_completo.strip(), dados.nome_guerra.strip(), dados.identificador.strip(),
          dados.tipo.strip().upper(), dados.posto_grad_cargo.strip(), dados.categoria,
          div_norm, dados.secao.strip(), dados.tempo_comara_meses))
          
    # 2. Inserir na fila de usuários LDAP com status PENDENTE_DPTI
    try:
        c.execute("""
        INSERT INTO usuarios_ldap (ldap_username, nome_completo, identificador, papel, divisao, secao, status, senha_hash, criado_em, ativo)
        VALUES (?, ?, ?, 'USUARIO_COMUM', ?, ?, 'PENDENTE_DPTI', ?, ?, 1)
        """, (username, dados.nome_completo.strip(), dados.identificador.strip(),
              div_norm, dados.secao.strip(), shash, agora))
        conn.commit()
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=400, detail=f"O login LDAP '{username}' ou identificador já possui cadastro pendente ou ativo no sistema.")

    conn.close()
    registrar_log("AUTO_CADASTRO_SUBMETIDO", username, div_norm, 
                  f"Auto-cadastro efetuado para {dados.posto_grad_cargo} {dados.nome_guerra}. Aguardando liberação na DPTI.")

    return {
        "sucesso": True,
        "mensagem": "Cadastro realizado com sucesso! Para começar a utilizar o sistema, compareça à DPTI para vincular sua conta de rede (LDAP) e liberar seu acesso."
    }

@app.get("/api/admin/dpti-fila")
def listar_fila_dpti(admin_user: dict = Depends(exigir_papeis(["ADMINISTRADOR"]))):
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
        div_norm = normalizar_divisao(divisao)
        query += " AND divisao = ?"
        params.append(div_norm)
    if categoria:
        query += " AND categoria = ?"
        params.append(categoria)
    query += " ORDER BY divisao, secao, categoria, posto_grad_cargo"
    c.execute(query, params)
    registros = [dict(r) for r in c.fetchall()]
    conn.close()
    return registros

@app.post("/api/admin/dpti-liberar")
def liberar_cadastro_dpti(dados: DptiLiberarInput, admin_user: dict = Depends(exigir_papeis(["ADMINISTRADOR"]))):
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

    div_norm = normalizar_divisao(dados.divisao)
    agora = datetime.now().isoformat()
    admin_op = admin_user["ldap_username"]
    c.execute("""
    UPDATE usuarios_ldap
    SET ldap_username = ?, papel = ?, divisao = ?, secao = ?, status = 'ATIVO', 
        vinculado_por = ?, vinculado_em = ?
    WHERE id = ?
    """, (dados.ldap_username.strip().lower(), dados.papel, div_norm, dados.secao,
          admin_op, agora, dados.usuario_id))
    conn.commit()
    conn.close()

    registrar_log("DPTI_LIBERACAO_CONTA", admin_op, div_norm,
                  f"Conta ID {dados.usuario_id} liberada. LDAP: '{dados.ldap_username}', Papel: '{dados.papel}'")

    return {
        "sucesso": True,
        "mensagem": f"Cadastro liberado com sucesso pela DPTI! O usuário '{dados.ldap_username}' agora está ativo como {dados.papel}."
    }

# ----------------- 2. GESTÃO DO EFETIVO (ADMINISTRADOR) -----------------

@app.post("/api/admin/efetivo/limpar")
def limpar_efetivo(admin_user: dict = Depends(exigir_papeis(["ADMINISTRADOR"]))):
    """
    Limpa todo o efetivo cadastrado e zera as tabelas eleitorais vinculadas para o ano corrente.
    A conta admin.dpti permanece preservada.
    """
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM efetivo")
    c.execute("DELETE FROM indicacoes_fase1_secao")
    c.execute("DELETE FROM indicacoes_fase2_divisao")
    c.execute("DELETE FROM vetos_fase3")
    c.execute("DELETE FROM votos_fase4")
    c.execute("DELETE FROM eleitores_votaram")
    c.execute("DELETE FROM decisao_fase5_comando")
    conn.commit()
    conn.close()

    registrar_log("ADMIN_LIMPAR_EFETIVO", admin_user["ldap_username"], "DPTI", 
                  "Efetivo da COMARA e registros eleitorais associados zerados pelo Administrador para o ano corrente.")

    return {
        "sucesso": True,
        "mensagem": "Efetivo da COMARA e registros eleitorais associados limpos com sucesso! O sistema está pronto para receber o novo efetivo."
    }

@app.post("/api/admin/efetivo/upload")
async def upload_efetivo(arquivo: UploadFile = File(...), admin_user: dict = Depends(exigir_papeis(["ADMINISTRADOR"]))):
    """
    Importa o efetivo para o ano corrente a partir de uma planilha Excel (.xlsx/.xls) ou arquivo CSV.
    """
    ext = os.path.splitext(arquivo.filename or "")[1].lower()
    if ext not in [".xlsx", ".xls", ".csv"]:
        raise HTTPException(status_code=400, detail="Formato de arquivo inválido. Envie um arquivo Excel (.xlsx, .xls) ou CSV (.csv).")

    conteudo = await arquivo.read()
    if not conteudo:
        raise HTTPException(status_code=400, detail="Arquivo enviado está vazio.")

    linhas = []
    if ext in [".xlsx", ".xls"]:
        import io
        import openpyxl
        try:
            wb = openpyxl.load_workbook(filename=io.BytesIO(conteudo), data_only=True)
            ws = wb.active
            for row in ws.iter_rows(values_only=True):
                if any(row):
                    linhas.append([str(v).strip() if v is not None else "" for v in row])
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Erro ao processar planilha Excel: {str(e)}")
    else:
        import csv
        import io
        try:
            texto = conteudo.decode("utf-8-sig", errors="replace")
            sample = texto[:2048]
            delimiter = ";" if ";" in sample else ("," if "," in sample else "\t")
            reader = csv.reader(io.StringIO(texto), delimiter=delimiter)
            for row in reader:
                if any(row):
                    linhas.append([c.strip() for c in row])
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Erro ao processar arquivo CSV: {str(e)}")

    if len(linhas) < 2:
        raise HTTPException(status_code=400, detail="O arquivo deve conter pelo menos uma linha de cabeçalho e uma de dados.")

    # Mapeamento do cabeçalho
    header = [h.lower().replace(" ", "").replace("_", "").replace("/", "") for h in linhas[0]]
    
    def encontrar_coluna(termos: List[str]) -> int:
        for t in termos:
            t_clean = t.lower().replace(" ", "").replace("_", "").replace("/", "")
            # 1. Correspondência exata primeiro
            for i, h in enumerate(header):
                if h == t_clean:
                    return i
            # 2. Correspondência de prefixo ou sufixo
            for i, h in enumerate(header):
                if h.startswith(t_clean) or h.endswith(t_clean):
                    return i
            # 3. Substring para termos com mais de 2 letras
            if len(t_clean) > 2:
                for i, h in enumerate(header):
                    if t_clean in h:
                        return i
        return -1

    col_posto = encontrar_coluna(["postograd", "posto", "grad", "cargo"])
    col_esp = encontrar_coluna(["esp", "especialidade", "quadro"])
    col_nome = encontrar_coluna(["nomecompleto", "nome"])
    col_guerra = encontrar_coluna(["nomeguerra", "nomedeguerra", "guerra"])
    col_ident = encontrar_coluna(["saramcpf", "saram", "cpf", "identificador", "matricula", "id"])
    col_cat = encontrar_coluna(["classeeleitoral", "classe", "categoria"])
    col_div = encontrar_coluna(["divisao", "divisão", "div"])
    col_sec = encontrar_coluna(["secao", "seção", "sec", "subdivisao"])
    col_tempo = encontrar_coluna(["tempocomara", "tempo", "meses"])

    if col_nome == -1 or col_ident == -1:
        raise HTTPException(
            status_code=400,
            detail="Colunas obrigatórias não identificadas no cabeçalho. Inclua 'Nome' e 'SARAM / CPF'."
        )

    vistos_ident = {}
    registros = []
    por_categoria = {"Graduados": 0, "Pracas": 0, "Civil": 0, "Oficiais": 0}

    for idx, row in enumerate(linhas[1:], start=2):
        if not any(row):
            continue
        nome = row[col_nome].strip() if col_nome < len(row) else ""
        if not nome:
            continue
        ident = row[col_ident].strip() if col_ident < len(row) else ""
        if not ident or ident.lower() in ["none", "null", "-", "s/id"]:
            ident = f"CAD-{idx}"

        # Deduplicação garantida caso a planilha contenha identificadores repetidos
        base_ident = ident
        sufixo = 1
        while ident in vistos_ident:
            sufixo += 1
            ident = f"{base_ident}-{sufixo}"
        vistos_ident[ident] = True

        posto = row[col_posto].strip() if col_posto != -1 and col_posto < len(row) else ""
        esp = row[col_esp].strip() if col_esp != -1 and col_esp < len(row) else ""
        posto_grad_cargo = f"{posto} {esp}".strip() or "INTEGRANTE"
        
        guerra = row[col_guerra].strip() if col_guerra != -1 and col_guerra < len(row) else ""
        if not guerra:
            partes = nome.split()
            guerra = partes[-1] if partes else nome

        div = row[col_div].strip() if col_div != -1 and col_div < len(row) else "COMARA"
        div = normalizar_divisao(div) or "COMARA"
        sec = row[col_sec].strip() if col_sec != -1 and col_sec < len(row) else ""
        
        tempo_str = row[col_tempo].strip() if col_tempo != -1 and col_tempo < len(row) else "12"
        tempo_meses = int(re.sub(r"\D", "", tempo_str) or 12)

        cat = row[col_cat].strip() if col_cat != -1 and col_cat < len(row) else ""
        p_up = posto_grad_cargo.upper()
        
        if not cat:
            if any(t in p_up for t in ["SO", "SGT", "1S", "2S", "3S"]):
                cat = "Graduados"
            elif any(t in p_up for t in ["CB", "SD", "S1", "S2", "TA", "TM", "MN"]):
                cat = "Pracas"
            elif any(t in p_up for t in ["CL", "TC", "MAJ", "CP", "1T", "2T", "ASP"]):
                cat = "Oficiais"
            else:
                cat = "Civil"

        if cat not in ["Graduados", "Pracas", "Civil", "Oficiais"]:
            cat = "Graduados" if "SGT" in p_up else ("Pracas" if "SD" in p_up or "CB" in p_up else "Civil")

        tipo = "CIVIL" if (cat == "Civil" or "CIV" in p_up or "SPTF" in p_up or "SPPF" in p_up) else "MILITAR"

        if cat in por_categoria:
            por_categoria[cat] += 1

        registros.append((
            nome, guerra, ident, tipo, posto_grad_cargo, cat, div, sec, tempo_meses
        ))

    if not registros:
        raise HTTPException(status_code=400, detail="Nenhum registro válido pôde ser extraído do arquivo.")

    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM efetivo")
    c.execute("DELETE FROM indicacoes_fase1_secao")
    c.execute("DELETE FROM indicacoes_fase2_divisao")
    c.execute("DELETE FROM vetos_fase3")
    c.execute("DELETE FROM votos_fase4")
    c.execute("DELETE FROM eleitores_votaram")
    c.execute("DELETE FROM decisao_fase5_comando")

    c.executemany("""
    INSERT OR REPLACE INTO efetivo (nome, nome_guerra, identificador, tipo, posto_grad_cargo, categoria, divisao, secao, tempo_comara_meses, ativo)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
    """, registros)
    conn.commit()
    conn.close()

    total = len(registros)
    registrar_log("ADMIN_UPLOAD_EFETIVO", admin_user["ldap_username"], "DPTI",
                  f"Importação de efetivo para o ano corrente via {arquivo.filename}: {total} integrantes cadastrados.")

    return {
        "sucesso": True,
        "mensagem": f"Efetivo do ano corrente importado com sucesso! {total} integrantes cadastrados.",
        "total": total,
        "por_categoria": por_categoria
    }

@app.post("/api/admin/efetivo/restaurar-padrao")
def restaurar_efetivo_padrao(admin_user: dict = Depends(exigir_papeis(["ADMINISTRADOR"]))):
    """
    Restaura o efetivo oficial da COMARA (443 integrantes atualizados: 320 militares e 123 civis).
    """
    try:
        import importar_efetivo_oficial
        importar_efetivo_oficial.importar()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao restaurar efetivo padrão: {str(e)}")

    registrar_log("ADMIN_RESTAURAR_EFETIVO", admin_user["ldap_username"], "DPTI",
                  "Efetivo oficial da COMARA restaurado com sucesso pelo Administrador (443 integrantes).")

    return {
        "sucesso": True,
        "mensagem": "Efetivo oficial da COMARA restaurado com sucesso (443 integrantes cadastrados: 320 militares e 123 civis).",
        "total": 443
    }

# ----------------- 3. AUTENTICAÇÃO UNIFICADA (SARAM / CPF / LDAP comara.intraer) -----------------

@app.post("/api/auth/login-ldap")
def login_ldap(credenciais: LoginLdapInput):
    raw_user = (credenciais.ldap_username or "").strip()
    password = credenciais.password
    
    # 1. Validação de segurança: Senha é estritamente obrigatória
    if not password or not str(password).strip():
        raise HTTPException(
            status_code=400,
            detail="A senha é obrigatória. Não é permitido efetuar login sem senha no sistema da COMARA."
        )
    
    # Normalização de Domínio Active Directory (comara.intraer)
    username_clean = raw_user
    if username_clean.lower().endswith(f"@{ACTIVE_DIRECTORY_DOMAIN}"):
        username_clean = username_clean[:-len(f"@{ACTIVE_DIRECTORY_DOMAIN}")]
    elif username_clean.lower().startswith(f"{ACTIVE_DIRECTORY_DOMAIN}\\"):
        username_clean = username_clean[len(f"{ACTIVE_DIRECTORY_DOMAIN}\\"):]
    username_clean = username_clean.strip()
    
    digitos = re.sub(r"\D", "", raw_user)
    
    conn = get_db_connection()
    c = conn.cursor()
    
    # 2. Localiza a conta na tabela de contas de rede / credenciadas (usuarios_ldap)
    # Permite busca por login LDAP de rede (ex.: admin.dpti) ou por SARAM / CPF
    u = None
    if digitos:
        c.execute("""
        SELECT * FROM usuarios_ldap 
        WHERE REPLACE(REPLACE(REPLACE(identificador, '.', ''), '-', ''), ' ', '') = ?
           OR identificador = ?
           OR LOWER(ldap_username) = ?
        ORDER BY id DESC LIMIT 1
        """, (digitos, raw_user, username_clean.lower()))
        u = c.fetchone()
        
    if not u:
        c.execute("""
        SELECT * FROM usuarios_ldap 
        WHERE LOWER(ldap_username) = ? OR LOWER(identificador) = ?
        ORDER BY id DESC LIMIT 1
        """, (username_clean.lower(), raw_user.lower()))
        u = c.fetchone()
        
    # Se a conta não existe em usuarios_ldap, verifica se o usuário ao menos consta no efetivo da COMARA
    if not u:
        integrante = None
        if digitos:
            c.execute("""
            SELECT * FROM efetivo 
            WHERE REPLACE(REPLACE(REPLACE(identificador, '.', ''), '-', ''), ' ', '') = ?
               OR identificador = ?
            LIMIT 1
            """, (digitos, raw_user))
            integrante = c.fetchone()
        if not integrante:
            c.execute("SELECT * FROM efetivo WHERE LOWER(identificador) = ? LIMIT 1", (raw_user.lower(),))
            integrante = c.fetchone()
            
        conn.close()
        registrar_log("FALHA_LOGIN_SEM_CONTA", raw_user, None, "Tentativa de login com conta não cadastrada ou não aprovada.")
        if integrante:
            raise HTTPException(
                status_code=401,
                detail=f"Olá, {integrante['posto_grad_cargo']} {integrante['nome_guerra']}. Seu identificador consta no efetivo da COMARA, porém sua conta ainda não foi aprovada pelo Administrador na DPTI. Realize o auto-cadastro ou solicite a liberação presencial."
            )
        else:
            raise HTTPException(
                status_code=401,
                detail=f"Credenciais inválidas: Usuário '{raw_user}' não localizado no sistema ou no efetivo ativo da COMARA."
            )

    # 3. Validação rigorosa da senha com SHA-256
    shash = hash_senha(password)
    if u["senha_hash"] != shash:
        conn.close()
        registrar_log("FALHA_LOGIN_SENHA", u["ldap_username"], u["divisao"], "Tentativa de login com senha incorreta.")
        raise HTTPException(
            status_code=401,
            detail="Credenciais inválidas: Senha incorreta. Verifique os dados e tente novamente."
        )

    # 4. Validação de aprovação pelo Administrador (DPTI)
    if u["status"] == "PENDENTE_DPTI":
        conn.close()
        registrar_log("BLOQUEIO_PENDENCIA_DPTI", u["ldap_username"], u["divisao"], "Acesso negado: Conta aguarda aprovação pelo Administrador na DPTI.")
        raise HTTPException(
            status_code=403,
            detail=f"Acesso Pendente: A conta '{u['ldap_username']}' aguarda aprovação presencial pelo Administrador na DPTI para ser liberada."
        )

    if u["ativo"] != 1 or u["status"] != "ATIVO":
        conn.close()
        registrar_log("BLOQUEIO_CONTA_DESATIVADA", u["ldap_username"], u["divisao"], "Acesso negado: Conta inativa.")
        raise HTTPException(status_code=403, detail="Conta desativada ou bloqueada pelo Administrador.")

    # 5. Obter informações complementares de posto/graduação do efetivo
    c.execute("""
    SELECT posto_grad_cargo, nome_guerra, categoria FROM efetivo 
    WHERE identificador = ? OR REPLACE(REPLACE(REPLACE(identificador, '.', ''), '-', ''), ' ', '') = ?
    LIMIT 1
    """, (u["identificador"], re.sub(r"\D", "", u["identificador"]) or u["identificador"]))
    efetivo_info = c.fetchone()
    conn.close()

    registrar_log("LOGIN_SUCESSO", u["ldap_username"], u["divisao"], f"Autenticado no sistema com perfil ativo {u['papel']}.")

    token = criar_token_jwt({
        "sub": u["ldap_username"],
        "papel": u["papel"],
        "divisao": u["divisao"],
        "secao": u["secao"]
    })

    return {
        "sucesso": True,
        "token": token,
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

@app.get("/api/auth/me")
def obter_usuario_logado(auth_user: dict = Depends(exigir_autenticacao)):
    """Retorna os dados do usuário autenticado a partir do token Bearer JWT."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
    SELECT posto_grad_cargo, nome_guerra, categoria FROM efetivo 
    WHERE identificador = ? OR REPLACE(REPLACE(REPLACE(identificador, '.', ''), '-', ''), ' ', '') = ?
    LIMIT 1
    """, (auth_user["identificador"], auth_user["identificador"]))
    efetivo_info = c.fetchone()
    conn.close()
    return {
        "sucesso": True,
        "ldap_username": auth_user["ldap_username"],
        "nome_completo": auth_user["nome_completo"],
        "identificador": auth_user["identificador"],
        "papel": auth_user["papel"],
        "divisao": auth_user["divisao"],
        "secao": auth_user["secao"],
        "posto_grad_cargo": efetivo_info["posto_grad_cargo"] if efetivo_info else "",
        "nome_guerra": efetivo_info["nome_guerra"] if efetivo_info else auth_user["nome_completo"],
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
def avancar_fase_eleitoral(dados: AvancarFaseInput, auth_user: dict = Depends(exigir_papeis(["ADMINISTRADOR", "CMDT_OM"]))):
    """Avança ou altera a fase do processo eleitoral (exclusivo Admin / Comandante)."""
    if dados.nova_fase not in FASES_ORDEM:
        raise HTTPException(status_code=400, detail=f"Fase inválida. Opções: {FASES_ORDEM}")
        
    agora = datetime.now().isoformat()
    operador = auth_user["ldap_username"]
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
    INSERT INTO controle_fases (fase_atual, iniciado_em, atualizado_em, atualizado_por)
    VALUES (?, ?, ?, ?)
    """, (dados.nova_fase, agora, agora, operador))
    conn.commit()
    conn.close()

    registrar_log("FASE_AVANCADA", operador, "COMANDO", 
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
def salvar_indicacao_fase1(dados: IndicarFase1Input, auth_user: dict = Depends(exigir_papeis(["CHEFE_SECAO", "ADMINISTRADOR"]))):
    """Chefe de Seção indica 1 subordinado por classe da sua seção."""
    if auth_user["papel"] == "CHEFE_SECAO" and auth_user["secao"].upper() != dados.secao.strip().upper():
        raise HTTPException(status_code=403, detail="Você só pode registrar indicações para a sua própria seção.")

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
    operador = auth_user["ldap_username"]
    c.execute("""
    INSERT OR REPLACE INTO indicacoes_fase1_secao (secao, divisao, categoria, candidato_id, indicado_por_ldap, data_hora)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (dados.secao, cand["divisao"], dados.categoria, dados.candidato_id, operador, agora))
    conn.commit()
    conn.close()

    registrar_log("FASE1_INDICACAO_SECAO", operador, dados.secao,
                  f"Chefe indicou {cand['posto_grad_cargo']} {cand['nome_guerra']} como representante da Seção {dados.secao} na classe {dados.categoria}.")
    return {"sucesso": True, "mensagem": f"{cand['posto_grad_cargo']} {cand['nome_guerra']} indicado com sucesso pela Seção {dados.secao}."}

# ----------------- 5. FASE 2: SELEÇÃO POR CHEFES DE DIVISÃO -----------------

@app.get("/api/fase2/indicados-secoes")
def listar_indicados_secoes_divisao(divisao: str):
    """Retorna os militares e civis indicados pelas seções subordinadas à divisão."""
    div_norm = normalizar_divisao(divisao)
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
    SELECT e.id, e.nome, e.nome_guerra, e.posto_grad_cargo, e.categoria, e.divisao, e.secao, e.tempo_comara_meses,
           e.identificador, e.tipo,
           i.secao as secao_origem, i.data_hora
    FROM indicacoes_fase1_secao i
    JOIN efetivo e ON i.candidato_id = e.id
    WHERE i.divisao = ?
    ORDER BY e.categoria, e.nome_guerra
    """, (div_norm,))
    candidatos = [dict(r) for r in c.fetchall()]

    c.execute("SELECT categoria, candidato_id FROM indicacoes_fase2_divisao WHERE divisao = ?", (div_norm,))
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
        "divisao": div_norm,
        "indicados_por_categoria": agrupados,
        "selecionados_fase2": selecionados
    }

@app.post("/api/fase2/selecionar-divisao")
def salvar_selecao_fase2(dados: SelecionarFase2Input, auth_user: dict = Depends(exigir_papeis(["CHEFE_DIVISAO", "ADMINISTRADOR"]))):
    """Chefe de Divisão seleciona até 2 indicados por classe para representar a divisão."""
    div_norm = normalizar_divisao(dados.divisao)
    if auth_user["papel"] == "CHEFE_DIVISAO" and normalizar_divisao(auth_user["divisao"]) != div_norm:
        raise HTTPException(status_code=403, detail="Você só pode homologar representantes para a sua própria divisão.")

    if len(dados.candidato_ids) > 2:
        raise HTTPException(status_code=400, detail="O Chefe de Divisão pode selecionar no máximo 2 candidatos por categoria.")

    operador = auth_user["ldap_username"]
    conn = get_db_connection()
    c = conn.cursor()
    
    # Remove seleções anteriores da divisão nessa categoria
    c.execute("DELETE FROM indicacoes_fase2_divisao WHERE divisao = ? AND categoria = ?", (div_norm, dados.categoria))
    
    agora = datetime.now().isoformat()
    for cid in dados.candidato_ids:
        c.execute("""
        INSERT INTO indicacoes_fase2_divisao (divisao, categoria, candidato_id, indicado_por_ldap, data_hora)
        VALUES (?, ?, ?, ?, ?)
        """, (div_norm, dados.categoria, cid, operador, agora))
        
    conn.commit()
    conn.close()

    registrar_log("FASE2_SELECAO_DIVISAO", operador, div_norm,
                  f"Chefe de Divisão selecionou {len(dados.candidato_ids)} candidatos na categoria {dados.categoria}.")
    return {"sucesso": True, "mensagem": f"{len(dados.candidato_ids)} representantes da Divisão {div_norm} homologados para a Fase 3."}

# ----------------- 6. FASE 3: RODADA DE VETO PELOS CHEFES DE DIVISÃO -----------------

@app.get("/api/fase3/candidatos-veto")
def listar_candidatos_para_veto(chefe_ldap: Optional[str] = None):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
    SELECT DISTINCT e.id, e.nome, e.nome_guerra, e.posto_grad_cargo, e.categoria, e.divisao, e.secao, e.tempo_comara_meses, e.identificador, e.tipo
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
def votar_veto_fase3(dados: VotarVetoFase3Input, auth_user: dict = Depends(exigir_papeis(["CHEFE_DIVISAO", "ADMINISTRADOR"]))):
    operador = auth_user["ldap_username"]
    agora = datetime.now().isoformat()
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
    INSERT OR REPLACE INTO vetos_fase3 (candidato_id, chefe_divisao_ldap, voto_veto, data_hora)
    VALUES (?, ?, ?, ?)
    """, (dados.candidato_id, operador, dados.voto_veto, agora))
    conn.commit()
    conn.close()

    acao = "VETOU" if dados.voto_veto == 1 else "NÃO VETOU (Aprovou)"
    registrar_log("FASE3_VOTO_VETO", operador, auth_user.get("divisao"), f"Chefe {operador} {acao} o candidato ID {dados.candidato_id}.")
    return {"sucesso": True, "mensagem": f"Voto de veto ({acao}) registrado com sucesso."}

# ----------------- 7. FASE 4: VOTAÇÃO GERAL POR CLIQUE (SEM NOTAS) -----------------

@app.get("/api/fase4/cedula-geral")
def obter_cedula_fase4():
    """Retorna candidatos aprovados na Fase 3 para votação por clique simples."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
    SELECT DISTINCT e.id, e.nome, e.nome_guerra, e.posto_grad_cargo, e.categoria, e.divisao, e.secao, e.tempo_comara_meses, e.identificador, e.tipo
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
def registrar_voto_fase4(dados: VotoGeralFase4Input, auth_user: dict = Depends(exigir_autenticacao)):
    """
    Computa o voto individual por clique (sem atribuição de notas!).
    Segurança Reforçada:
    - Exige autenticação prévia (token Bearer JWT) de conta aprovada.
    - O eleitor que está votando é estritamente o usuário autenticado (auth_user['identificador']).
    - Tentativa de enviar identificador de terceiros é bloqueada com HTTP 403.
    """
    eleitor_identificador = auth_user["identificador"]
    
    # Impedir qualquer tentativa de personificação de outro eleitor
    if dados.identificador:
        dados_ident_limpo = re.sub(r"\D", "", dados.identificador) or dados.identificador.strip().lower()
        auth_ident_limpo = re.sub(r"\D", "", eleitor_identificador) or eleitor_identificador.strip().lower()
        if dados_ident_limpo != auth_ident_limpo and dados.identificador.strip().lower() != eleitor_identificador.strip().lower():
            registrar_log("TENTATIVA_IMPERSONACAO_VOTO", auth_user["ldap_username"], auth_user["divisao"],
                          f"Tentativa de votar com identificador de terceiros ({dados.identificador}) bloqueada.")
            raise HTTPException(
                status_code=403,
                detail="Violação de segurança: Você só pode votar em seu próprio nome e SARAM/CPF autenticado. Voto em nome de terceiros é estritamente proibido."
            )

    conn = get_db_connection()
    c = conn.cursor()
    
    digitos = re.sub(r"\D", "", eleitor_identificador)
    c.execute("""
    SELECT id, nome, identificador, divisao FROM efetivo 
    WHERE (identificador = ? OR ( ? != '' AND REPLACE(REPLACE(REPLACE(identificador, '.', ''), '-', ''), ' ', '') = ? ))
      AND ativo = 1
    LIMIT 1
    """, (eleitor_identificador, digitos, digitos))
    eleitor = c.fetchone()
    if not eleitor:
        conn.close()
        raise HTTPException(status_code=403, detail="O usuário autenticado não consta no efetivo ativo de votantes da COMARA.")
        
    voter_hash = gerar_hash_eleitor(eleitor["identificador"])
    c.execute("SELECT voter_hash FROM eleitores_votaram WHERE voter_hash = ?", (voter_hash,))
    if c.fetchone():
        conn.close()
        registrar_log("BLOQUEIO_VOTO_DUPLICADO", auth_user["ldap_username"], eleitor["divisao"], "Tentativa de re-votação bloqueada.")
        raise HTTPException(status_code=400, detail="Voto já computado para o seu usuário nesta eleição. Cada eleitor só pode votar uma única vez.")

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
        INSERT INTO eleitores_votaram (voter_hash, identificador_mascarado, data_hora, efetivo_id)
        VALUES (?, ?, ?, ?)
        """, (voter_hash, mascara, agora, eleitor["id"]))
        conn.commit()
    except Exception as e:
        conn.rollback()
        conn.close()
        raise HTTPException(status_code=500, detail=f"Erro ao gravar voto: {str(e)}")
        
    conn.close()
    registrar_log("FASE4_VOTO_COMPUTADO", auth_user["ldap_username"], eleitor["divisao"], f"Voto computado com sucesso pelo eleitor autenticado. Comprovante: {voter_hash[:12]}")
    return {
        "sucesso": True,
        "mensagem": "Voto computado com sucesso!",
        "comprovante_hash": voter_hash[:16].upper(),
        "data_hora": agora
    }

@app.get("/api/fase4/painel-votantes")
def obter_painel_votantes(
    divisao: Optional[str] = None,
    status: Optional[str] = None,
    busca: Optional[str] = None,
    authorization: Optional[str] = Header(None),
    ldap_username: Optional[str] = None
):
    """
    Painel de Acompanhamento Eleitoral e Quórum de Votação.
    Exclusivo para: Presidente da OM (CMDT_OM), Administrador (ADMINISTRADOR) e Chefes de Divisão (CHEFE_DIVISAO).
    Exibe quem já votou, quem ainda não votou e as porcentagens globais, por divisão e por categoria.
    O sigilo do voto é estritamente preservado: nenhum voto individual é associado ao candidato escolhido.
    """
    papeis_permitidos = ["ADMINISTRADOR", "CMDT_OM", "CHEFE_DIVISAO"]
    
    # 1. Validação de autenticação via Token JWT Bearer
    user_autenticado = obter_usuario_autenticado(authorization)
    if user_autenticado:
        if user_autenticado["papel"] not in papeis_permitidos:
            raise HTTPException(
                status_code=403,
                detail="Acesso restrito: Apenas o Presidente da COMARA, Administrador e Chefes de Divisão possuem permissão para visualizar o quórum e a lista de votantes."
            )
    elif ldap_username:
        conn_auth = get_db_connection()
        c_auth = conn_auth.cursor()
        c_auth.execute("SELECT papel, status, ativo FROM usuarios_ldap WHERE LOWER(ldap_username) = ? AND ativo = 1", (ldap_username.strip().lower(),))
        u = c_auth.fetchone()
        conn_auth.close()
        if not u or u["papel"] not in papeis_permitidos or u["status"] != "ATIVO":
            raise HTTPException(
                status_code=403,
                detail="Acesso restrito: Apenas o Presidente da COMARA, Administrador e Chefes de Divisão possuem permissão para visualizar o quórum e a lista de votantes."
            )
    else:
        raise HTTPException(
            status_code=401,
            detail="Acesso restrito: Autenticação obrigatória para visualização do quórum eleitoral."
        )

    if divisao:
        divisao = normalizar_divisao(divisao)
    conn = get_db_connection()
    c = conn.cursor()
    
    # 1. Obter todo o efetivo ativo
    c.execute("""
    SELECT id, nome, nome_guerra, identificador, tipo, posto_grad_cargo, categoria, divisao, secao
    FROM efetivo
    WHERE ativo = 1
    ORDER BY divisao, secao, categoria, posto_grad_cargo, nome_guerra
    """)
    efetivo_rows = [dict(r) for r in c.fetchall()]
    
    # 2. Obter registros de eleitores que já votaram
    c.execute("SELECT voter_hash, data_hora, efetivo_id FROM eleitores_votaram")
    votos_registrados = c.fetchall()
    conn.close()
    
    votaram_por_id = {}
    votaram_por_hash = {}
    for r in votos_registrados:
        if r["efetivo_id"]:
            votaram_por_id[r["efetivo_id"]] = r["data_hora"]
        if r["voter_hash"]:
            votaram_por_hash[r["voter_hash"]] = r["data_hora"]
            
    total_geral = len(efetivo_rows)
    total_votaram = 0
    
    por_divisao = {}
    por_categoria = {
        "Graduados": {"total": 0, "votaram": 0, "percentual": 0.0},
        "Pracas": {"total": 0, "votaram": 0, "percentual": 0.0},
        "Civil": {"total": 0, "votaram": 0, "percentual": 0.0}
    }
    
    eleitores_processados = []
    
    for m in efetivo_rows:
        m_id = m["id"]
        m_ident = m["identificador"]
        m_hash = gerar_hash_eleitor(m_ident)
        
        data_voto = votaram_por_id.get(m_id) or votaram_por_hash.get(m_hash)
        ja_votou = (data_voto is not None)
        if ja_votou:
            total_votaram += 1
            
        div = m["divisao"]
        if div not in por_divisao:
            por_divisao[div] = {"divisao": div, "total": 0, "votaram": 0, "percentual": 0.0}
        por_divisao[div]["total"] += 1
        if ja_votou:
            por_divisao[div]["votaram"] += 1
            
        cat = m["categoria"]
        if cat in por_categoria:
            por_categoria[cat]["total"] += 1
            if ja_votou:
                por_categoria[cat]["votaram"] += 1
                
        eleitor_info = {
            "id": m_id,
            "nome": m["nome"],
            "nome_guerra": m["nome_guerra"],
            "identificador": m_ident,
            "tipo": m["tipo"],
            "posto_grad_cargo": m["posto_grad_cargo"],
            "categoria": cat,
            "divisao": div,
            "secao": m["secao"],
            "votou": ja_votou,
            "data_hora_voto": data_voto
        }
        
        # Filtros opcionais
        if divisao and div.upper() != divisao.upper():
            continue
        if status:
            if status.lower() == "votou" and not ja_votou:
                continue
            if status.lower() == "pendente" and ja_votou:
                continue
        if busca:
            termo = busca.strip().lower()
            texto_busca = f"{m['nome']} {m['nome_guerra']} {m['identificador']} {m['posto_grad_cargo']} {m['divisao']} {m['secao']}".lower()
            if termo not in texto_busca:
                continue
                
        eleitores_processados.append(eleitor_info)
        
    total_pendentes = total_geral - total_votaram
    percentual_geral = round((total_votaram / total_geral * 100), 1) if total_geral > 0 else 0.0
    percentual_pendentes = round((total_pendentes / total_geral * 100), 1) if total_geral > 0 else 0.0
    
    divisoes_lista = []
    for div_key, div_dados in por_divisao.items():
        pct = round((div_dados["votaram"] / div_dados["total"] * 100), 1) if div_dados["total"] > 0 else 0.0
        div_dados["percentual"] = pct
        divisoes_lista.append(div_dados)
    divisoes_lista.sort(key=lambda x: x["divisao"])
    
    for cat_key in por_categoria:
        t = por_categoria[cat_key]["total"]
        v = por_categoria[cat_key]["votaram"]
        por_categoria[cat_key]["percentual"] = round((v / t * 100), 1) if t > 0 else 0.0
        
    return {
        "resumo": {
            "total_efetivo": total_geral,
            "total_votaram": total_votaram,
            "total_pendentes": total_pendentes,
            "percentual_votaram": percentual_geral,
            "percentual_pendentes": percentual_pendentes,
            "por_divisao": divisoes_lista,
            "por_categoria": por_categoria
        },
        "eleitores": eleitores_processados
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
    SELECT DISTINCT e.id, e.nome, e.nome_guerra, e.posto_grad_cargo, e.categoria, e.divisao, e.secao, e.tempo_comara_meses, e.identificador, e.tipo
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
def salvar_decisao_comandante(dados: DecisaoComandoFase5Input, auth_user: dict = Depends(exigir_papeis(["CMDT_OM", "ADMINISTRADOR"]))):
    """
    O Presidente da COMARA decide:
    - Se a favor: homologa o mais votado da classe.
    - Se contra: indica diretamente quem ele quer que seja o ganhador!
    """
    operador = auth_user["ldap_username"]
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
        """, (agora, agora, operador))

    conn.commit()
    conn.close()

    tipo_decisao = "HOMOLOGOU O MAIS VOTADO" if dados.acao_comando == "HOMOLOGADO_ELEITO" else f"INDICOU DIRETAMENTE O GANHADOR (ID {dados.candidato_final_id})"
    registrar_log("DECISAO_COMANDANTE_REGISTRADA", operador, "COMANDO", 
                  f"Presidente da COMARA deliberou na classe {dados.categoria}: {tipo_decisao}.")

    return {
        "sucesso": True,
        "mensagem": f"Decisão do Presidente da COMARA para a classe '{NOMES_CLASSES[dados.categoria]}' formalizada com sucesso!",
        "assinatura_digital": sig_hash
    }

# ----------------- 9. AUDITORIA E TESTES -----------------

@app.get("/api/auditoria/logs")
def listar_logs_auditoria(limite: int = 50, auth_user: dict = Depends(exigir_papeis(["ADMINISTRADOR", "CMDT_OM"]))):
    return obter_logs(limite)

@app.post("/api/testes/executar")
def executar_bateria_testes(auth_user: dict = Depends(exigir_papeis(["ADMINISTRADOR"]))):
    laudo = rodar_testes_e_obter_relatorio()
    registrar_log("EXECUCAO_SUITE_TESTES", auth_user["ldap_username"], "TESTES", 
                  f"Bateria de testes executada: {laudo['total_testes']} testes, {laudo['erros']} erros, {laudo['falhas']} falhas. Sucesso: {laudo['sucesso']}")
    return laudo

# Monta frontend
frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend")
app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
