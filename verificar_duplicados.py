import sys

with open("analisar_efetivo.py", "r", encoding="utf-8") as f:
    content = f.read()

# Extrai o bloco de dados
start = content.find('dados_raw = """') + len('dados_raw = """')
end = content.find('"""', start)
raw = content[start:end].strip()

linhas = raw.split("\n")
nomes = {}
duplicados = []
registros = []

for l in linhas:
    parts = [p.strip() for p in l.split("\t")]
    if len(parts) >= 7:
        ordem, posto, esp, nome, guerra, ddd, tel = parts[:7]
    elif len(parts) == 6:
        ordem, posto, esp, nome, guerra, ddd = parts[:6]
        tel = ""
    elif len(parts) == 5:
        ordem, posto, nome, guerra, ddd = parts[:5]
        esp = ""
        tel = ""
    else:
        continue
    
    reg = {
        "ordem": ordem,
        "posto": posto,
        "esp": esp,
        "nome": nome,
        "guerra": guerra,
        "ddd": ddd,
        "tel": tel
    }
    registros.append(reg)
    if nome in nomes:
        duplicados.append((nome, nomes[nome], ordem))
    else:
        nomes[nome] = ordem

print(f"Total registros processados: {len(registros)}")
print(f"Nomes únicos: {len(nomes)}")
print(f"Duplicados encontrados: {len(duplicados)}")
for dup in duplicados:
    print(f"  - {dup[0]}: ordens {dup[1]} e {dup[2]}")
