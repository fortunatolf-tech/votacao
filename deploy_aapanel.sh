#!/usr/bin/env bash
# ==============================================================================
# Script de Deploy Automático no aaPanel / VPS Linux
# Sistema Oficial de Seleção e Votação "Padrão do Ano" - COMARA
# ==============================================================================

set -e

echo "======================================================================"
echo "    INICIANDO DEPLOY DO SISTEMA PADRÃO DO ANO (COMARA) NO AAPANEL    "
echo "======================================================================"

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR"

echo "-> Diretório da Aplicação: $APP_DIR"

# 1. Criação e ativação de ambiente virtual Python
if [ ! -d "venv" ]; then
    echo "-> Criando ambiente virtual Python (venv)..."
    python3 -m venv venv
fi

echo "-> Ativando venv e atualizando pip..."
source venv/bin/activate
pip install --upgrade pip

# 2. Instalação das dependências
echo "-> Instalando dependências do requirements.txt..."
pip install -r requirements.txt

# 3. Garantia de diretórios e permissões do SQLite
echo "-> Configurando permissões do diretório data/..."
mkdir -p data
chmod -R 775 data
if [ -f "data/comara_padrao.db" ]; then
    chmod 664 data/comara_padrao.db
fi

# 4. Verificação de integridade e importação do efetivo oficial
echo "-> Verificando integridade e provisionando o banco oficial..."
python3 -c "
import sys, os
sys.path.insert(0, os.path.join(os.getcwd(), 'backend'))
from database import init_db
init_db()
print('Banco SQLite inicializado com sucesso.')
"

# Se o banco estiver vazio, importa o efetivo oficial completo
python3 -c "
import sys, os
sys.path.insert(0, os.path.join(os.getcwd(), 'backend'))
from database import get_db_connection
conn = get_db_connection()
c = conn.cursor()
c.execute('SELECT COUNT(*) as total FROM efetivo')
total = c.fetchone()['total']
conn.close()
if total == 0:
    print('Efetivo zerado. Importando 272 integrantes do efetivo oficial...')
    os.system('python3 importar_efetivo_oficial.py')
else:
    print(f'Efetivo oficial já carregado com {total} integrantes.')
"

# 5. Execução de testes de pré-voo
echo "-> Executando testes automatizados de pré-voo..."
python3 -m unittest backend.test_suite

echo "======================================================================"
echo " DEPLOY CONCLUÍDO COM SUCESSO! "
echo " O sistema está pronto para ser executado via Python Project Manager"
echo " ou comando de inicialização com Gunicorn/Uvicorn:"
echo "   source venv/bin/activate && gunicorn -c gunicorn_conf.py backend.app:app"
echo "======================================================================"
