import re
from collections import defaultdict
import pytesseract
from PIL import Image, ImageOps

from categorias import normalizar_categoria, deve_ignorar

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

_CONFIG = "--psm 6"
_CONF_MIN = 20      # descarta palavras (não-valor) com confiança abaixo disso
_CONF_RELER = 70    # abaixo disso, re-lê a célula do valor ampliada
_ESCALA_VALOR = 4   # fator de ampliação ao re-ler uma célula de valor

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


def _reler_valor(imagem, left, top, w, h):
    """
    Re-lê apenas a célula de um valor, recortada e ampliada, com whitelist
    de dígitos. Usado quando o OCR da imagem inteira leu o valor com
    confiança baixa — dígitos pequenos eram confundidos (ex: "10,00" → "19,00").
    Retorna o valor (float) ou None se não reconhecer.
    """
    pad = 4
    box = (max(0, left - pad), max(0, top - pad),
           min(imagem.width, left + w + pad), min(imagem.height, top + h + pad))
    cell = imagem.crop(box)
    cell = ImageOps.grayscale(cell)
    cell = ImageOps.autocontrast(cell)
    cell = cell.resize((cell.width * _ESCALA_VALOR, cell.height * _ESCALA_VALOR), Image.LANCZOS)
    try:
        txt = pytesseract.image_to_string(
            cell, config="--psm 7 -c tessedit_char_whitelist=0123456789.,"
        )
    except pytesseract.TesseractError:
        return None
    return parsear_valor(txt)


def _reler_categoria(imagem, palavras_esq, val_h):
    """
    Re-lê a célula da categoria (lado esquerdo), recortada e ampliada. Usado
    quando o texto da categoria saiu garbled na leitura da imagem inteira
    (ex: "Crédito" virou lixo) e a linha não foi reconhecida.

    A altura do recorte é limitada (min das alturas das palavras e a do valor):
    um token garbled costuma ter bounding box com altura inflada, que sujava
    o recorte com texto das linhas vizinhas. Retorna o texto re-lido ou None.
    """
    if not palavras_esq:
        return None
    lefts   = [w["bbox"][0] for w in palavras_esq]
    tops    = [w["bbox"][1] for w in palavras_esq]
    rights  = [w["bbox"][0] + w["bbox"][2] for w in palavras_esq]
    heights = [w["bbox"][3] for w in palavras_esq]
    left, top, right = min(lefts), min(tops), max(rights)
    h = min(heights + [val_h])
    pad = 4
    box = (max(0, left - pad), max(0, top - pad),
           min(imagem.width, right + pad), min(imagem.height, top + h + pad))
    cell = imagem.crop(box)
    cell = ImageOps.grayscale(cell)
    cell = ImageOps.autocontrast(cell)
    cell = cell.resize((cell.width * _ESCALA_VALOR, cell.height * _ESCALA_VALOR), Image.LANCZOS)
    try:
        return pytesseract.image_to_string(cell, config="--psm 7 -l por").strip()
    except pytesseract.TesseractError:
        return None


def processar_imagem(imagem):
    """
    Agrupa as palavras do Tesseract pelas linhas que ele próprio detectou
    (block_num + par_num + line_num), depois divide cada linha em
    esquerda (categoria) e direita (valor) pelo X de corte.

    Isso evita que palavras de linhas diferentes se misturem, o que
    acontecia quando a banda vertical era calculada manualmente.

    O texto da categoria usa a imagem original (acentos leem melhor sem
    pré-processamento); valores lidos com confiança baixa são re-lidos da
    célula ampliada (dígitos pequenos como "10,00" eram lidos como "19,00").
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
        if not texto or conf < 0:
            continue
        # Filtra ruído de baixa confiança, MAS nunca descarta um token com
        # formato de valor monetário — valores reais às vezes saem com conf
        # baixa (ex: "450,00" com conf 18) e não podem ser perdidos.
        if conf < _CONF_MIN and not _RE_VALOR.fullmatch(texto):
            continue
        cy = dados["top"][i] + dados["height"][i] // 2
        palavras.append({
            "texto": texto,
            "x":     dados["left"][i],
            "cy":    cy,
            "conf":  conf,
            "bbox":  (dados["left"][i], dados["top"][i], dados["width"][i], dados["height"][i]),
            "grupo": (dados["block_num"][i], dados["par_num"][i], dados["line_num"][i]),
        })

    if not palavras:
        return []

    # X de corte: mediana dos X dos tokens com formato monetário
    x_monetarios = sorted(w["x"] for w in palavras if _RE_VALOR.fullmatch(w["texto"]))
    if not x_monetarios:
        return []
    split_x = x_monetarios[len(x_monetarios) // 2] - 10

    # Separa as duas colunas pelo X de corte
    esq_tokens = [w for w in palavras if w["x"] <  split_x]
    dir_tokens = [w for w in palavras if w["x"] >= split_x]
    if not dir_tokens:
        return []

    # Agrupa cada coluna em linhas (pela linha detectada pelo Tesseract)
    def _agrupar_linhas(tokens):
        grupos: dict = defaultdict(list)
        for w in tokens:
            grupos[w["grupo"]].append(w)
        linhas = []
        for _, ws in grupos.items():
            ws = sorted(ws, key=lambda w: w["x"])
            cy = sum(w["cy"] for w in ws) / len(ws)
            linhas.append({"cy": cy, "tokens": ws})
        linhas.sort(key=lambda l: l["cy"])
        return linhas

    val_linhas = _agrupar_linhas(dir_tokens)
    cat_linhas = _agrupar_linhas(esq_tokens)

    # Banda vertical de associação categoria↔valor: metade do espaçamento
    # mediano entre as linhas de valor. Ancorar no valor (e não exigir mesmo
    # grupo de linha) resolve o caso da categoria que quebra em 2 linhas
    # visuais e empurra o valor para um grupo de linha separado — aí o valor
    # ficava órfão e a linha era descartada.
    cys = [l["cy"] for l in val_linhas]
    if len(cys) >= 2:
        gaps = sorted(cys[i + 1] - cys[i] for i in range(len(cys) - 1))
        banda = gaps[len(gaps) // 2] / 2
    else:
        banda = max((w["bbox"][3] for w in dir_tokens), default=20) * 1.5

    # Para cada linha de valor, junta a categoria das linhas próximas (dentro da banda)
    resultados = []
    for vl in val_linhas:
        cat_tokens = []
        for cl in cat_linhas:
            if abs(cl["cy"] - vl["cy"]) <= banda:
                cat_tokens.extend(cl["tokens"])
        if not cat_tokens:
            continue
        cat_tokens.sort(key=lambda w: (w["cy"], w["x"]))

        # Token do valor: de preferência um que já parseie; senão um com dígito;
        # senão o primeiro da coluna (pode ter saído totalmente garbled, ex:
        # "20,00" lido como "=" — sem dígito, mas a célula ainda é re-legível).
        tokens = vl["tokens"]
        w_val = next((w for w in tokens if parsear_valor(w["texto"]) is not None), None)
        if w_val is None:
            w_val = next((w for w in tokens if any(c.isdigit() for c in w["texto"])), None)
        if w_val is None:
            w_val = tokens[0]

        valor = parsear_valor(w_val["texto"])
        # Re-lê a célula ampliada quando o valor não parseou (garbled) ou veio
        # com confiança baixa. Leitura boa de confiança alta é mantida.
        if valor is None or w_val["conf"] < _CONF_RELER:
            relido = _reler_valor(imagem, *w_val["bbox"])
            if relido is not None:
                valor = relido

        if valor is None:
            continue

        cat_texto = " ".join(w["texto"] for w in cat_tokens)
        # Categoria não reconhecida e não é linha a ignorar de propósito →
        # texto pode ter saído garbled; re-lê a célula ampliada e só adota a
        # nova leitura se ela passar a classificar (nunca piora um acerto).
        if normalizar_categoria(cat_texto) is None and not deve_ignorar(cat_texto):
            relido = _reler_categoria(imagem, cat_tokens, w_val["bbox"][3])
            if relido and normalizar_categoria(relido) is not None:
                cat_texto = relido

        resultados.append((cat_texto, valor))

    return resultados
