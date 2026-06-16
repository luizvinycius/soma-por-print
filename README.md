# 💰 Soma por Print

Aplicação desktop para **Windows** que roda em background e soma valores de tabelas de pagamento direto da tela, via OCR.

Você pressiona um atalho global, seleciona uma área da tela com uma tabela de formas de pagamento, e o app extrai os valores, classifica por categoria (crédito, débito, pix) e **acumula os totais** entre capturas — exibindo o resultado num popup.

---

## ✨ Funcionalidades

- 🎯 **Atalho global** `Ctrl+Alt+P` — funciona mesmo com outras janelas em foco
- ✂️ **Captura interativa** — a tela escurece e você seleciona a área com o mouse (igual ao `Win+Shift+S`)
- 🔍 **OCR por linha** — associa cada categoria ao seu valor pela posição na tabela (via Tesseract)
- 🗂️ **Classificação automática** em `crédito`, `débito` e `pix`, com regras de exclusão
- ➕ **Acumulação persistente** — os totais somam entre capturas e sobrevivem ao fechar/reabrir
- 🖥️ **Ícone na bandeja** com menu (Ver Totais, Zerar Totais, Sair)
- 🔒 **Instância única** — impede execução duplicada que causaria dupla contagem

---

## ⚙️ Como funciona

1. O app fica rodando em background, com um ícone **R$** na bandeja do sistema
2. Você pressiona **`Ctrl+Alt+P`**
3. A tela escurece — selecione a área com a tabela de pagamentos
4. A imagem é processada por OCR e os pares *(categoria → valor)* são extraídos
5. Os valores são classificados, somados aos totais e salvos em `totais.json`
6. Um popup mostra os totais atualizados:

```
✅ Captura registrada

  Credito    R$ 348,00
  Debito     R$ 480,00
  Pix        R$ 226,00
  ──────────────────────
  Total      R$ 1.054,00

  [Zerar Totais]   [Fechar]
```

---

## 📋 Pré-requisitos

- **Windows 10/11**
- **Python 3.x** instalado e no PATH
- **Tesseract OCR** para Windows — baixe em [UB-Mannheim/tesseract](https://github.com/UB-Mannheim/tesseract/wiki)
  - Caminho padrão esperado: `C:\Program Files\Tesseract-OCR\tesseract.exe`
  - Se instalar em outro local, edite a linha `tesseract_cmd` em `ocr.py`

---

## 🚀 Instalação

1. Clone o repositório:
   ```bash
   git clone https://github.com/luizvinycius/soma-por-print.git
   cd soma-por-print
   ```

2. Instale as dependências Python (duplo-clique em **`instalar.bat`** ou rode):
   ```bash
   pip install pytesseract Pillow pynput pystray mss
   ```

3. Instale o **Tesseract OCR** (link acima).

---

## ▶️ Como usar

Duplo-clique em **`iniciar.bat`** (ou rode `pythonw main.py`).

O ícone **R$** aparece na bandeja do sistema. No **Windows 11**, ícones novos costumam ir para a área de ícones ocultos — clique na seta `^` ao lado do relógio e, se quiser, arraste o ícone para fixá-lo na barra.

| Ação | Como |
|---|---|
| Capturar e somar | `Ctrl+Alt+P` → selecione a área |
| Ver os totais atuais | botão direito no ícone → **Ver Totais** |
| Zerar os totais | menu do ícone (ou botão no popup) → **Zerar Totais** |
| Sair | menu do ícone → **Sair** |

---

## 🧾 Regras de classificação

A coluna esquerda da tabela (nome da forma de pagamento) é normalizada em categorias:

| Texto reconhecido (exemplos)              | Categoria   |
|-------------------------------------------|-------------|
| TEF Crédito, Cartão Crédito, Crédito      | `credito`   |
| TEF Débito, Cartão Débito, Débito         | `debito`    |
| PIX (Voucher)                             | `pix`       |
| **PIX TEF (Pix)**                         | *ignorado*  |
| **Totais (R$)** / qualquer linha com "total" | *ignorado* |
| Formas não mapeadas (ex: Caderneta, Delivery) | *ignorado* |

> **Observação:** apenas crédito, débito e pix são contabilizados. Outras formas de pagamento e a linha de totais são ignoradas de propósito — por isso o "Total" do app pode não bater com o "Totais (R$)" impresso na nota.

---

## 📂 Estrutura do projeto

```
soma-por-print/
├── main.py          # entrada: background, atalho global, fila de eventos, tray
├── captura.py       # overlay de seleção de área (snip interativo)
├── ocr.py           # extração e parsing da tabela via pytesseract
├── categorias.py    # mapeamento e normalização de categorias
├── acumulador.py    # leitura/escrita do totais.json
├── ui.py            # popup de resultado e ícone da bandeja
├── instalar.bat     # instala as dependências Python
├── iniciar.bat      # inicia a aplicação
└── totais.json      # gerado automaticamente (persistência dos totais)
```

---

## 🛠️ Stack

`Python` · `pytesseract` (Tesseract OCR) · `Pillow` · `pynput` (atalho global) · `pystray` (bandeja) · `mss` (captura de tela) · `tkinter` (overlay e popups)
