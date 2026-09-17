# Guia Definitivo de Deploy no aaPanel
## Sistema Oficial de Seleção e Votação "Padrão do Ano" (COMARA)
**Força Aérea Brasileira &bull; Comissão de Aeroportos da Região Amazônica**

---

Este tutorial orienta o processo completo para colocar em produção o sistema **Padrão do Ano (COMARA)** em um servidor Linux gerenciado pelo **aaPanel** (Ubuntu 20.04/22.04/24.04, Debian 11/12, AlmaLinux ou CentOS 7/8/9).

---

## 🏗️ 1. Arquitetura da Aplicação
* **Backend:** FastAPI (Python 3.10+) com ASGI/WSGI de alta performance.
* **Servidor de Aplicação:** Gunicorn + Uvicorn Workers (`uvicorn.workers.UvicornWorker`).
* **Frontend:** Cédula digital responsiva em HTML5/CSS3/JS puro (montado na raiz `/`).
* **Banco de Dados:** SQLite3 (`data/comara_padrao.db`) com integridade criptográfica SHA-256 e sem necessidade de configurar bancos externos pesados.
* **Porta Interna Padrão:** `8000`.
* **Servidor Web / Proxy Reverso:** Nginx (portas `80` e `443` com SSL HTTPS).

---

## 📋 2. Requisitos Prévios no aaPanel
Antes de iniciar, certifique-se de que o seu aaPanel possui os seguintes módulos instalados através da **App Store** do painel:
1. **Nginx** (qualquer versão 1.20+ ou 1.24+).
2. **Python Manager 2.x** ou **Python Project Manager**.
3. Pelo menos uma versão do **Python (3.10, 3.11 ou 3.12)** adicionada no Python Manager:
   * Vá em **App Store** > **Python Manager** > **Settings** > **Install Python** > Selecione **3.11** ou **3.12**.
4. (Opcional) **Supervisor Manager** (caso prefira gerenciar o serviço via Supervisor em vez de systemd).

---

## 🚀 3. Método 1: Deploy com Python Project Manager (Interface Gráfica do aaPanel)

### Passo 1: Criar o Diretório e Baixar o Código
1. No menu lateral do aaPanel, acesse **Files**.
2. Navegue até `/www/wwwroot/`.
3. Crie a pasta `padrao-comara` (ou clone diretamente via Git no terminal).
4. No terminal do aaPanel (ou via SSH), execute:
   ```bash
   cd /www/wwwroot/
   git clone https://github.com/SEU_USUARIO/SEU_REPOSITORIO.git padrao-comara
   cd padrao-comara
   ```
   *(Ou envie o arquivo ZIP pelo gerenciador de arquivos do aaPanel e extraia dentro de `/www/wwwroot/padrao-comara`)*.

---

### Passo 2: Configurar o Projeto no Python Project Manager
1. No aaPanel, acesse **Website** > aba **Python project** > clique em **Add Python project**.
2. Preencha os campos exatamente como abaixo:
   * **Project Name:** `padrao-comara`
   * **Path:** `/www/wwwroot/padrao-comara`
   * **Python Version:** Selecione `Python 3.11` (ou a versão 3.10+ instalada)
   * **Framework:** `Custom` (ou `FastAPI`)
   * **Execution Method:** `gunicorn`
   * **Startup File/Folder:** `backend/app.py`
   * **Run Parameters / Startup command:**
     ```bash
     gunicorn -c gunicorn_conf.py backend.app:app
     ```
   * **Port:** `8000`
   * **Run User:** `www` (ou `root`)
   * **Processes:** `4`
3. Marque a opção para **Install requirements.txt** (o sistema detectará o `requirements.txt` na raiz automaticamente).
4. Clique em **Confirm**. O aaPanel criará o ambiente virtual (`/www/wwwroot/padrao-comara/padrao-comara_venv`) e instalará as dependências.

---

### Passo 3: Ajustar Permissões de Dados (Crítico para SQLite)
O banco de dados SQLite precisa de permissão de escrita pelo usuário do processo:
No terminal do aaPanel, execute:
```bash
cd /www/wwwroot/padrao-comara
mkdir -p data
chown -R www:www data
chmod -R 775 data
if [ -f "data/comara_padrao.db" ]; then
    chmod 664 data/comara_padrao.db
fi
```

---

## ⚡ 4. Método 2: Deploy Automatizado via Terminal / SSH (1 Comando)

Se preferir fazer tudo pelo terminal do servidor, utilize o script automatizado incluído no projeto:

```bash
cd /www/wwwroot/
git clone https://github.com/SEU_USUARIO/SEU_REPOSITORIO.git padrao-comara
cd padrao-comara
chmod +x deploy_aapanel.sh
./deploy_aapanel.sh
```

### Criando o Serviço Systemd (Para Inicialização Automática com o Servidor)
Crie o arquivo de serviço do sistema:
```bash
cat << 'EOF' > /etc/systemd/system/comara-padrao.service
[Unit]
Description=Sistema Oficial Padrao do Ano - COMARA
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/www/wwwroot/padrao-comara
Environment="PATH=/www/wwwroot/padrao-comara/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin"
ExecStart=/www/wwwroot/padrao-comara/venv/bin/gunicorn -c gunicorn_conf.py backend.app:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
```

Ative e inicie o serviço:
```bash
systemctl daemon-reload
systemctl enable comara-padrao
systemctl restart comara-padrao
systemctl status comara-padrao
```

---

## 🌐 5. Configuração do Nginx e Domínio / IP no aaPanel

Para que o sistema seja acessado publicamente na porta 80/443 (e com certificado SSL):

### Criando o Site no aaPanel:
1. No aaPanel, acesse **Website** > **Add site**.
2. **Domain Name:** Digite o seu domínio (ex: `eleicoes.comara.intraer` ou `padrao.seuservidor.com`) ou o IP do servidor.
3. **PHP Version:** Selecione `Pure Python` ou `Static`.
4. Clique em **Submit**.

---

### Configurando o Reverse Proxy (Proxy Reverso):
1. Na lista de sites, clique sobre o domínio criado.
2. Acesse a aba **Reverse Proxy** > clique em **Add Reverse Proxy**.
3. Preencha:
   * **Proxy Name:** `comara_api`
   * **Target URL:** `http://127.0.0.1:8000`
   * **Sent Domain:** `$host`
4. Clique em **Save**.

---

### Configuração Avançada do Nginx (Recomendada):
Para garantir suporte pleno a WebSockets, envio de cabeçalhos reais de IP e uploads sem restrição, clique em **Edit Config** do site no Nginx e inclua o seguinte bloco `location /`:

```nginx
location / {
    proxy_pass http://127.0.0.1:8000;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection 'upgrade';
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_connect_timeout 90s;
    proxy_send_timeout 90s;
    proxy_read_timeout 90s;
    client_max_body_size 50M;
}
```

---

### Certificado SSL Gratuito (HTTPS):
1. No menu do site no aaPanel, clique na aba **SSL**.
2. Selecione a aba **Let's Encrypt**.
3. Marque os seus domínios e clique em **Apply**.
4. Ative a chave **Force HTTPS**.
5. Pronto! Seu sistema está acessível com criptografia SSL e cadeado verde.

---

## 👥 6. Inicialização do Efetivo Oficial (272 Integrantes da COMARA)

O repositório já inclui o script de processamento oficial com todos os 264 militares e 8 civis da COMARA.

Para garantir que a base esteja com os 272 integrantes carregados na primeira inicialização:
```bash
cd /www/wwwroot/padrao-comara
source venv/bin/activate  # ou source padrao-comara_venv/bin/activate
python3 importar_efetivo_oficial.py
```
Isso criará automaticamente:
* `data/comara_padrao.db` com o efetivo militar/civil categorizado.
* `data/efetivo_comara_oficial.xlsx` com a planilha oficial formatada.

---

## 🔒 7. Credenciais de Acesso Administrativo e Comando

| Papel | Login LDAP | Senha Inicial | Titular Oficial |
| :--- | :--- | :--- | :--- |
| **Administrador Geral** | `admin.dpti` | `comara` | Administrador DPTI |
| **Presidente da COMARA (CMDT)** | `trigueiro.cmdt` | `comara` | Cel Av Trigueiro |
| **Chefe Divisão Engenharia (DE)** | `moreira.cde` | `comara` | Ten Cel Eng Moreira |
| **Chefe Divisão Logística (DL)** | `duarte.cdl` | `comara` | Ten Cel Int Duarte |
| **Chefe Divisão Apoio (DA)** | `vasconcelos.cda` | `comara` | Ten Cel Av Vasconcelos |
| **Chefe Divisão DPC** | `siqueira.cdpc` | `comara` | Cel Av Siqueira |
| **Chefe DACO-MN** | `rocha.cdaco` | `comara` | Ten Cel Av Rocha |
| **Chefe Vice-Presidência (VP)** | `baptista.vp` | `comara` | Cel Av Baptista |

---

## 🛠️ 8. Resolução de Problemas (Troubleshooting)

### 1. Erro 502 Bad Gateway no Navegador
* O serviço Python não está em execução ou não conseguiu bindar na porta 8000.
* No terminal, execute:
  ```bash
  journalctl -u comara-padrao -n 50 --no-pager
  # ou verifique os logs do Python Manager no aaPanel
  ```
* Verifique se a porta 8000 já não está ocupada: `netstat -tlpn | grep 8000`

### 2. Erro "attempt to write a readonly database"
* O usuário do Nginx (`www` ou `www-data`) não possui permissão de escrita no arquivo SQLite ou na pasta `data`.
* Execute:
  ```bash
  chown -R www:www /www/wwwroot/padrao-comara/data
  chmod -R 775 /www/wwwroot/padrao-comara/data
  ```

### 3. Verificar status da aplicação
Para testar localmente no servidor se o FastAPI está respondendo:
```bash
curl -I http://127.0.0.1:8000/
# Deve retornar HTTP/1.1 200 OK
```

### 4. Backup do Banco de Dados
Para fazer backup a qualquer momento de todo o histórico criptográfico de votos e auditoria:
```bash
cp /www/wwwroot/padrao-comara/data/comara_padrao.db /www/backup/comara_backup_$(date +%Y%m%d).db
```
