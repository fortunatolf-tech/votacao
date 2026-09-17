FROM python:3.11-slim

WORKDIR /app

# Instala dependências do sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copia e instala dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia os arquivos do projeto
COPY . .

# Cria diretório de dados persistente e define permissões
RUN mkdir -p /app/data && chmod -R 775 /app/data

EXPOSE 8000

ENV HOST=0.0.0.0
ENV PORT=8000

CMD ["gunicorn", "-c", "gunicorn_conf.py", "backend.app:app"]
