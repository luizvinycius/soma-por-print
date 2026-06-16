import re
import pytesseract
from PIL import Image, ImageOps

from categorias import normalizar_categoria, deve_ignorar

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# Modos de segmentação de página rodados e UNIDOS (ver processar_imagem):
#   - psm 6  = "bloco uniforme": leitura limpa, mas a análise de layout às vezes
#              DESCARTA linhas inteiras (no print de 4 linhas, só retornava 1).
#   - psm 11 = "texto esparso": acha TODAS as linhas (não descarta), porém com
#              agrupamento de linha ruim — por isso agrupamos por geometria (Y),
#              não pelo line_num do Tesseract.
# Unir os dois dá recall do 11 + leitura limpa do 6. Nenhum PSM sozinho é confiável.
_PSMS = (6, 11)
_CONF_MIN = 20      # descarta palavras (não-valor) com confiança abaixo disso
_CONF_RELER = 70    # abaixo disso, re-lê a célula do valor ampliada
_ESCALA_VALOR = 4   # fator de ampliação ao re-ler uma célula de valor

# Valor monetário brasileiro. Duas formas aceitas:
#   - parte inteira agrupada por ponto de milhar: 1.234,56 / 12.345,67
#   - parte inteira simples (sem ponto): 95,00 / 1234,56 / 5000,00
# A 2ª alternativa é essencial: sem ela, "5000,00" virava 0.0 e "1234,56" virava 234,56.
_RE_VALOR = re.compile(r"\d{1,3}(?:\.\d{3})+,\d{2}|\d+,\d{2}")


def _eh_celula_valor(texto):
    """
    True se o token PARECE uma célula de valor (>= 2 dígitos), mesmo lido com
    erro. Valores como "318,00" às vezes saem garbled e com confiança baixíssima
    ("218oo" conf 9, "62(00" conf 0) — não casam _RE_VALOR e seriam descartados
    pelo filtro de confiança, sumindo a linha inteira. Mantê-los permite re-ler a
    célula ampliada e recuperar o valor.
    """
    return sum(c.isdigit() for c in texto) >= 2


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


def _extrair_tokens(imagem, psm):
    """
    Roda image_to_data num modo PSM (idioma por, com fallback sem idioma) e
    devolve os tokens já filtrados por confiança. Não guarda o agrupamento de
    linha do Tesseract — a linha é reconstruída depois por geometria (Y).
    """
    try:
        dados = pytesseract.image_to_data(
            imagem, config=f"--psm {psm} -l por",
            output_type=pytesseract.Output.DICT
        )
    except pytesseract.TesseractError:
        dados = pytesseract.image_to_data(
            imagem, config=f"--psm {psm}",
            output_type=pytesseract.Output.DICT
        )

    tokens = []
    for i in range(len(dados["text"])):
        texto = dados["text"][i].strip()
        conf = int(dados["conf"][i])
        if not texto or conf < 0:
            continue
        # Filtra ruído de baixa confiança, MAS nunca descarta um token com
        # formato de valor monetário (ex: "450,00" com conf 18) nem um token
        # que pareça uma célula de valor lida com erro (>= 2 dígitos, ex:
        # "218oo"/"62(00") — esses são re-lidos da célula ampliada e, se
        # descartados aqui, levam a linha inteira junto.
        if conf < _CONF_MIN and not _RE_VALOR.fullmatch(texto) and not _eh_celula_valor(texto):
            continue
        tokens.append({
            "texto": texto,
            "x":     dados["left"][i],
            "cy":    dados["top"][i] + dados["height"][i] // 2,
            "conf":  conf,
            "bbox":  (dados["left"][i], dados["top"][i], dados["width"][i], dados["height"][i]),
        })
    return tokens


def _dedup_tokens(tokens, medh):
    """
    Remove quase-duplicatas — a mesma palavra detectada por mais de um passe
    PSM. Mantém a leitura de MAIOR confiança quando dois tokens caem na mesma
    posição (X e Y próximos). Sem isso, a categoria viria com texto repetido.
    """
    tokens = sorted(tokens, key=lambda t: -t["conf"])
    unicos = []
    for t in tokens:
        if any(abs(t["cy"] - u["cy"]) <= medh * 0.6 and abs(t["x"] - u["x"]) <= medh * 0.8
               for u in unicos):
            continue
        unicos.append(t)
    return unicos


def _agrupar_por_y(tokens, medh):
    """
    Agrupa tokens em linhas visuais pela coordenada Y — NÃO pelo line_num do
    Tesseract, que é instável no psm 11. Abre uma nova linha quando o salto de Y
    entre tokens consecutivos passa de ~0.7 da altura mediana das letras. Como a
    associação categoria↔valor é por banda, a categoria que quebra em 2 linhas
    vira 2 linhas visuais e ambas são atribuídas ao mesmo valor.
    """
    toks = sorted(tokens, key=lambda t: t["cy"])
    if not toks:
        return []
    thr = medh * 0.7
    grupos = [[toks[0]]]
    for t in toks[1:]:
        if t["cy"] - grupos[-1][-1]["cy"] <= thr:
            grupos[-1].append(t)
        else:
            grupos.append([t])
    linhas = []
    for ws in grupos:
        ws = sorted(ws, key=lambda w: w["x"])
        cy = sum(w["cy"] for w in ws) / len(ws)
        linhas.append({"cy": cy, "tokens": ws})
    linhas.sort(key=lambda l: l["cy"])
    return linhas


def processar_imagem(imagem):
    """
    Extrai pares (categoria, valor) da tabela por GEOMETRIA, sem confiar na
    análise de layout do Tesseract (instável — às vezes descarta linhas):

    1. Roda dois passes PSM (6 e 11) e UNE os tokens — recall do esparso (11) +
       leitura limpa do bloco (6). Ver _PSMS.
    2. Remove duplicatas entre passes (_dedup_tokens).
    3. Determina o X de corte entre as colunas (meio do vão categoria↔valor).
    4. Agrupa cada coluna em linhas visuais por Y (_agrupar_por_y).
    5. Associa categoria↔valor por proximidade vertical (banda), cobrindo a
       categoria que quebra em 2 linhas (comum no zoom 110%).

    Valores garbled / de confiança baixa são re-lidos da célula ampliada.
    """
    palavras = []
    for psm in _PSMS:
        palavras += _extrair_tokens(imagem, psm)
    if not palavras:
        return []

    # Altura mediana das letras — escala de referência p/ agrupar e deduplicar.
    medh = max(1, sorted(w["bbox"][3] for w in palavras)[len(palavras) // 2])
    palavras = _dedup_tokens(palavras, medh)

    # X de corte entre as colunas. Os valores são alinhados à direita, então o
    # X ESQUERDO deles varia com a largura (ex: "1.076,50" começa mais à esquerda
    # que "22,00") — usar a mediana desse X derrubava valores largos para o lado
    # da categoria. Em vez disso, corta no MEIO do espaço em branco entre a borda
    # direita da categoria e a borda esquerda da coluna de valores.
    monetarios = [w for w in palavras if _RE_VALOR.fullmatch(w["texto"])]
    if not monetarios:
        # Nenhum valor saiu limpo (todos garbled). Usa as células com cara de
        # valor na metade direita como âncora de coluna, para não perder a
        # captura inteira (antes retornava [] → popup com "tudo zerado").
        meio = imagem.width / 2
        monetarios = [w for w in palavras
                      if _eh_celula_valor(w["texto"]) and w["x"] >= meio]
    if not monetarios:
        return []
    val_left = min(w["x"] for w in monetarios)
    cat_rights = [w["x"] + w["bbox"][2] for w in palavras if w["x"] + w["bbox"][2] <= val_left]
    split_x = (max(cat_rights) + val_left) / 2 if cat_rights else val_left - 10

    # Separa as duas colunas pelo X de corte
    esq_tokens = [w for w in palavras if w["x"] <  split_x]
    dir_tokens = [w for w in palavras if w["x"] >= split_x]
    if not dir_tokens:
        return []

    val_linhas = _agrupar_por_y(dir_tokens, medh)
    cat_linhas = _agrupar_por_y(esq_tokens, medh)

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
