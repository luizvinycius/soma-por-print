import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageDraw, ImageFont

_TEXTO_BOTAO_COPIAR = "📋"


def _formatar_reais(valor):
    return "R$ " + f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _formatar_numerico(valor):
    """Valor puro para colar em calculadora: sem separador de milhar, vírgula decimal."""
    return f"{valor:.2f}".replace(".", ",")


def _copiar_para_clipboard(root, texto):
    """
    Copia pelo clipboard do próprio tkinter (~2ms), usando o `root` — que vive
    enquanto o app está na bandeja — e não o popup, que é destruído ao fechar.

    Medido: o `clip.exe` do Windows custava ~310ms sob pythonw (sem console, o
    Windows precisa alocar um) e chegava a segundos com antivírus escaneando o
    processo novo, travando a UI durante a cópia.
    """
    root.clipboard_clear()
    root.clipboard_append(texto)


def criar_icone():
    """Gera ícone para o system tray: cifrão branco sobre fundo verde."""
    img = Image.new("RGB", (64, 64), color=(25, 110, 55))
    draw = ImageDraw.Draw(img)

    # Fonte grande para o cifrão ficar legível mesmo reduzido a 16×16
    fonte = None
    for caminho in (r"C:\Windows\Fonts\arialbd.ttf", r"C:\Windows\Fonts\arial.ttf"):
        try:
            fonte = ImageFont.truetype(caminho, 46)
            break
        except Exception:
            continue

    if fonte is not None:
        # Centraliza o "R$" usando a caixa do texto
        cx, cy = 32, 30
        try:
            l, t, r, b = draw.textbbox((0, 0), "R$", font=fonte)
            draw.text((cx - (r - l) / 2 - l, cy - (b - t) / 2 - t), "R$",
                      fill="white", font=fonte)
        except Exception:
            draw.text((8, 10), "R$", fill="white", font=fonte)
    else:
        draw.rectangle([4, 4, 60, 60], outline="white", width=3)
        draw.text((14, 18), "SP", fill="white")

    return img


def mostrar_popup_totais(root, totais, callback_zerar=None):
    """Abre popup de totais como Toplevel sobre o root existente."""
    top = tk.Toplevel(root)
    top.title("Soma por Print")
    top.resizable(False, False)
    top.attributes("-topmost", True)

    frame = tk.Frame(top, padx=22, pady=16)
    frame.pack(fill=tk.BOTH, expand=True)

    tk.Label(frame, text="✅ Captura registrada", font=("Arial", 11, "bold")).pack(pady=(0, 10))

    def copiar_valor(botao, valor):
        _copiar_para_clipboard(root, _formatar_numerico(valor))
        botao.config(text="✓")
        botao.after(800, lambda: botao.config(text=_TEXTO_BOTAO_COPIAR))

    total_geral = 0.0
    for cat, val in totais.items():
        row = tk.Frame(frame)
        row.pack(fill=tk.X, pady=1)
        tk.Label(row, text=cat.capitalize(), width=10, anchor="w").pack(side=tk.LEFT)
        btn_copiar = tk.Button(row, text=_TEXTO_BOTAO_COPIAR, width=3)
        btn_copiar.config(command=lambda b=btn_copiar, v=val: copiar_valor(b, v))
        btn_copiar.pack(side=tk.RIGHT, padx=(4, 0))
        tk.Label(row, text=_formatar_reais(val), anchor="e").pack(side=tk.RIGHT)
        total_geral += val

    tk.Label(frame, text="─" * 34, fg="#888").pack(pady=3)

    row_t = tk.Frame(frame)
    row_t.pack(fill=tk.X)
    tk.Label(row_t, text="Total", width=10, anchor="w", font=("Arial", 10, "bold")).pack(side=tk.LEFT)
    btn_copiar_total = tk.Button(row_t, text=_TEXTO_BOTAO_COPIAR, width=3)
    btn_copiar_total.config(command=lambda b=btn_copiar_total, v=total_geral: copiar_valor(b, v))
    btn_copiar_total.pack(side=tk.RIGHT, padx=(4, 0))
    tk.Label(row_t, text=_formatar_reais(total_geral), anchor="e", font=("Arial", 10, "bold")).pack(side=tk.RIGHT)

    frame_btns = tk.Frame(frame)
    frame_btns.pack(pady=(14, 0))

    def zerar():
        if callback_zerar:
            callback_zerar()
        top.destroy()

    tk.Button(frame_btns, text="Zerar Totais", command=zerar,      width=13).pack(side=tk.LEFT, padx=5)
    tk.Button(frame_btns, text="Fechar",        command=top.destroy, width=13).pack(side=tk.LEFT, padx=5)

    # Dimensiona pelo conteúdo, só depois de tudo montado: com o DPI awareness
    # do main.py o `tk scaling` passa de 1.6, e tamanho fixo cortava a barra de
    # botões inferior (Zerar/Fechar) para fora da janela
    top.update_idletasks()
    largura, altura = top.winfo_reqwidth(), top.winfo_reqheight()
    x = (top.winfo_screenwidth()  - largura) // 2
    y = (top.winfo_screenheight() - altura)  // 2
    top.geometry(f"{largura}x{altura}+{x}+{y}")


def mostrar_erro(root, mensagem):
    messagebox.showerror("Soma por Print — Erro", mensagem, parent=root)


def mostrar_aviso(root, mensagem):
    messagebox.showwarning("Soma por Print", mensagem, parent=root)
