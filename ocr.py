import re
from collections import defaultdict
import pytesseract
from PIL import Image

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

_CONFIG = "--psm 6"
_CONF_MIN = 20  # descarta palavras com confiança abaixo disso

# Valor monetário brasileiro. Duas formas aceitas:
#   - parte inteira agrupada por ponto de milhar: 1.234,56 / 12.345,67
#   - parte inteira simples (sem ponto): 95,00 / 1234,56 / 5000,00
# A 2ª alternativa é essencial: sem ela, "5000,00" virava 0.0 e "1234,56" virava 234,56.
_RE_VALOR = re.compile(r"\d{1,3}(?:\.\d{3})+,\d{2}|\d+,\d{2}")


def parsear_valor(texto):
    """Extrai valor numérico brasileiro (ex: 1.234,56 ou 5000,00) de uma string."""
    match = _RE_VALOR.search(texto)
    if match:
        return float(match.group(0).replace(".", "").replace(",", "."))
    return None


def processar_imagem(imagem):
    """
    Agrupa as palavras do Tesseract pelas linhas que ele próprio detectou
    (block_num + par_num + line_num), depois divide cada linha em
    esquerda (categoria) e direita (valor) pelo X de corte.

    Isso evita que palavras de linhas diferentes se misturem, o que
    acontecia quando a banda vertical era calculada manualmente.
    """
    try:
        dados = pytesseract.image_to_data(
            imagem, config=f"{_CONFIG} -l por",
            output_type=pytesseract.Output.DICT
        )
    except pytesseract.TesseractError:
        dados = pytesseract.image_to_data(
            imagem, config=_CONFIG,
            output_type=pytesseract.Output.DICT
        )

    palavras = []
    for i in range(len(dados["text"])):
        texto = dados["text"][i].strip()
        conf = int(dados["conf"][i])
        if not texto or conf < _CONF_MIN:
            continue
        cy = dados["top"][i] + dados["height"][i] // 2
        palavras.append({
            "texto": texto,
            "x":     dados["left"][i],
            "cy":    cy,
            "grupo": (dados["block_num"][i], dados["par_num"][i], dados["line_num"][i]),
        })

    if not palavras:
        return []

    # Agrupa por linha detectada pelo Tesseract
    grupos: dict = defaultdict(list)
    for p in palavras:
        grupos[p["grupo"]].append(p)

    # Monta lista de linhas ordenadas de cima para baixo
    linhas = []
    for _, words in sorted(grupos.items()):
        words = sorted(words, key=lambda w: w["x"])
        cy_medio = sum(w["cy"] for w in words) / len(words)
        linhas.append({"cy": cy_medio, "palavras": words})
    linhas.sort(key=lambda l: l["cy"])

    # X de corte: mediana dos X dos tokens com formato monetário
    x_monetarios = sorted(
        w["x"]
        for linha in linhas
        for w in linha["palavras"]
        if _RE_VALOR.fullmatch(w["texto"])
    )
    if not x_monetarios:
        return []

    split_x = x_monetarios[len(x_monetarios) // 2] - 10

    # Para cada linha: texto à esquerda do corte → categoria; valor à direita → número
    resultados = []
    for linha in linhas:
        esq  = [w for w in linha["palavras"] if w["x"] <  split_x]
        dir_ = [w for w in linha["palavras"] if w["x"] >= split_x]

        valor = next(
            (parsear_valor(w["texto"]) for w in dir_ if parsear_valor(w["texto"]) is not None),
            None
        )
        if valor is not None and esq:
            cat_texto = " ".join(w["texto"] for w in esq)
            resultados.append((cat_texto, valor))

    return resultados
