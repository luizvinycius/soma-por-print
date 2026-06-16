# Projeto: soma_pagamentos

## Contexto

Preciso de uma aplicação desktop para Windows 10 que roda em background. Quando pressiono um atalho de teclado, ela abre um snip interativo (igual ao Win+Shift+S), eu seleciono uma área da tela com uma tabela de pagamentos, e ela extrai os valores por categoria via OCR, acumula os totais e exibe um popup com o resultado.

---

## Funcionamento esperado

1. Aplicação fica rodando em background (pode aparecer na bandeja do sistema / system tray)
2. Pressiono `Ctrl+Shift+S` (ou outro atalho configurável)
3. A tela escurece e posso selecionar uma área com o mouse (igual ao Snipping Tool)
4. Após soltar o mouse, a imagem capturada é processada via OCR
5. O sistema extrai pares de (categoria → valor) da tabela
6. Os valores são acumulados em um arquivo `totais.json` local
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

### Mapeamento de categorias

Normalize os nomes das formas de pagamento para categorias simples:

| Texto no OCR (exemplos)              | Categoria   |
|--------------------------------------|-------------|
| TEF Crédito, Cartão Crédito, Crédito | `credito`   |
| TEF Débito, Cartão Débito, Débito    | `debito`    |
| PIX (Voucher), TEF PIX (Pix)        | `pix`       |
| PIX TEF (Pix)                        | `IGNORAR`   |
| Totais (R$)                          | `IGNORAR`   |

### Regras de exclusão (IMPORTANTE)

- **"PIX TEF (Pix)"** → deve ser **completamente ignorado**, NÃO soma em nenhuma categoria
- **"Totais (R$)"** ou qualquer linha que contenha "total" → **completamente ignorado**
- Qualquer linha sem valor numérico identificável → ignorar silenciosamente

### Lógica de acumulação

- Os totais são acumulados entre capturas (sessão do dia)
- Deve haver um botão/opção para **zerar os totais** (resetar o JSON)
- Os totais persistem no arquivo `totais.json` mesmo se fechar e reabrir o app

---

## Stack tecnológica

- **Linguagem**: Python (já instalado no sistema)
- **OCR**: `pytesseract` + Tesseract instalado no Windows
- **Captura de tela**: overlay com `tkinter` (tela escurece, usuário seleciona área com mouse)
- **Atalho global**: biblioteca `keyboard`
- **Processamento de imagem**: `Pillow`
- **System tray**: `pystray`
- **Persistência**: arquivo `totais.json` na mesma pasta do script
- **UI de resultado**: popup `tkinter`

---

## Estrutura de arquivos esperada

```
soma_pagamentos/
├── main.py           # entrada principal, roda em background
├── captura.py        # overlay de snip interativo com tkinter
├── ocr.py            # extração e parsing da tabela via pytesseract
├── categorias.py     # mapeamento e normalização de categorias
├── acumulador.py     # leitura/escrita do totais.json
├── ui.py             # popup de resultado e system tray
├── totais.json       # gerado automaticamente, persistência dos totais
├── instalar.bat      # instala dependências Python com pip
└── iniciar.bat       # atalho para rodar o main.py
```

---

## Dependências Python

Instalar via pip:

```
pytesseract
Pillow
keyboard
pystray
mss
```

O Tesseract para Windows deve ser baixado de:
https://github.com/UB-Mannheim/tesseract/wiki
(path padrão: `C:\Program Files\Tesseract-OCR\tesseract.exe`)

---

## Estratégia de OCR para tabela (importante para qualidade)

Não usar OCR na imagem inteira de uma vez. Em vez disso:

1. Dividir a imagem capturada **verticalmente ao meio** (ou em ~60% esquerda / 40% direita)
2. Rodar OCR separadamente em cada metade
3. Zipar os resultados linha a linha para associar categoria ↔ valor
4. Usar `--psm 6` no pytesseract (assume bloco de texto uniforme)
5. Pré-processar a imagem: escala de cinza + threshold para melhorar acurácia

---

## UI do popup de resultado

Após cada captura, mostrar um popup com:

```
✅ Captura registrada

  Crédito    R$ 348,00
  Débito     R$ 480,00
  Pix        R$ 226,00
  ─────────────────────
  Total      R$ 1.054,00

  [Zerar Totais]   [Fechar]
```

- "Zerar Totais" reseta o `totais.json` e fecha o popup
- "Fechar" apenas fecha o popup

---

## Comportamento do system tray

- Ícone simples na bandeja do sistema (pode ser gerado programaticamente com Pillow)
- Menu de clique direito com opções:
  - "Ver Totais" → abre o popup com os totais atuais
  - "Zerar Totais" → reseta sem capturar
  - "Sair" → encerra o aplicativo

---

## Observações finais

- O app deve funcionar no **Windows 10**
- O atalho `Ctrl+Shift+S` deve funcionar globalmente (mesmo com outras janelas em foco)
- Tratar erros de OCR graciosamente (se não reconhecer nada, avisar sem travar)
- Comentar o código em **português**
- Criar os arquivos `.bat` para facilitar instalação e execução sem precisar abrir terminal
