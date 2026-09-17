"""
Configuração de Produção do Gunicorn para Servidores Linux / aaPanel
Sistema Oficial 'Padrão do Ano' - COMARA
"""
import os
import multiprocessing

bind = os.getenv("BIND", "0.0.0.0:8000")
workers = int(os.getenv("WORKERS", min(4, multiprocessing.cpu_count() * 2 + 1)))
worker_class = "uvicorn.workers.UvicornWorker"
timeout = 120
keepalive = 5
max_requests = 1000
max_requests_jitter = 50
loglevel = os.getenv("LOG_LEVEL", "info")
accesslog = "-"
errorlog = "-"
