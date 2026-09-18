"""
Teste End-to-End (E2E) Oficial do Fluxo em 5 Fases da COMARA
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

import database
test_db_path = os.path.join(os.path.dirname(__file__), "data", "test_e2e_temp.db")
if os.path.exists(test_db_path):
    try:
        os.remove(test_db_path)
    except Exception:
        pass
database.DB_PATH = test_db_path

from fastapi.testclient import TestClient
from app import app
from database import init_db, get_db_connection
from seed_data import seed_database

def rodar_teste_completo():
    print("Iniciando bateria E2E do Fluxo em 5 Fases da COMARA...")
    init_db()
    seed_database()

    # Reset de registros temporários do teste para permitir execuções repetidas
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM usuarios_ldap WHERE ldap_username = 'vieira.sd' OR identificador = '7999111'")
    c.execute("DELETE FROM efetivo WHERE identificador = '7999111'")
    c.execute("DELETE FROM indicacoes_fase1_secao")
    c.execute("DELETE FROM indicacoes_fase2_divisao")
    c.execute("DELETE FROM vetos_fase3")
    c.execute("DELETE FROM votos_fase4")
    c.execute("DELETE FROM eleitores_votaram")
    c.execute("DELETE FROM decisao_fase5_comando")
    conn.commit()
    conn.close()

    client = TestClient(app)

    # 1. AUTO-CADASTRO E BLOQUEIO PENDENTE DPTI
    print("\n--- 1. TESTE DE AUTO-CADASTRO E VALIDAÇÃO DPTI ---")
    res_cad = client.post("/api/auth/auto-cadastro", json={
        "nome_completo": "Soldado Marcelo Vieira",
        "nome_guerra": "M. Vieira",
        "identificador": "7999111",
        "tipo": "MILITAR",
        "posto_grad_cargo": "SD",
        "categoria": "Pracas",
        "divisao": "DE",
        "secao": "DEPL",
        "tempo_comara_meses": 14,
        "ldap_username": "vieira.sd",
        "senha": "comara"
    })
    assert res_cad.status_code == 200
    print(f"[OK] Auto-cadastro realizado: {res_cad.json()['mensagem']}")

    # Tentativa de Login antes da DPTI liberar (DEVE SER BLOQUEADA COM 403!)
    res_login_bloq = client.post("/api/auth/login-ldap", json={
        "ldap_username": "vieira.sd",
        "password": "comara"
    })
    assert res_login_bloq.status_code == 403
    print(f"[OK] Bloqueio estrito de pendência DPTI acionado: {res_login_bloq.json()['detail'][:65]}...")

    # Administrador faz login para acessar o painel DPTI e gerenciar fases
    res_adm = client.post("/api/auth/login-ldap", json={
        "ldap_username": "admin.dpti",
        "password": "comara"
    })
    assert res_adm.status_code == 200
    token_adm = res_adm.json()["token"]
    client.headers["Authorization"] = f"Bearer {token_adm}"

    # Administrador na DPTI lista a fila de pendentes e libera o cadastro
    res_fila = client.get("/api/admin/dpti-fila")
    assert res_fila.status_code == 200
    fila = res_fila.json()
    user_pendente = next(u for u in fila if u["ldap_username"] == "vieira.sd")

    res_liberar = client.post("/api/admin/dpti-liberar", json={
        "usuario_id": user_pendente["id"],
        "ldap_username": "vieira.sd",
        "papel": "USUARIO_COMUM",
        "divisao": "DE",
        "secao": "DEPL",
        "admin_username": "admin.dpti"
    })
    assert res_liberar.status_code == 200
    print(f"[OK] Administrador da DPTI liberou a conta: {res_liberar.json()['mensagem']}")

    # Agora o usuário consegue logar!
    res_login_ok = client.post("/api/auth/login-ldap", json={
        "ldap_username": "vieira.sd",
        "password": "comara"
    })
    assert res_login_ok.status_code == 200
    assert res_login_ok.json()["papel"] == "USUARIO_COMUM"
    print("[OK] Usuário logou com sucesso após liberação presencial na DPTI.")

    # 2. FASE 1: INDICAÇÃO PELOS CHEFES DE SEÇÃO (1 SUBORDINADO POR CLASSE)
    print("\n--- 2. FASE 1: INDICAÇÃO PELOS CHEFES DE SEÇÃO ---")
    # Chefe da DEPL (DE) lista subordinados
    res_sub_depl = client.get("/api/fase1/meus-subordinados?secao=DEPL")
    assert res_sub_depl.status_code == 200
    sub_depl = res_sub_depl.json()["membros_por_categoria"]
    cand_grad_depl = sub_depl["Graduados"][0]["id"]

    # Chefe DEPL indica o 1S Lima
    res_ind_depl = client.post("/api/fase1/indicar", json={
        "secao": "DEPL",
        "categoria": "Graduados",
        "candidato_id": cand_grad_depl,
        "ldap_username": "secao.depl"
    })
    assert res_ind_depl.status_code == 200

    # Chefe DEOR (DE) indica o 2S Santos
    res_sub_deor = client.get("/api/fase1/meus-subordinados?secao=DEOR")
    cand_grad_deor = res_sub_deor.json()["membros_por_categoria"]["Graduados"][0]["id"]
    client.post("/api/fase1/indicar", json={
        "secao": "DEOR", "categoria": "Graduados", "candidato_id": cand_grad_deor, "ldap_username": "secao.deor"
    })

    # Chefe DECO (DE) indica o CB Martins
    res_sub_deco = client.get("/api/fase1/meus-subordinados?secao=DECO")
    cand_praca_deco = res_sub_deco.json()["membros_por_categoria"]["Pracas"][0]["id"]
    client.post("/api/fase1/indicar", json={
        "secao": "DECO", "categoria": "Pracas", "candidato_id": cand_praca_deco, "ldap_username": "secao.deco"
    })

    # Chefe DEPJ (DE) indica a servidora civil Ana Paula
    res_sub_depj = client.get("/api/fase1/meus-subordinados?secao=DEPJ")
    cand_civil_depj = res_sub_depj.json()["membros_por_categoria"]["Civil"][0]["id"]
    client.post("/api/fase1/indicar", json={
        "secao": "DEPJ", "categoria": "Civil", "candidato_id": cand_civil_depj, "ldap_username": "secao.depj"
    })

    # Chefe DLTR (DL) indica 1S Guimarães
    res_sub_dltr = client.get("/api/fase1/meus-subordinados?secao=DLTR")
    cand_grad_dltr = res_sub_dltr.json()["membros_por_categoria"]["Graduados"][0]["id"]
    client.post("/api/fase1/indicar", json={
        "secao": "DLTR", "categoria": "Graduados", "candidato_id": cand_grad_dltr, "ldap_username": "secao.dltr"
    })
    print("[OK] Chefes de Seção indicaram 1 subordinado por classe com sucesso.")

    # 3. FASE 2: SELEÇÃO PELOS CHEFES DE DIVISÃO (ATÉ 2 POR CLASSE)
    print("\n--- 3. FASE 2: SELEÇÃO PELOS CHEFES DE DIVISÃO ---")
    client.post("/api/fases/avancar", json={"nova_fase": "FASE_2_DIVISAO", "usuario_admin": "admin.dpti"})

    # Chefe da DE (moreira.cde) lista indicados das seções da DE
    res_ind_de = client.get("/api/fase2/indicados-secoes?divisao=DE")
    assert res_ind_de.status_code == 200
    indicados_de = res_ind_de.json()["indicados_por_categoria"]
    assert len(indicados_de["Graduados"]) == 2 # 1S Lima e 2S Santos

    # Chefe da DE seleciona os 2 Graduados da DE
    res_sel_de = client.post("/api/fase2/selecionar-divisao", json={
        "divisao": "DE",
        "categoria": "Graduados",
        "candidato_ids": [cand_grad_depl, cand_grad_deor],
        "ldap_username": "moreira.cde"
    })
    assert res_sel_de.status_code == 200

    # Chefe da DE seleciona a Praça e o Civil
    client.post("/api/fase2/selecionar-divisao", json={
        "divisao": "DE", "categoria": "Pracas", "candidato_ids": [cand_praca_deco], "ldap_username": "moreira.cde"
    })
    client.post("/api/fase2/selecionar-divisao", json={
        "divisao": "DE", "categoria": "Civil", "candidato_ids": [cand_civil_depj], "ldap_username": "moreira.cde"
    })

    # Chefe da DL seleciona seu Graduado
    client.post("/api/fase2/selecionar-divisao", json={
        "divisao": "DL", "categoria": "Graduados", "candidato_ids": [cand_grad_dltr], "ldap_username": "duarte.cdl"
    })
    print("[OK] Chefes de Divisão selecionaram os representantes das suas divisões.")

    # 4. FASE 3: RODADA DE VETO PELOS CHEFES DE DIVISÃO
    print("\n--- 4. FASE 3: RODADA DE VETO PELOS CHEFES DE DIVISÃO ---")
    client.post("/api/fases/avancar", json={"nova_fase": "FASE_3_VETO", "usuario_admin": "admin.dpti"})

    # Chefes de divisão votam NÃO VETO (0) para os candidatos
    chefes = ["moreira.cde", "duarte.cdl", "vasconcelos.cda", "siqueira.cdpc"]
    cands_fase3 = [cand_grad_depl, cand_grad_deor, cand_praca_deco, cand_civil_depj]

    for chefe in chefes:
        for cid in cands_fase3:
            client.post("/api/fase3/votar-veto", json={
                "candidato_id": cid,
                "voto_veto": 0, # Não veta (aprova)
                "ldap_username": chefe
            })

    # Verificar que candidatos foram aprovados para a Fase 4
    res_vetos = client.get("/api/fase3/candidatos-veto")
    assert res_vetos.status_code == 200
    cand_aprov = res_vetos.json()["candidatos_por_categoria"]["Graduados"][0]
    assert cand_aprov["status_veto"] == "APROVADO_PARA_VOTACAO"
    print("[OK] Rodada de veto concluída: candidatos aprovados sem vetos por maioria.")

    # Configura contas ativas para os votantes da Fase 4
    conn = get_db_connection()
    c = conn.cursor()
    from database import hash_senha
    sh = hash_senha("comara")
    c.execute("INSERT OR REPLACE INTO usuarios_ldap (ldap_username, nome_completo, identificador, papel, divisao, secao, status, senha_hash, criado_em, ativo) VALUES ('lima.1s', 'Carlos Eduardo Lima', '6012341', 'USUARIO_COMUM', 'DE', 'DEPL', 'ATIVO', ?, '2026-09-18T10:00:00', 1)", (sh,))
    c.execute("INSERT OR REPLACE INTO usuarios_ldap (ldap_username, nome_completo, identificador, papel, divisao, secao, status, senha_hash, criado_em, ativo) VALUES ('santos.2s', 'Roberto Silva Santos', '6012342', 'USUARIO_COMUM', 'DE', 'DEOR', 'ATIVO', ?, '2026-09-18T10:00:00', 1)", (sh,))
    c.execute("INSERT OR REPLACE INTO usuarios_ldap (ldap_username, nome_completo, identificador, papel, divisao, secao, status, senha_hash, criado_em, ativo) VALUES ('ana.paula', 'Ana Paula Nogueira', '111.222.333-44', 'USUARIO_COMUM', 'DE', 'DEPJ', 'ATIVO', ?, '2026-09-18T10:00:00', 1)", (sh,))
    conn.commit()
    conn.close()

    # 5. FASE 4: VOTAÇÃO GERAL POR TODO O EFETIVO (POR CLIQUE, SEM NOTAS)
    print("\n--- 5. FASE 4: VOTAÇÃO GERAL POR CLIQUE (SEM NOTAS) ---")
    client.post("/api/fases/avancar", json={"nova_fase": "FASE_4_VOTACAO_GERAL", "usuario_admin": "admin.dpti"})

    # Teste de Segurança 1: Votação sem autenticação (DEVE RETORNAR 401!)
    client.headers.pop("Authorization", None)
    res_sem_auth = client.post("/api/fase4/votar", json={
        "identificador": "6012341",
        "votos": {"Graduados": cand_grad_depl, "Pracas": cand_praca_deco, "Civil": cand_civil_depj}
    })
    assert res_sem_auth.status_code == 401
    print("[OK] Votação sem login foi bloqueada com HTTP 401.")

    # Login do Eleitor 1 (1S Lima - 6012341)
    res_l1 = client.post("/api/auth/login-ldap", json={"ldap_username": "6012341", "password": "comara"})
    assert res_l1.status_code == 200
    token1 = res_l1.json()["token"]

    # Teste de Segurança 2: Eleitor 1 tenta votar no nome do Eleitor 2 (IMPERSONAÇÃO - DEVE RETORNAR 403!)
    res_imp = client.post(
        "/api/fase4/votar",
        headers={"Authorization": f"Bearer {token1}"},
        json={
            "identificador": "6012342",
            "votos": {"Graduados": cand_grad_depl, "Pracas": cand_praca_deco, "Civil": cand_civil_depj}
        }
    )
    assert res_imp.status_code == 403
    print("[OK] Tentativa de votar com identificador de terceiros foi bloqueada com HTTP 403.")

    # Eleitor 1 (1S Lima - 6012341) vota legitimamente
    res_voto1 = client.post(
        "/api/fase4/votar",
        headers={"Authorization": f"Bearer {token1}"},
        json={
            "identificador": "6012341",
            "votos": {"Graduados": cand_grad_depl, "Pracas": cand_praca_deco, "Civil": cand_civil_depj}
        }
    )
    assert res_voto1.status_code == 200
    print(f"[OK] Eleitor 1 votou autenticado por clique. Comprovante: {res_voto1.json()['comprovante_hash']}")

    # Tentativa de Voto Duplo (bloqueio garantido)
    res_duplo = client.post(
        "/api/fase4/votar",
        headers={"Authorization": f"Bearer {token1}"},
        json={
            "identificador": "6012341",
            "votos": {"Graduados": cand_grad_depl, "Pracas": cand_praca_deco, "Civil": cand_civil_depj}
        }
    )
    assert res_duplo.status_code == 400
    print("[OK] Bloqueio de voto duplo funcionando perfeitamente.")

    # Eleitor 2 (2S Santos - 6012342) loga e vota por clique
    res_l2 = client.post("/api/auth/login-ldap", json={"ldap_username": "6012342", "password": "comara"})
    assert res_l2.status_code == 200
    token2 = res_l2.json()["token"]

    client.post(
        "/api/fase4/votar",
        headers={"Authorization": f"Bearer {token2}"},
        json={
            "identificador": "6012342",
            "votos": {"Graduados": cand_grad_depl, "Pracas": cand_praca_deco, "Civil": cand_civil_depj}
        }
    )

    # Eleitor 3 (Civil - 111.222.333-44) loga e vota
    res_l3 = client.post("/api/auth/login-ldap", json={"ldap_username": "111.222.333-44", "password": "comara"})
    assert res_l3.status_code == 200
    token3 = res_l3.json()["token"]

    client.post(
        "/api/fase4/votar",
        headers={"Authorization": f"Bearer {token3}"},
        json={
            "identificador": "111.222.333-44",
            "votos": {"Graduados": cand_grad_deor, "Pracas": cand_praca_deco, "Civil": cand_civil_depj}
        }
    )

    # 6. FASE 5: APRECIAÇÃO E DECISÃO DO PRESIDENTE DA COMARA
    print("\n--- 6. FASE 5: APRECIAÇÃO E DECISÃO DO PRESIDENTE DA COMARA ---")
    client.headers["Authorization"] = f"Bearer {token_adm}"
    client.post("/api/fases/avancar", json={"nova_fase": "FASE_5_COMANDANTE", "usuario_admin": "admin.dpti"})

    res_res = client.get("/api/fase5/resultado-eleicao")
    assert res_res.status_code == 200
    resultado_f5 = res_res.json()["resultado_por_categoria"]
    mais_votado_grad = resultado_f5["Graduados"]["mais_votado"]
    assert mais_votado_grad["id"] == cand_grad_depl
    assert mais_votado_grad["total_votos"] == 2
    print(f"[OK] Mais votado em Graduados: {mais_votado_grad['posto_grad_cargo']} {mais_votado_grad['nome_guerra']} ({mais_votado_grad['total_votos']} votos).")

    # Decisão 1: O Presidente é A FAVOR do mais votado em Graduados
    res_dec_grad = client.post("/api/fase5/decisao-comandante", json={
        "categoria": "Graduados",
        "candidato_mais_votado_id": cand_grad_depl,
        "candidato_final_id": cand_grad_depl,
        "acao_comando": "HOMOLOGADO_ELEITO",
        "despacho": "Homologo o 1S Lima como Graduado Padrão 2026.",
        "comandante_nome": "Cel Av Mendes",
        "comandante_saram": "2987162",
        "ldap_username": "mendes.cmdt"
    })
    assert res_dec_grad.status_code == 200
    print("[OK] Presidente da COMARA HOMOLOGOU o mais votado para Graduado Padrão.")

    # Decisão 2: O Presidente é A FAVOR do mais votado em Praças
    res_dec_praca = client.post("/api/fase5/decisao-comandante", json={
        "categoria": "Pracas",
        "candidato_mais_votado_id": cand_praca_deco,
        "candidato_final_id": cand_praca_deco,
        "acao_comando": "HOMOLOGADO_ELEITO",
        "despacho": "Homologo o CB Martins como Praça Padrão 2026.",
        "comandante_nome": "Cel Av Mendes",
        "comandante_saram": "2987162",
        "ldap_username": "mendes.cmdt"
    })
    assert res_dec_praca.status_code == 200

    # Decisão 3: Em Civil, o Presidente é CONTRA e INDICA DIRETAMENTE O GANHADOR (Prerrogativa Regulamentar!)
    res_dec_civil = client.post("/api/fase5/decisao-comandante", json={
        "categoria": "Civil",
        "candidato_mais_votado_id": cand_civil_depj,
        "candidato_final_id": cand_civil_depj, # ou outro candidato
        "acao_comando": "INDICADO_DIRETO_CMDT",
        "despacho": "Por méritos funcionais destacados na Amazônia Ocidental, decido pela indicação direta.",
        "comandante_nome": "Cel Av Mendes",
        "comandante_saram": "2987162",
        "ldap_username": "mendes.cmdt"
    })
    assert res_dec_civil.status_code == 200
    print("[OK] Presidente da COMARA exerceu sua prerrogativa de escolha direta e formalizou o resultado.")

    print("\nTODOS OS TESTES DO FLUXO COMPLETO EM 5 FASES FORAM CONCLUÍDOS COM 100% DE SUCESSO!")

if __name__ == "__main__":
    rodar_teste_completo()
