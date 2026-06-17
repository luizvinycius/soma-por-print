"""
Suíte de regressão do OCR (soma-por-print).

Roda `processar_imagem` em prints reais versionados (tests/fixtures/) e compara
os totais por categoria com o gabarito. Rode após QUALQUER alteração em
ocr.py / categorias.py para garantir que nenhum print parou de somar certo.

    python tests/test_ocr.py

Os prints aqui são a fonte da verdade — caches de imagem do Claude expiram, então
o material de teste foi versionado de propósito. Para adicionar um caso novo:
salve o print em tests/fixtures/ e acrescente o total esperado em ESPERADO.
"""
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image

from ocr import processar_imagem
from categorias import normalizar_categoria

_FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")

# Totais esperados (credito, debito, pix) por print — conferidos a olho na imagem.
# Lembrete das regras: Caderneta/Delivery, PIX TEF/TEF PIX e Totais são ignorados.
ESPERADO = {
    "1.png": (318.0, 462.0, 0.0),     # baixa resolução (zoom antigo); valores garbled
    "2.png": (306.0, 174.98, 0.0),    # categoria de crédito em 2 linhas
    "3.png": (461.0, 232.0, 0.0),     # psm 6 sozinho descartava 3 das 4 linhas
    "4.png": (461.0, 232.0, 0.0),     # idem 3.png (mesmo caso)
    "5.png": (594.0, 779.0, 82.0),    # 8 linhas, 2 categorias em 2 linhas + PIX Voucher
    "6.png": (222.0, 226.0, 0.0),
    "7.png": (326.99, 118.0, 0.0),    # centavos quebrados (326,99)
    "8.png": (411.0, 243.0, 46.0),    # crédito em 2 linhas + PIX Voucher
    "9.png": (201.0, 335.0, 0.0),     # débito em 2 linhas
    "10.png": (58.0, 283.0, 0.0),
    "11.png": (328.0, 444.0, 28.0),
    "12.png": (106.0, 356.0, 0.0),
    "13.png": (77.0, 337.0, 45.0),    # débito 0,00 em 2 linhas + PIX Voucher
    "14.png": (695.0, 705.0, 0.0),    # crédito 0,00 em 2 linhas; PIX TEF 1.168 (milhar) ignorado
    "15.png": (684.0, 570.0, 0.0),    # 684,00 era lido como 664,00 (autocontraste antes de ampliar)
    "16.png": (94.0, 242.0, 10.0),    # débito em 2 linhas + PIX Voucher
    "17.png": (125.0, 223.0, 0.0),    # crédito 0,00 em 2 linhas
    "18.png": (170.0, 348.96, 0.0),   # tabela longa; várias linhas zeradas no fim
    "19.png": (341.0, 367.0, 222.0),  # "Vale Alimentação (Voucher)" virava pix (era casado por "voucher")
}


def somar(imagem):
    tot = defaultdict(float)
    for cat_texto, valor in processar_imagem(imagem):
        cat = normalizar_categoria(cat_texto)
        if cat:
            tot[cat] += valor
    return (round(tot["credito"], 2), round(tot["debito"], 2), round(tot["pix"], 2))


def main():
    falhas = 0
    for nome, esperado in ESPERADO.items():
        img = Image.open(os.path.join(_FIXTURES, nome))
        obtido = somar(img)
        ok = obtido == esperado
        if not ok:
            falhas += 1
        print(f"{'OK ' if ok else 'XX '} {nome}: obtido={obtido} esperado={esperado}")
    total = len(ESPERADO)
    print(f"\n==== {total - falhas}/{total} OK ====")
    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    main()
