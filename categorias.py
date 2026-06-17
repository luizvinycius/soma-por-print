import re


def deve_ignorar(texto):
    """
    True se o texto casa uma regra de exclusão EXPLÍCITA (linha de total, ou
    pix + tef em qualquer ordem). Usado para distinguir uma linha que deve ser
    ignorada de propósito de uma que apenas não foi reconhecida (ex: texto
    garbled pelo OCR) — só esta última vale a pena re-ler.
    """
    t = texto.strip().lower()
    if "total" in t:
        return True
    if "pix" in t and "tef" in t:
        return True
    return False


def normalizar_categoria(texto):
    """
    Normaliza o nome de uma forma de pagamento para uma categoria simples.
    Retorna a categoria ('credito', 'debito', 'pix') ou None se deve ser ignorada.
    """
    t = texto.strip().lower()

    if not t:
        return None

    # Regras de exclusão explícitas (total, PIX TEF / TEF PIX) — antes do pix genérico
    if deve_ignorar(t):
        return None

    # Crédito
    if re.search(r"cr[eé]d", t):
        return "credito"

    # Débito
    if re.search(r"d[eé]b", t):
        return "debito"

    # PIX (qualquer variação que não seja PIX TEF — já excluído acima).
    # NÃO casar por "voucher": "PIX (Voucher)" já casa por "pix", enquanto
    # "Vale Alimentação (Voucher)" deve ser ignorado (não é forma mapeada).
    if "pix" in t:
        return "pix"

    return None
