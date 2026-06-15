"""
PrometheeInvestor — Sistema de Apoio à Decisão para Investimentos na Bolsa Brasileira
Based on the PROMETHEE II multicriteria method with ROC weights
"""

import os
import logging

from flask import Flask, render_template
from flask_cors import CORS
from flask_migrate import Migrate

from config import config_map
from models import db

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
)


def create_app(config_name=None):
    """Application factory."""
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')

    app = Flask(__name__)
    app.config.from_object(config_map.get(config_name, config_map['development']))

    # Extensions
    db.init_app(app)
    Migrate(app, db)
    CORS(app)

    # Register blueprints
    from routes.api import api as api_bp
    app.register_blueprint(api_bp)

    # Frontend routes
    @app.route('/')
    def index():
        return render_template('index.html')

    # Create tables on first run
    with app.app_context():
        db.create_all()
        _seed_indicators(app)

    return app


def _seed_indicators(app):
    """Seed indicator definitions on startup if empty."""
    from models.indicator import IndicatorDefinition, INDICATOR_SEED_DATA

    if IndicatorDefinition.query.count() == 0:
        for ind_data in INDICATOR_SEED_DATA:
            indicator = IndicatorDefinition(**ind_data)
            db.session.add(indicator)
        db.session.commit()
        app.logger.info(f"Seeded {len(INDICATOR_SEED_DATA)} indicator definitions")


# ─── Entry Point ─────────────────────────────────────────────────────

app = create_app()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
