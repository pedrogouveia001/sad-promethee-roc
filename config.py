import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Base configuration."""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///sad_promethee.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # brapi.dev
    BRAPI_TOKEN = os.environ.get('BRAPI_TOKEN', '')
    BRAPI_BASE_URL = os.environ.get('BRAPI_BASE_URL', 'https://brapi.dev/api')

    # Data collection
    COLLECTION_INTERVAL_HOURS = int(os.environ.get('COLLECTION_INTERVAL_HOURS', 24))
    API_RATE_LIMIT_SECONDS = float(os.environ.get('API_RATE_LIMIT_SECONDS', 1.0))

    # Free test tickers (brapi.dev allows these without a token)
    FREE_TEST_TICKERS = ['PETR4', 'MGLU3', 'VALE3', 'ITUB4']


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


config_map = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
}
