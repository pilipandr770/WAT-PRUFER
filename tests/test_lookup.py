import pytest
from app import create_app
from app.extensions import db
from app.models import Company, Check, CheckResult

class TestConfig:
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

@pytest.fixture
def app():
    app = create_app()
    app.config.from_object(TestConfig)
    with app.app_context():
        db.drop_all()
        db.create_all()
        yield app

@pytest.fixture
def client(app):
    return app.test_client()

def test_lookup_siements_vat_creates_check_and_results(client, app):
    # This is an integration-style test that requires real VIES integration to be enabled
    if not app.config.get('VIES_ENABLED'):
        pytest.skip('VIES integration not enabled; skip integration test')

    # Use known VAT to exercise real VIES
    vat = "DE811220642"
    data = {"vat_number": vat, "name": "", "country": "DE"}

    resp = client.post('/lookup', data=data, follow_redirects=False)
    assert resp.status_code in (302, 303)

    with app.app_context():
        company = Company.query.filter_by(vat_number=vat).first()
        assert company is not None, "Company row was not created"

        check = Check.query.filter_by(company_id=company.id).order_by(Check.created_at.desc()).first()
        assert check is not None, "Check was not created"

        results = CheckResult.query.filter_by(check_id=check.id).all()
        assert len(results) > 0, "No CheckResult rows created"

        # Find vies result
        vies = next((r for r in results if r.adapter_name == 'vies'), None)
        assert vies is not None, "VIES result missing"
        assert vies.status == 'ok', f"Expected vies status 'ok', got {vies.status}"
