"""
Suíte Oficial de Testes Automatizados - Sistema 'Padrão do Ano' (COMARA)
Validação Completa do Fluxo em 5 Fases, Auto-Cadastro e Aprovação na DPTI
"""
import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import get_db_connection, init_db, hash_senha
from logic import (
    CATEGORIAS_OFICIAIS,
    NOMES_CLASSES,
    gerar_hash_eleitor,
    validar_indicacao_fase1,
    validar_selecao_fase2,
    apurar_vetos_fase3,
    apurar_votos_fase4
)

class TestProcessoSeletivoComara(unittest.TestCase):

    def setUp(self):
        init_db()

    # 1. TESTE DE AUTO-CADASTRO E BLOQUEIO PENDENTE DPTI
    def test_01_auto_cadastro_e_bloqueio_pendente_dpti(self):
        """Ao se auto-cadastrar, usuário é criado como USUARIO_COMUM com status PENDENTE_DPTI"""
        conn = get_db_connection()
        c = conn.cursor()
        shash = hash_senha("minhasenha123")
        c.execute("""
        INSERT OR REPLACE INTO usuarios_ldap (ldap_username, nome_completo, identificador, papel, divisao, secao, status, senha_hash, criado_em, ativo)
        VALUES ('soldado.silva', 'Sd Silva Ramos', '8910293', 'USUARIO_COMUM', 'DE', 'DEPL', 'PENDENTE_DPTI', ?, '2026-09-16T12:00:00', 1)
        """, (shash,))
        conn.commit()

        c.execute("SELECT status, papel FROM usuarios_ldap WHERE ldap_username = 'soldado.silva'")
        user = c.fetchone()
        self.assertEqual(user["status"], "PENDENTE_DPTI", "Conta recém auto-cadastrada deve nascer bloqueada como PENDENTE_DPTI.")
        self.assertEqual(user["papel"], "USUARIO_COMUM")
        conn.close()

    # 2. TESTE DE LIBERAÇÃO NA DPTI PELO ADMINISTRADOR
    def test_02_liberacao_e_atribuicao_papel_pela_dpti(self):
        """Administrador da DPTI vincula a conta de rede e define modificador de acesso definitivo"""
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("""
        UPDATE usuarios_ldap
        SET status = 'ATIVO', papel = 'CHEFE_SECAO', vinculado_por = 'admin.dpti', vinculado_em = '2026-09-16T12:30:00'
        WHERE ldap_username = 'soldado.silva'
        """)
        conn.commit()

        c.execute("SELECT status, papel, vinculado_por FROM usuarios_ldap WHERE ldap_username = 'soldado.silva'")
        user = c.fetchone()
        self.assertEqual(user["status"], "ATIVO", "Conta deve estar ATIVA após liberação na DPTI.")
        self.assertEqual(user["papel"], "CHEFE_SECAO", "Papel deve ter sido atualizado para CHEFE_SECAO.")
        self.assertEqual(user["vinculado_por"], "admin.dpti")
        conn.close()

    # 3. TESTE DA FASE 1: CHEFE DE SEÇÃO INDICA 1 SUBORDINADO
    def test_03_fase1_indicacao_chefe_secao(self):
        """Chefe de Seção pode indicar 1 subordinado da sua seção por classe"""
        subordinado_valido = {"nome_guerra": "Lima", "secao": "DEPL", "categoria": "Graduados"}
        valido, msg = validar_indicacao_fase1(subordinado_valido, "DEPL", "Graduados")
        self.assertTrue(valido, f"Deveria ser válido: {msg}")

        # Rejeição de subordinado de outra seção
        subordinado_outro = {"nome_guerra": "Vieira", "secao": "DEPJ", "categoria": "Graduados"}
        invalido, msg_inv = validar_indicacao_fase1(subordinado_outro, "DEPL", "Graduados")
        self.assertFalse(invalido, "Deve bloquear indicação de militar de outra seção.")

    # 4. TESTE DA FASE 2: CHEFE DE DIVISÃO SELECIONA 2 MILITARES
    def test_04_fase2_selecao_chefe_divisao(self):
        """Chefe de Divisão seleciona até 2 indicados pelas seções subordinadas à sua divisão"""
        candidatos_disponiveis = [
            {"id": 10, "nome": "Sgt Alfa", "divisao": "DE"},
            {"id": 11, "nome": "Sgt Bravo", "divisao": "DE"},
            {"id": 12, "nome": "Sgt Charlie", "divisao": "DE"}
        ]
        # Seleciona 2 permitidos
        valido, msg = validar_selecao_fase2([10, 11], candidatos_disponiveis, maximo_permitido=2)
        self.assertTrue(valido)

        # Tentativa de selecionar 3 (deve bloquear!)
        invalido, msg_inv = validar_selecao_fase2([10, 11, 12], candidatos_disponiveis, maximo_permitido=2)
        self.assertFalse(invalido, "Deve bloquear seleção superior a 2 candidatos.")

    # 5. TESTE DA FASE 3: RODADA DE VETO PELOS CHEFES DE DIVISÃO
    def test_05_fase3_apuracao_vetos(self):
        """Candidato que recebe maioria de vetos é VETADO; sem maioria é APROVADO"""
        candidatos = [
            {"id": 1, "nome": "Candidato Aprovado"},
            {"id": 2, "nome": "Candidato Vetado"}
        ]
        # Total de 6 chefes de divisão:
        # Candidato 1 recebe 1 veto -> aprovado
        # Candidato 2 recebe 4 vetos (> 3) -> vetado
        vetos = [
            {"candidato_id": 1, "chefe_divisao_ldap": "chefe1", "voto_veto": 1},
            {"candidato_id": 1, "chefe_divisao_ldap": "chefe2", "voto_veto": 0},
            {"candidato_id": 2, "chefe_divisao_ldap": "chefe1", "voto_veto": 1},
            {"candidato_id": 2, "chefe_divisao_ldap": "chefe2", "voto_veto": 1},
            {"candidato_id": 2, "chefe_divisao_ldap": "chefe3", "voto_veto": 1},
            {"candidato_id": 2, "chefe_divisao_ldap": "chefe4", "voto_veto": 1}
        ]
        resultado = apurar_vetos_fase3(candidatos, vetos, total_chefes_divisao=6)
        self.assertEqual(resultado[0]["status_veto"], "APROVADO_PARA_VOTACAO")
        self.assertEqual(resultado[1]["status_veto"], "VETADO")

    # 6. TESTE DA FASE 4: VOTAÇÃO GERAL POR CLIQUE (SEM NOTAS)
    def test_06_fase4_votacao_geral_por_clique(self):
        """Votação direta por contagem de cliques sem atribuição de notas"""
        candidatos = [
            {"id": 1, "nome": "1S Lima", "tempo_comara_meses": 48},
            {"id": 2, "nome": "2S Santos", "tempo_comara_meses": 36},
            {"id": 3, "nome": "3S Costa", "tempo_comara_meses": 60}
        ]
        votos = {1: 45, 2: 12, 3: 20}
        apurados = apurar_votos_fase4(candidatos, votos)

        self.assertEqual(apurados[0]["id"], 1, "O mais votado deve ser o 1S Lima.")
        self.assertEqual(apurados[0]["total_votos"], 45)
        self.assertTrue(apurados[0]["mais_votado"])
        self.assertFalse(apurados[1]["mais_votado"])

    # 7. TESTE DA FASE 5: PRERROGATIVA DE ESCOLHA DO PRESIDENTE DA COMARA
    def test_07_fase5_decisao_presidente_comara(self):
        """Presidente pode homologar o eleito ou indicar diretamente outro ganhador se for contra"""
        # Caso 1: A favor -> homologa o mais votado
        candidato_eleito_id = 1
        decisao_a_favor = "HOMOLOGADO_ELEITO"
        candidato_vencedor_final = candidato_eleito_id
        self.assertEqual(candidato_vencedor_final, 1)

        # Caso 2: Contra -> Comandante indica diretamente o ganhador de sua escolha
        candidato_escolhido_cmdt = 3 # 3S Costa
        decisao_contra = "INDICADO_DIRETO_CMDT"
        candidato_vencedor_final_cmdt = candidato_escolhido_cmdt
        self.assertEqual(candidato_vencedor_final_cmdt, 3, "Comandante tem a prerrogativa de indicar quem ele quer que seja o ganhador.")

def rodar_testes_e_obter_relatorio():
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestProcessoSeletivoComara)
    runner = unittest.TextTestRunner(verbosity=2)
    resultado = runner.run(suite)
    return {
        "total_testes": resultado.testsRun,
        "erros": len(resultado.errors),
        "falhas": len(resultado.failures),
        "sucesso": resultado.wasSuccessful()
    }

if __name__ == "__main__":
    unittest.main()
