import json
import os

ARQUIVO_TOTAIS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "totais.json")

_CATEGORIAS_PADRAO = {"credito": 0.0, "debito": 0.0, "pix": 0.0}


def carregar_totais():
    """Lê o totais.json e retorna o dicionário com os valores acumulados."""
    if not os.path.exists(ARQUIVO_TOTAIS):
        return _CATEGORIAS_PADRAO.copy()
    try:
        with open(ARQUIVO_TOTAIS, "r", encoding="utf-8") as f:
            dados = json.load(f)
        for cat in _CATEGORIAS_PADRAO:
            if cat not in dados:
                dados[cat] = 0.0
        return dados
    except Exception:
        return _CATEGORIAS_PADRAO.copy()


def salvar_totais(totais):
    """Persiste o dicionário de totais no totais.json."""
    with open(ARQUIVO_TOTAIS, "w", encoding="utf-8") as f:
        json.dump(totais, f, ensure_ascii=False, indent=2)


def acumular(novos_valores):
    """
    Recebe dict {categoria: valor} extraído da captura atual e
    soma nos totais já existentes. Retorna os totais atualizados.
    """
    totais = carregar_totais()
    for cat, val in novos_valores.items():
        if cat in totais:
            totais[cat] += val
    salvar_totais(totais)
    return totais


def zerar_totais():
    """Reseta todos os totais para zero e sobrescreve o arquivo."""
    totais = _CATEGORIAS_PADRAO.copy()
    salvar_totais(totais)
    return totais
