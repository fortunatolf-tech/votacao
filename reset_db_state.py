import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from database import init_db, get_db_connection
from seed_data import seed_database

def reset():
    init_db()
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM controle_fases")
    c.execute("DELETE FROM indicacoes_fase1_secao")
    c.execute("DELETE FROM indicacoes_fase2_divisao")
    c.execute("DELETE FROM vetos_fase3")
    c.execute("DELETE FROM votos_fase4")
    c.execute("DELETE FROM eleitores_votaram")
    c.execute("DELETE FROM decisao_fase5_comando")
    conn.commit()
    conn.close()

    seed_database()
    print("Estado do banco de dados resetado com sucesso para a FASE 1.")

if __name__ == "__main__":
    reset()
