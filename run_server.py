"""
Script de Inicialização do Sistema 'Padrão do Ano' - COMARA
Executa a validação de integridade pré-voo e inicializa o servidor web FastAPI / Uvicorn.
"""
import sys
import os
import uvicorn

# Garante que o diretório backend esteja no sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from test_suite import rodar_testes_e_obter_relatorio
from seed_data import seed_database
from app import app

def main():
    print("=" * 70)
    print("SISTEMA OFICIAL DE SELEÇÃO E VOTAÇÃO - PADRÃO DO ANO (COMARA)")
    print("Força Aérea Brasileira - Comissão de Aeroportos da Região Amazônica")
    print("=" * 70)
    
    # 1. Execução de testes de validação pré-voo
    print("\n[1/3] Executando bateria obrigatória de testes de validação algorítmica...")
    laudo = rodar_testes_e_obter_relatorio()
    if not laudo["sucesso"]:
        print(f"ERRO CRÍTICO: Falha na validação prévia dos algoritmos! Erros: {laudo['erros']}, Falhas: {laudo['falhas']}")
        sys.exit(1)
    print(f" -> Sucesso: {laudo['total_testes']} testes automatizados aprovados sem erros.")
    
    # 2. Inicialização e verificação da base de dados
    print("\n[2/3] Verificando base de dados SQLite e planilhas modelo...")
    seed_database()
    print(" -> Base de dados e registros iniciais prontos.")
    
    # 3. Inicialização do servidor web
    print("\n[3/3] Iniciando servidor web oficial na porta 8000...")
    print(" -> Acesse o sistema pelo navegador em: http://localhost:8000")
    print("=" * 70)
    
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")

if __name__ == "__main__":
    main()
