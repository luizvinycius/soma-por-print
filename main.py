import sys
import os
import threading
import queue
import ctypes
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Declara DPI-aware antes de qualquer janela para que tkinter e mss
# usem pixels físicos — corrige overlay em monitores com scaling >100%
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # per-monitor DPI aware
except Exception:
    ctypes.windll.user32.SetProcessDPIAware()

_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "debug.log")

def _log(msg):
    with open(_LOG, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now().strftime('%H:%M:%S.%f')} {msg}\n")

import tkinter as tk
import pystray
from pynput import keyboard as kb

from captura import OverlayCaptura
from ocr import processar_imagem
from categorias import normalizar_categoria
from acumulador import acumular, zerar_totais, carregar_totais
from ui import criar_icone, mostrar_popup_totais, mostrar_erro, mostrar_aviso

# Fila de eventos: main thread tkinter consome, threads secundárias produzem
_fila: queue.Queue = queue.Queue()

# Evita capturas simultâneas
_captura_lock = threading.Lock()

# Estado das teclas pressionadas para compor o atalho
_pressionadas: set = set()

# Debounce thread-safe: lock garante que check+update sejam atômicos
_atalho_lock = threading.Lock()
_ultimo_atalho: float = 0.0

# Handle do mutex de instância única — mantido vivo durante todo o processo
# (o Windows libera automaticamente quando o processo encerra)
_mutex_handle = None


def _ja_em_execucao():
    """
    Cria um mutex nomeado do Windows. Se ele já existir, significa que
    outra instância do app está rodando — evita execução dupla, que causava
    dupla contagem nos totais e overlays empilhados.
    """
    global _mutex_handle
    ERROR_ALREADY_EXISTS = 183
    kernel32 = ctypes.windll.kernel32
    _mutex_handle = kernel32.CreateMutexW(None, False, "SomaPorPrint_SingleInstance")
    return kernel32.GetLastError() == ERROR_ALREADY_EXISTS


# ── Normalização e listener de teclado ────────────────────────────────────────

def _normalizar(tecla):
    if tecla in (kb.Key.ctrl_l, kb.Key.ctrl_r):
        return "ctrl"
    if tecla in (kb.Key.alt_l, kb.Key.alt_r):
        return "alt"
    # char fica None quando Ctrl/Alt estão pressionados — verifica vk também
    if hasattr(tecla, "char") and tecla.char in ("p", "P"):
        return "p"
    if hasattr(tecla, "vk") and tecla.vk == 0x50:  # VK_P = 80
        return "p"
    return tecla


def _ao_pressionar(tecla):
    global _ultimo_atalho
    norm = _normalizar(tecla)
    _pressionadas.add(norm)
    _log(f"TECLA DOWN: {tecla!r} -> norm={norm!r} | pressionadas={_pressionadas}")
    if _pressionadas >= {"ctrl", "alt", "p"}:
        agora = time.time()
        with _atalho_lock:
            if agora - _ultimo_atalho <= 0.5:
                _log("ATALHO IGNORADO (debounce)")
                return
            _ultimo_atalho = agora
        _log("ATALHO DETECTADO -> colocando na fila")
        _fila.put(("capturar",))


def _ao_soltar(tecla):
    _pressionadas.discard(_normalizar(tecla))


# ── Tray (roda em thread daemon) ───────────────────────────────────────────────

def _iniciar_tray():
    menu = pystray.Menu(
        pystray.MenuItem("Ver Totais",    lambda: _fila.put(("ver_totais",))),
        pystray.MenuItem("Zerar Totais",  lambda: _fila.put(("zerar_totais",))),
        pystray.MenuItem("Sair",          lambda: _fila.put(("sair",))),
    )
    icone = pystray.Icon("soma_pagamentos", criar_icone(), "Soma por Print", menu)

    def _apos_inicio(icon):
        icon.visible = True  # garante que o ícone seja exibido
        try:
            icon.notify("Use Ctrl+Alt+P para capturar", "Soma por Print iniciado")
        except Exception as e:
            _log(f"notify falhou (ignorado): {e}")

    try:
        icone.run(setup=_apos_inicio)
    except Exception as e:
        _log(f"ERRO no tray: {e}")


# ── Fluxo de captura (etapa 2: OCR + popup, em thread) ───────────────────────

def _processar_captura(root, imagem):
    try:
        pares = processar_imagem(imagem)
    except Exception as e:
        root.after(0, lambda: mostrar_erro(root, f"Falha no OCR:\n{e}"))
        _captura_lock.release()
        return

    _log(f"OCR extraiu {len(pares)} par(es): {pares}")

    novos_valores = {}
    for texto, valor in pares:
        cat = normalizar_categoria(texto)
        _log(f"  '{texto}' -> cat={cat!r} val={valor}")
        if cat:
            novos_valores[cat] = novos_valores.get(cat, 0.0) + valor

    _captura_lock.release()

    if not novos_valores:
        root.after(0, lambda: mostrar_aviso(
            root,
            "Nenhuma categoria reconhecida.\n"
            "Verifique se a área contém a tabela de pagamentos."
        ))
        return

    totais = acumular(novos_valores)
    root.after(0, lambda: mostrar_popup_totais(root, totais, callback_zerar=zerar_totais))


# ── Loop de eventos tkinter (roda no main thread) ─────────────────────────────

def _processar_fila(root):
    try:
        while True:
            msg = _fila.get_nowait()
            acao = msg[0]

            if acao == "capturar":
                _log("FILA: recebeu capturar")
                if _captura_lock.acquire(blocking=False):
                    _log("LOCK adquirido -> abrindo overlay")
                    def _on_captura(img):
                        _log(f"OVERLAY fechado -> img={'capturada' if img else 'None (cancelado)'}")
                        if img is None:
                            _captura_lock.release()
                            return
                        threading.Thread(
                            target=_processar_captura, args=(root, img), daemon=True
                        ).start()
                    OverlayCaptura(root, _on_captura).iniciar()
                    _log("OVERLAY iniciado")
                else:
                    _log("LOCK ocupado -> ignorando captura duplicada")

            elif acao == "ver_totais":
                mostrar_popup_totais(root, carregar_totais(), callback_zerar=zerar_totais)

            elif acao == "zerar_totais":
                zerar_totais()

            elif acao == "sair":
                root.quit()
                return

    except queue.Empty:
        pass

    root.after(100, _processar_fila, root)


# ── Entrada principal ─────────────────────────────────────────────────────────

def main():
    # Impede que o app rode duas vezes ao mesmo tempo
    if _ja_em_execucao():
        _log("INSTÂNCIA JÁ EM EXECUÇÃO — encerrando esta")
        raiz = tk.Tk()
        raiz.withdraw()
        mostrar_aviso(
            raiz,
            "O Soma por Print já está em execução.\n\n"
            "Procure o ícone na bandeja do sistema (canto inferior direito, "
            "pode estar na setinha de ícones ocultos ▲)."
        )
        raiz.destroy()
        return

    root = tk.Tk()
    root.withdraw()  # janela principal oculta — só serve como âncora do event loop

    # Tray em thread daemon
    threading.Thread(target=_iniciar_tray, daemon=True).start()

    # Listener de teclado em thread daemon
    listener = kb.Listener(on_press=_ao_pressionar, on_release=_ao_soltar)
    listener.start()

    _log("APP INICIADO — listener e tray ativos")

    # Inicia o consumidor da fila no main thread
    root.after(100, _processar_fila, root)

    root.mainloop()
    listener.stop()
    _log("APP ENCERRADO")


if __name__ == "__main__":
    main()
