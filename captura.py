import tkinter as tk
from PIL import Image, ImageTk
import mss


class OverlayCaptura:
    """
    Overlay de seleção de área. Roda sobre o root tkinter existente
    (Toplevel) e chama `callback(imagem)` ao finalizar.
    """
    def __init__(self, root, callback):
        self._root = root
        self._callback = callback
        self._ix = self._iy = self._fx = self._fy = 0
        self._rect = None
        self._screenshot = None
        self._tk_fundo = None

    def iniciar(self):
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            raw = sct.grab(monitor)
            self._screenshot = Image.frombytes("RGB", raw.size, raw.rgb)

        top = tk.Toplevel(self._root)
        top.overrideredirect(True)
        top.attributes("-topmost", True)
        top.configure(cursor="crosshair")

        sw = top.winfo_screenwidth()
        sh = top.winfo_screenheight()
        top.geometry(f"{sw}x{sh}+0+0")

        fundo = self._screenshot.copy().convert("RGBA")
        escuro = Image.new("RGBA", fundo.size, (0, 0, 0, 130))
        fundo = Image.alpha_composite(fundo, escuro).convert("RGB")
        self._tk_fundo = ImageTk.PhotoImage(fundo, master=top)

        canvas = tk.Canvas(top, highlightthickness=0, cursor="crosshair")
        canvas.pack(fill=tk.BOTH, expand=True)
        canvas.create_image(0, 0, anchor=tk.NW, image=self._tk_fundo)
        canvas.create_text(sw // 2, 28,
                           text="Selecione a área da tabela. ESC para cancelar.",
                           fill="white", font=("Arial", 13))

        def inicio(ev):
            self._ix, self._iy = ev.x, ev.y
            if self._rect:
                canvas.delete(self._rect)

        def arrastar(ev):
            self._fx, self._fy = ev.x, ev.y
            if self._rect:
                canvas.delete(self._rect)
            self._rect = canvas.create_rectangle(
                self._ix, self._iy, ev.x, ev.y, outline="#FF3333", width=2)

        def soltar(ev):
            self._fx, self._fy = ev.x, ev.y
            x1, y1 = min(self._ix, self._fx), min(self._iy, self._fy)
            x2, y2 = max(self._ix, self._fx), max(self._iy, self._fy)
            imagem = self._screenshot.crop((x1, y1, x2, y2)) if (x2-x1 > 10 and y2-y1 > 10) else None
            top.destroy()
            self._callback(imagem)

        def cancelar(ev=None):
            top.destroy()
            self._callback(None)

        canvas.bind("<ButtonPress-1>",   inicio)
        canvas.bind("<B1-Motion>",        arrastar)
        canvas.bind("<ButtonRelease-1>",  soltar)
        top.bind("<Escape>", cancelar)
