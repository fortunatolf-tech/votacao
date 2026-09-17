# 🎖️ Sistema Oficial de Seleção e Votação "Padrão do Ano" (COMARA)
### Força Aérea Brasileira &bull; Comissão de Aeroportos da Região Amazônica

Sistema oficial para operacionalizar integralmente o processo seletivo do prêmio **"Padrão do Ano"** da **COMARA**, atendendo estritamente ao regulamento interno (**RICA 21-209** e **ROCA 21-55**), com segregação de categorias funcionais, controle presencial na DPTI, cabine de votação digital direta por clique e deliberação soberana da Presidência da COMARA.

---

## 🌟 Funcionalidades Principais

### 1. Três Classes Funcionais Totalmente Segregadas
* **Graduado Padrão:** Suboficiais (SO) e Sargentos (1S, 2S, 3S).
* **Praça Padrão:** Cabos (CB) e Soldados (S1, S2).
* **Civil Padrão:** Servidores Públicos Civis (SPPF e SPTF).

### 2. Fluxo Eleitoral em 5 Fases Sequenciais
1. **Fase 1 (Seções):** Cada Chefe de Seção indica 1 militar/civil diretamente subordinado por classe.
2. **Fase 2 (Divisões):** Cada Chefe de Divisão seleciona até 2 representantes da sua divisão por classe.
3. **Fase 3 (Rodada de Veto):** Todos os Chefes de Divisão deliberam votando VETO ou NÃO VETO. Candidatos com a maioria de vetos são desqualificados.
4. **Fase 4 (Votação Geral Popular):** Todo o efetivo habilitado vota diretamente por clique nos cartões (sem notas, sem voto em branco ou nulo, auto-voto permitido).
5. **Fase 5 (Decisão Presidencial):** O Presidente da COMARA (Comandante da OM) avalia a apuração e pode homologar os mais votados ou exercer sua prerrogativa institucional de indicar diretamente o vencedor.

### 3. Credenciamento Presencial Obrigatório na DPTI
* Todo usuário recém auto-cadastrado entra bloqueado com status `PENDENTE_DPTI`.
* A ativação só ocorre presencialmente na DPTI pelo Administrador, vinculando o login LDAP de rede e atribuindo o modificador de acesso funcional (`USUARIO_COMUM`, `CHEFE_SECAO`, `CHEFE_DIVISAO`, `CMDT_OM` ou `ADMINISTRADOR`).

### 4. Cabine de Votação Digital com Abertura Direta
* Cédula digital que abre imediatamente na escolha dos candidatos com detecção do eleitor ativo.
* Pílulas de progresso em tempo real (`⚪ Pendente` ➔ `🟢 Escolhido`).
* Avisos visuais com pulso de destaque (`missing-category-pulse`) caso o eleitor tente submeter o voto sem preencher as 3 classes.
* Emissão de comprovante digital com hash criptográfico SHA-256 inviolável.

### 5. Auditoria Criptográfica SHA-256 e Roster Oficial
* 272 integrantes oficiais da COMARA carregados e validados no banco de dados SQLite.
* Planilha oficial gerada: `data/efetivo_comara_oficial.xlsx`.
* Trilha de auditoria imutável gravando todas as ações em tempo real.

---

## 🚀 Como Executar Localmente

### Pré-requisitos
* Python 3.10 ou superior.

### 1. Clonar o Repositório
```bash
git clone https://github.com/SEU_USUARIO/comara-padrao-ano.git
cd comara-padrao-ano
```

### 2. Criar Ambiente Virtual e Instalar Dependências
```bash
python -m venv venv
# No Windows:
.\venv\Scripts\activate
# No Linux/Mac:
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Inicializar o Efetivo Oficial (Opcional se já existir data/comara_padrao.db)
```bash
python importar_efetivo_oficial.py
```

### 4. Executar os Testes Automatizados
```bash
python -m unittest backend.test_suite
# ou
python test_e2e_flow.py
```

### 5. Iniciar o Servidor
```bash
python run_server.py
```
Acesse no navegador: **[http://localhost:8000](http://localhost:8000)**.

---

## 🌐 Deploy em Produção (aaPanel / Linux / Docker)

Para o guia passo a passo completo de deploy no **aaPanel**, consulte o arquivo dedicado:
📖 **[TUTORIAL_DEPLOY_AAPANEL.md](TUTORIAL_DEPLOY_AAPANEL.md)**

### Deploy Rápido com Docker
```bash
docker-compose up -d --build
```

---

## 🔑 Credenciais de Acesso Inicial para Demonstração

| Papel | Login LDAP | Senha | Integrante Oficial |
| :--- | :--- | :--- | :--- |
| **Administrador Geral** | `admin.dpti` | `comara` | Administrador DPTI |
| **Presidente da COMARA** | `trigueiro.cmdt` | `comara` | Cel Av Trigueiro |
| **Chefe Divisão Engenharia** | `moreira.cde` | `comara` | Ten Cel Eng Moreira |
| **Chefe Divisão Logística** | `duarte.cdl` | `comara` | Ten Cel Int Duarte |
| **Chefe Divisão Apoio** | `vasconcelos.cda` | `comara` | Ten Cel Av Vasconcelos |
| **Chefe Seção DEPL** | `secao.depl` | `comara` | Cap Eng Rios |
| **Eleitor Comum** | `lima.eleitor` | `comara` | 1S Lima |

---

## 📄 Licença e Conformidade
Desenvolvido em conformidade com as normas regulamentares da **Força Aérea Brasileira (FAB)** e da **Comissão de Aeroportos da Região Amazônica (COMARA)**.
Todos os direitos reservados.
