from app import create_app
from app.extensions import db
from app.models import Company, Check, CheckResult
import os

# create app with real integrations enabled
app = create_app()
app.config['TESTING'] = True
app.config['VIES_ENABLED'] = True
app.config['SANCTIONS_EU_ENABLED'] = True
app.config['OPENCORP_ENABLED'] = True
app.config['OPENCORP_API_KEY'] = os.getenv('OPENCORP_API_KEY', '')
app.config['CELERY_TASK_ALWAYS_EAGER'] = True

with app.app_context():
    # make sure DB is fresh in memory
    db.drop_all()
    db.create_all()

    client = app.test_client()
    vat = 'DE811220642'
    data = {
        'vat_number': vat,
        'country': 'DE',
        'requester': {
            'country_code': 'DE',
            'vat_number': 'DE456902445'  # real requester VAT
        }
    }
    resp = client.post('/api/companies/lookup', json=data, follow_redirects=True)
    print('POST /api/companies/lookup status:', resp.status_code)

    company = Company.query.filter_by(vat_number=vat).first()
    if not company:
        print('No company created')
    else:
        print('Company created:', company.vat_number, company.name)
        check = Check.query.filter_by(company_id=company.id).order_by(Check.created_at.desc()).first()
        if not check:
            print('No check created')
        else:
            results = CheckResult.query.filter_by(check_id=check.id).all()
            print('Found', len(results), 'adapter results')
            for r in results:
                print('---', r.adapter_name, r.status)
                # details stored as JSON
                if r.details:
                    print('details keys:', list(r.details.keys()))
                    # print small summary
                    keys = list(r.details.keys())
                    for k in keys[:5]:
                        print('   ', k, ':', r.details.get(k))
