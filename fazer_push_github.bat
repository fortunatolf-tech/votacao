@echo off
title Push do Sistema Padrao do Ano para o GitHub
color 0A
echo ========================================================
echo   SISTEMA DE VOTACAO PADRAO DO ANO - COMARA
echo   Envio do Repositorio para o GitHub Oficial
echo ========================================================
echo.
echo Repositorio Remoto: https://github.com/fortunatolf-tech/votacao.git
echo Ramo: main
echo.
echo Se o navegador abrir solicitando autorizacao do GitHub, clique em "Authorize".
echo Ou informe seu Personal Access Token se solicitado.
echo.
pause

"C:\Users\DPTI\AppData\Local\GitHubDesktop\app-3.6.6\resources\app\git\cmd\git.exe" push -u origin main

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================================
    echo   [SUCESSO] Repositorio enviado com sucesso para o GitHub!
    echo ========================================================
) else (
    echo.
    echo ========================================================
    echo   [INFO] Caso tenha ocorrido erro de autenticacao:
    echo   1. Voce pode abrir o GitHub Desktop (ja aberto na sua barra de tarefas)
    echo   2. Ir em File -^> Add Local Repository -^> selecionar esta pasta
    echo   3. Clicar em 'Push origin'
    echo   OU execute com seu token:
    echo   git push https://SEU_TOKEN@github.com/fortunatolf-tech/votacao.git main
    echo ========================================================
)

echo.
pause
