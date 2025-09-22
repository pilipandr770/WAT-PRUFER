# app/app.wsgi
# WSGI сумісність (наприклад, для gunicorn/uwsgi)
from .app import app as application