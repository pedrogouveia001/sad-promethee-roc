from datetime import datetime, timezone
from models import db


class IndicatorDefinition(db.Model):
    """Definition of a financial indicator that can be used as a decision criterion."""
    __tablename__ = 'indicator_definitions'

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), nullable=False, unique=True)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False)  # valuation, rentabilidade, dividendos, endividamento, crescimento
    default_type = db.Column(db.String(10), nullable=False)  # 'cost' or 'benefit'
    description = db.Column(db.Text)
    api_key = db.Column(db.String(100))  # Corresponding key in brapi/yfinance API
    formula = db.Column(db.Text)  # Formula if this is a calculated indicator

    # Relationships
    history = db.relationship('IndicatorHistory', backref='indicator', lazy='dynamic')

    def __repr__(self):
        return f'<Indicator {self.code} ({self.default_type})>'

    def to_dict(self):
        return {
            'id': self.id,
            'code': self.code,
            'name': self.name,
            'category': self.category,
            'default_type': self.default_type,
            'description': self.description,
        }


# Seed data for all supported indicators
INDICATOR_SEED_DATA = [
    # --- Valuation ---
    {
        'code': 'trailing_pe',
        'name': 'P/L (Preço/Lucro)',
        'category': 'valuation',
        'default_type': 'cost',
        'description': 'Quanto o mercado paga por cada R$ de lucro da empresa. Menor indica empresa mais barata.',
        'api_key': 'trailingPE',
    },
    {
        'code': 'price_to_book',
        'name': 'P/VP (Preço/Valor Patrimonial)',
        'category': 'valuation',
        'default_type': 'cost',
        'description': 'Relação entre preço de mercado e valor contábil por ação.',
        'api_key': 'priceToBook',
    },
    {
        'code': 'ev_ebitda',
        'name': 'EV/EBITDA',
        'category': 'valuation',
        'default_type': 'cost',
        'description': 'Valor da firma sobre geração de caixa operacional. Indica quantos anos de geração de caixa para pagar a empresa.',
        'api_key': 'enterpriseToEbitda',
    },
    {
        'code': 'price_to_sales',
        'name': 'PSR (Preço/Receita)',
        'category': 'valuation',
        'default_type': 'cost',
        'description': 'Preço da ação dividido pela receita por ação.',
        'api_key': 'priceToSalesTrailing12Months',
    },
    {
        'code': 'ev_revenue',
        'name': 'EV/Receita',
        'category': 'valuation',
        'default_type': 'cost',
        'description': 'Enterprise Value dividido pela receita total.',
        'api_key': 'enterpriseToRevenue',
    },
    # --- Rentabilidade ---
    {
        'code': 'roe',
        'name': 'ROE (Retorno s/ Patrimônio)',
        'category': 'rentabilidade',
        'default_type': 'benefit',
        'description': 'Retorno sobre patrimônio líquido. Mede a eficiência do capital próprio.',
        'api_key': 'returnOnEquity',
    },
    {
        'code': 'roa',
        'name': 'ROA (Retorno s/ Ativos)',
        'category': 'rentabilidade',
        'default_type': 'benefit',
        'description': 'Retorno sobre ativos totais. Mede a eficiência do uso de todos os ativos.',
        'api_key': 'returnOnAssets',
    },
    {
        'code': 'profit_margin',
        'name': 'Margem Líquida',
        'category': 'rentabilidade',
        'default_type': 'benefit',
        'description': 'Lucro líquido dividido pela receita total.',
        'api_key': 'profitMargins',
    },
    {
        'code': 'ebitda_margin',
        'name': 'Margem EBITDA',
        'category': 'rentabilidade',
        'default_type': 'benefit',
        'description': 'EBITDA dividido pela receita total.',
        'api_key': 'ebitdaMargins',
    },
    {
        'code': 'operating_margin',
        'name': 'Margem Operacional (EBIT)',
        'category': 'rentabilidade',
        'default_type': 'benefit',
        'description': 'EBIT dividido pela receita total.',
        'api_key': 'operatingMargins',
    },
    {
        'code': 'gross_margin',
        'name': 'Margem Bruta',
        'category': 'rentabilidade',
        'default_type': 'benefit',
        'description': 'Lucro bruto dividido pela receita total.',
        'api_key': 'grossMargins',
    },
    # --- Dividendos ---
    {
        'code': 'dividend_yield',
        'name': 'Dividend Yield',
        'category': 'dividendos',
        'default_type': 'benefit',
        'description': 'Dividendos pagos nos últimos 12 meses dividido pelo preço atual da ação.',
        'api_key': 'dividendYield',
    },
    {
        'code': 'payout_ratio',
        'name': 'Payout Ratio',
        'category': 'dividendos',
        'default_type': 'benefit',
        'description': 'Percentual do lucro distribuído como dividendo. Configurável como custo ou benefício.',
        'api_key': 'payoutRatio',
    },
    # --- Endividamento ---
    {
        'code': 'debt_to_equity',
        'name': 'Dívida/Patrimônio',
        'category': 'endividamento',
        'default_type': 'cost',
        'description': 'Dívida total dividida pelo patrimônio líquido. Menor indica menor alavancagem.',
        'api_key': 'debtToEquity',
    },
    {
        'code': 'current_ratio',
        'name': 'Liquidez Corrente',
        'category': 'endividamento',
        'default_type': 'benefit',
        'description': 'Ativo circulante dividido pelo passivo circulante. Maior indica melhor capacidade de pagar dívidas de curto prazo.',
        'api_key': 'currentRatio',
    },
    {
        'code': 'quick_ratio',
        'name': 'Liquidez Seca',
        'category': 'endividamento',
        'default_type': 'benefit',
        'description': 'Liquidez corrente excluindo estoques.',
        'api_key': 'quickRatio',
    },
    # --- Crescimento ---
    {
        'code': 'revenue_growth',
        'name': 'Crescimento de Receita',
        'category': 'crescimento',
        'default_type': 'benefit',
        'description': 'Taxa de crescimento da receita (trimestre/ano vs anterior).',
        'api_key': 'revenueGrowth',
    },
    {
        'code': 'earnings_growth',
        'name': 'Crescimento de Lucro',
        'category': 'crescimento',
        'default_type': 'benefit',
        'description': 'Taxa de crescimento do lucro (trimestre/ano vs anterior).',
        'api_key': 'earningsGrowth',
    },
]
