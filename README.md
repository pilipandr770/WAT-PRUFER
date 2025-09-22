# Company Checker (Flask + Celery)

## Що це
MVP сервіс для перевірки контрагентів: вводиш VAT/назву/сайт — система збирає дані з відкритих джерел (VIES, санкції, insolvency, WHOIS, SSL, Unternehmensregister), зберігає в БД та моніторить зміни.

## Запуск (локально)
```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
set FLASK_APP=app.app:app
flask db init
flask db migrate -m "init"
flask db upgrade
python -m app.app
```

Відкрити: [http://localhost:5000/](http://localhost:5000/)

## Celery (фон)

```bash
celery -A app.app:app.celery_app worker -l info
celery -A app.app:app.celery_app beat -l info
```

## Docker

```bash
docker-compose up --build
```