# Projeto: soma-por-print

## Contexto

Aplicação desktop para **Windows 10/11** que roda em background. Ao pressionar um atalho global, abre um snip interativo (igual ao `Win+Shift+S`); o usuário seleciona uma área da tela com uma tabela de pagamentos, e o app extrai os valores por categoria via OCR, acumula os totais e exibe um popup com o resultado.

> Este arquivo documenta o **estado atual implementado** do projeto. Ao alterar o código, mantenha este documento em sincronia.

---

## Funcionamento

1. Aplicação fica rodando em background, com ícone **R$** na bandeja do sistema (system tray)
2. Usuário pressiona **`Ctrl+Alt+P`** (atalho global, funciona com qualquer janela em foco)
3. A tela escurece e o usuário seleciona uma área com o mouse (igual ao Snipping Tool); `ESC` cancela
4. Após soltar o mouse, a imagem capturada é processada via OCR
5. O sistema extrai pares de (categoria → valor) da tabela
6. Os valores são classificados, acumulados e salvos em `totais.json`
7. Um popup exibe os totais atualizados de cada categoria

---

## Estrutura da tabela capturada

A tabela tem duas colunas relevantes:
- **Coluna esquerda**: nome da forma de pagamento (ex: "TEF Crédito (Cartão Crédito)")
- **Coluna direita**: valor em reais com vírgula decimal (ex: "95,00")

Exemplo real de uma captura:

```
TEF Crédito (Cartão Crédito)     95,00
TEF Débito (Cartão Débito)      160,00
TEF PIX (Pix)                   113,00
PIX (Voucher)                   130,00
PIX TEF (Pix)                   447,00
Totais (R$)                     945,00   ← IGNORAR esta linha
```

---

## Regras de negócio críticas

### Mapeamento de categorias (`categorias.py`)

Os nomes das formas de pagamento são normalizados para categorias simples:

| Texto no OCR (exemplos)              | Categoria   |
|--------------------------------------|-------------|
| TEF Crédito, Cartão Crédito, Crédito | `credito`   |
| TEF Débito, Cartão Débito, Débito    | `debito`    |
| PIX (Voucher)                        | `pix`       |
| PIX TEF (Pix), TEF PIX (Pix)         | `IGNORAR`   |
| Totais (R$)                          | `IGNORAR`   |
| Qualquer forma não mapeada           | `IGNORAR`   |

### Regras de exclusão (IMPORTANTE)

- **"PIX TEF" e "TEF PIX"** → qualquer linha que contenha **pix + tef** (em qualquer ordem) é completamente ignorada. Verificado **antes** do pix genérico, então só "PIX (Voucher)" e variações sem "tef" contam como `pix`.
- **"Totais (R$)"** ou qualquer linha com "total" → completamente ignorado
- Formas de pagamento fora de crédito/débito/pix (ex: "Caderneta", "Delivery") → **ignoradas de propósito**. Por isso o "Total" do app pode não bater com o "Totais (R$)" da nota.
- Qualquer linha sem valor numérico identificável → ignorada silenciosamente

### Lógica de acumulação (`acumulador.py`)

- Os totais são acumulados entre capturas (sessão do dia)
- Há um botão **Zerar Totais** (no popup e no menu da bandeja) que reseta o `totais.json`
- Os totais persistem em `totais.json` mesmo ao fechar e reabrir o app

---

## Stack tecnológica

- **Linguagem**: Python 3.x
- **OCR**: `pytesseract` + Tesseract instalado no Windows
- **Captura de tela**: `mss` (screenshot) + overlay com `tkinter` (tela escurece, seleção com mouse)
- **Atalho global**: `pynput` (listener de teclado em thread daemon)
- **Processamento de imagem**: `Pillow`
- **System tray**: `pystray`
- **Persistência**: arquivo `totais.json` na mesma pasta do script
- **UI de resultado**: popup `tkinter`

---

## Estrutura de arquivos

```
soma-por-print/
├── main.py          # entrada: background, atalho global, fila de eventos, tray, instância única
├── captura.py       # overlay de snip interativo com tkinter + mss
├── ocr.py           # extração e parsing da tabela via pytesseract
├── categorias.py    # mapeamento e normalização de categorias
├── acumulador.py    # leitura/escrita do totais.json
├── ui.py            # popup de resultado e ícone do system tray
├── instalar.bat     # instala dependências Python com pip
├── iniciar.bat      # inicia o app (pythonw main.py)
├── README.md        # documentação do repositório
├── .gitignore       # ignora runtime e config local
└── totais.json      # gerado automaticamente (ignorado pelo git)
```

Arquivos gerados em runtime e **não versionados** (ver `.gitignore`): `totais.json`, `debug.log`, `stdout.log`, `stderr.log`, `__pycache__/`, `.claude/`.

---

## Dependências Python

Instalar via pip (ou rodar `instalar.bat`):

```
pytesseract
Pillow
pynput
pystray
mss
```

O Tesseract para Windows deve ser baixado de:
https://github.com/UB-Mannheim/tesseract/wiki
(path padrão: `C:\Program Files\Tesseract-OCR\tesseract.exe` — configurado em `ocr.py` via `tesseract_cmd`)

---

## Estratégia de OCR (`ocr.py`)

O OCR usa `pytesseract.image_to_data` para obter a posição (bounding box) de cada palavra, e associa categoria ↔ valor pela geometria — **não** por divisão manual da imagem:

1. Roda `image_to_data` com `--psm 6` (idioma `por`, com fallback sem idioma)
2. Descarta palavras com confiança abaixo de `_CONF_MIN` (20)
3. Agrupa palavras pelas **linhas detectadas pelo próprio Tesseract** (`block_num + par_num + line_num`) — evita misturar texto de linhas diferentes
4. Determina o **X de corte** (`split_x`) pela mediana do X dos tokens com formato monetário
5. Para cada linha: texto à esquerda do corte → categoria; primeiro número à direita → valor

### Parsing de valores (`parsear_valor` / `_RE_VALOR`)

Regex aceita as duas formas brasileiras:
- agrupada por ponto de milhar: `1.234,56`, `12.345,67`
- simples, sem ponto: `95,00`, `1234,56`, `5000,00`

> Crítico: a alternativa "simples" é necessária — sem ela, `5000,00` virava `0.0` e `1234,56` virava `234,56`.

---

## UI do popup de resultado (`ui.py`)

Após cada captura, mostra um popup:

```
✅ Captura registrada

  Credito    R$ 348,00
  Debito     R$ 480,00
  Pix        R$ 226,00
  ──────────────────────
  Total      R$ 1.054,00

  [Zerar Totais]   [Fechar]
```

- **Zerar Totais** reseta o `totais.json` (via `callback_zerar`) e fecha o popup
- **Fechar** apenas fecha o popup

---

## Comportamento do system tray (`ui.py` + `main.py`)

- Ícone **R$** (branco sobre fundo verde) gerado programaticamente com Pillow
- Menu de clique direito:
  - "Ver Totais" → abre o popup com os totais atuais
  - "Zerar Totais" → reseta sem capturar
  - "Sair" → encerra o aplicativo
- No **Windows 11**, ícones novos vão para a área de ícones ocultos (seta `^` ao lado do relógio); o usuário pode arrastar para fixar na barra.

---

## Detalhes de implementação importantes

- **Instância única**: `main.py` cria um mutex nomeado do Windows (`SomaPorPrint_SingleInstance`). Uma 2ª instância detecta o mutex, avisa o usuário e encerra — evita dupla contagem e overlays empilhados.
- **Arquitetura de threads**: tkinter roda o `mainloop` na thread principal (âncora do event loop). Tray (`pystray`) e listener de teclado (`pynput`) rodam em threads daemon. A comunicação é feita por uma `queue.Queue` consumida na thread principal via `root.after`.
- **Debounce do atalho**: protegido por `threading.Lock` para que o check+update do timestamp seja atômico (o `pynput` pode disparar o evento múltiplas vezes).
- **DPI awareness**: declarado no topo do `main.py` para o overlay funcionar em monitores com scaling > 100%.
- **Log**: eventos são gravados em `debug.log` (útil para depurar OCR e fluxo de captura).

---

## Convenções do projeto

- Comentar o código em **português**
- Manter os arquivos `.bat` para instalação/execução sem abrir terminal
- Tratar erros de OCR graciosamente (se não reconhecer nada, avisar sem travar)
- O atalho `Ctrl+Alt+P` deve funcionar globalmente (mesmo com outras janelas em foco)
- Manter este `CLAUDE.md` em sincronia com o código ao fazer alterações
