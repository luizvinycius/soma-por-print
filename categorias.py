import re


def normalizar_categoria(texto):
    """
    Normaliza o nome de uma forma de pagamento para uma categoria simples.
    Retorna a categoria ('credito', 'debito', 'pix') ou None se deve ser ignorada.
    """
    t = texto.strip().lower()

    if not t:
        return None

    # Ignora linhas com "total"
    if "total" in t:
        return None

    # "PIX TEF" deve ser ignorado (verificar ANTES do pix genérico)
    if re.search(r"pix\s*tef", t):
        return None

    # Crédito
    if re.search(r"cr[eé]d", t):
        return "credito"

    # Débito
    if re.search(r"d[eé]b", t):
        return "debito"

    # PIX (qualquer variação que não seja PIX TEF — já excluído acima)
    if "pix" in t or "voucher" in t:
        return "pix"

    return None
