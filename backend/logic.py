"""
Módulo de Lógica de Negócio e Algoritmos das 5 Fases Eleitorais
Prêmio 'Padrão do Ano' - COMARA
"""
import hashlib
from typing import List, Dict, Any, Tuple

CATEGORIAS_OFICIAIS = ["Graduados", "Pracas", "Civil"]

NOMES_CLASSES = {
    "Graduados": "Graduado Padrão da COMARA (SO/SGT)",
    "Pracas": "Praça Padrão da COMARA (SD/CB)",
    "Civil": "Civil Padrão da COMARA"
}

def gerar_hash_eleitor(identificador: str, salt: str = "COMARA_PADRAO_ANO_2026_SECRET") -> str:
    """Gera hash SHA-256 anônimo e idempotente para o eleitor."""
    limpo = identificador.strip().replace(".", "").replace("-", "").upper()
    chave = f"{salt}:{limpo}"
    return hashlib.sha256(chave.encode("utf-8")).hexdigest()

def validar_indicacao_fase1(
    candidato: Dict[str, Any],
    secao_chefe: str,
    categoria: str
) -> Tuple[bool, str]:
    """
    Fase 1: O Chefe de Seção indica 1 militar/servidor subordinado a ele por classe.
    """
    if candidato["secao"] != secao_chefe:
        return False, f"O integrante {candidato['nome_guerra']} não pertence à sua seção ({secao_chefe})."
        
    if candidato["categoria"] != categoria:
        return False, f"O integrante {candidato['nome_guerra']} pertence à categoria {candidato['categoria']}, não {categoria}."
        
    return True, "Indicação válida na Fase 1."

def validar_selecao_fase2(
    candidatos_selecionados_ids: List[int],
    candidatos_disponiveis: List[Dict[str, Any]],
    maximo_permitido: int = 2
) -> Tuple[bool, str]:
    """
    Fase 2: O Chefe de Divisão seleciona até 2 militares/civis entre os indicados pelas seções subordinadas.
    """
    ids_disponiveis = [c["id"] for c in candidatos_disponiveis]
    for cid in candidatos_selecionados_ids:
        if cid not in ids_disponiveis:
            return False, f"O candidato ID {cid} não foi indicado pelas seções subordinadas à sua divisão."
            
    if len(candidatos_selecionados_ids) > maximo_permitido:
        return False, f"O Chefe de Divisão pode selecionar no máximo {maximo_permitido} candidatos por categoria."
        
    return True, "Seleção válida na Fase 2."

def apurar_vetos_fase3(
    candidatos: List[Dict[str, Any]],
    vetos_registrados: List[Dict[str, Any]],
    total_chefes_divisao: int
) -> List[Dict[str, Any]]:
    """
    Fase 3: Todos os Chefes de Divisão votam se vetam (1) ou não vetam (0).
    Avançam para a Fase 4 os candidatos que NÃO forem vetados por maioria.
    """
    resultado = []
    for c in candidatos:
        cid = c["id"]
        votos_candidato = [v for v in vetos_registrados if v["candidato_id"] == cid]
        total_vetos = sum(1 for v in votos_candidato if v["voto_veto"] == 1)
        total_nao_vetos = sum(1 for v in votos_candidato if v["voto_veto"] == 0)
        
        # Um candidato é considerado aprovado se os vetos forem menores que a maioria
        # Ou seja, vetos < (total_chefes_divisao / 2)
        vetado = total_vetos > (total_chefes_divisao / 2)
        
        item = dict(c)
        item["total_vetos"] = total_vetos
        item["total_nao_vetos"] = total_nao_vetos
        item["status_veto"] = "VETADO" if vetado else "APROVADO_PARA_VOTACAO"
        resultado.append(item)
        
    return resultado

def apurar_votos_fase4(
    candidatos_categoria: List[Dict[str, Any]],
    contagem_votos: Dict[int, int]
) -> List[Dict[str, Any]]:
    """
    Fase 4: Totalização direta de votos por clique (sem notas!).
    Ordena pelo maior número de votos. Desempate subsidiário por tempo de COMARA.
    """
    apurados = []
    for c in candidatos_categoria:
        cid = c["id"]
        votos = contagem_votos.get(cid, 0)
        item = dict(c)
        item["total_votos"] = votos
        apurados.append(item)
        
    # Ordenar por votos decrescente, desempate secundário por tempo_comara_meses
    apurados.sort(
        key=lambda x: (int(x.get("total_votos", 0)), int(x.get("tempo_comara_meses", 0))),
        reverse=True
    )
    
    for idx, c in enumerate(apurados):
        c["posicao"] = idx + 1
        c["mais_votado"] = (idx == 0)
        
    return apurados
