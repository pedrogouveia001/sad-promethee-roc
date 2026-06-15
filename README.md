# PrometheeInvestor — Sistema de Apoio à Decisão (SAD)

O **PrometheeInvestor** é um Sistema de Apoio à Decisão (SAD) voltado para a análise multicritério e estatística de ativos da bolsa brasileira (B3). O sistema utiliza o método multicritério **PROMETHEE II (Brans & Vincke, 1985)** com pesos baseados no método **ROC (Rank Order Centroid)** como motor matemático e realiza correlações históricas com os preços reais das ações.

---

## 🛠️ Tecnologias Utilizadas

*   **Backend:** Python 3.x com **Flask** (Framework Web), Flask-SQLAlchemy (Mapeamento Objeto-Relacional) e Flask-Migrate (Gerenciamento de Migrações).
*   **Banco de Dados:** SQLite para armazenar dados cadastrais e séries temporais de indicadores e preços.
*   **Integração de Dados:** Coletor automático consumindo a API [brapi.dev](https://brapi.dev/) para cotações e indicadores financeiros em tempo real e históricos.
*   **Frontend:** HTML5, CSS3 personalizado e JavaScript (Vanilla) com **Chart.js** para gráficos interativos (Séries temporais de fluxos líquidos, dispersão e correlação).

---

## 📐 Como Funciona o Motor de Decisão (PROMETHEE II ROC)?

A lógica matemática está implementada na classe `PROMETHEEEngine` em `services/promethee_engine.py`:

### 1. Pesos ROC (Rank Order Centroid)
Os critérios são ordenados por nível de importância pelo usuário no painel interativo. O sistema converte automaticamente essa ordem qualitativa em pesos numéricos rigorosos usando a fórmula ROC:
$$w_i = \frac{1}{N} \sum_{j=i}^{N} \frac{1}{j}$$

### 2. Função de Preferência Linear (Tipo V)
Para cada critério $j$ e para cada período histórico $t$, o sistema calcula a preferência de uma empresa $a$ sobre uma empresa $b$ ($P_j(a, b) \in [0, 1]$) com base na diferença absoluta de seus indicadores $d = x_j(a) - x_j(b)$ (invertido para critérios de custo):
*   Se $d \le 0$: $P_j(a, b) = 0$
*   Se $d > 0$: $P_j(a, b) = \frac{d}{p_j}$, onde o parâmetro $p_j$ (limiar de preferência estrita) é definido dinamicamente como a diferença máxima do indicador entre todas as empresas analisadas no período: $p_j = max(x_j) - min(x_j)$.

### 3. Índice de Preferência Multicritério
Para cada par de alternativas $(a, b)$, calcula-se o índice agregado:
$$\pi(a, b) = \sum_{j=1}^{N} w_j P_j(a, b)$$

### 4. Fluxo Líquido de Preferência $\Phi(a, t)$
Para cada empresa $a$, calcula-se sua força relativa e fraqueza no período:
*   **Fluxo de Saída (Leaving Flow - $\Phi^+$):** $\Phi^+(a) = \frac{1}{M-1} \sum_{b \neq a} \pi(a, b)$ (o quanto $a$ domina as outras)
*   **Fluxo de Entrada (Entering Flow - $\Phi^-$):** $\Phi^-(a) = \frac{1}{M-1} \sum_{b \neq a} \pi(b, a)$ (o quanto $a$ é dominada pelas outras)
*   **Fluxo Líquido (Net Flow - $\Phi$):** $\Phi(a) = \Phi^+(a) - \Phi^-(a)$

O Fluxo Líquido $\Phi(a, t) \in [-1, 1]$ determina o ordenamento completo (PROMETHEE II) e é salvo como o **Valor Global** do ativo para correlações de preços.

---

## 📁 Estrutura de Pastas do Projeto

```text
sad-promethee-roc/
│
├── app.py                # Ponto de entrada (Application Factory do Flask)
├── config.py             # Configurações de desenvolvimento e testes
├── check_db.py           # Status e diagnóstico do banco de dados
├── seed_historical.py    # Script para popular o banco de dados com dados de teste
│
├── models/               # Modelos SQLAlchemy (company, sector, indicator, etc.)
│
├── services/             # Regras de Negócio e Cálculos
│   ├── promethee_engine.py # Implementação matemática do PROMETHEE II ROC
│   ├── statistical_analyzer.py # Correlações de Pearson/Spearman
│   └── data_collector.py   # Coleta de dados via brapi.dev API
│
├── routes/               # Endpoints REST (routes/api.py)
│
└── templates/ & static/  # Interface Visual (HTML/CSS/JS)
```

---

## 🚀 Instalação e Execução

### Passo 1: Configurar Ambiente Virtual
```bash
git clone https://github.com/pedrogouveia001/sad-promethee-roc.git
cd sad-promethee-roc
python -m venv .venv
```

### Passo 2: Ativar o Ambiente Virtual
*   **Windows (PowerShell):** `.venv\Scripts\Activate.ps1`
*   **Linux/macOS:** `source .venv/bin/activate`

### Passo 3: Instalar Dependências e Carga Inicial
```bash
pip install -r requirements.txt
python seed_historical.py
```

### Passo 4: Executar a Aplicação
```bash
python app.py
```
Acesse a aplicação no seu navegador em **`http://localhost:5000`**.
