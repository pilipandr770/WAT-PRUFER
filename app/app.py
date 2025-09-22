# app/app.py
# Точка входу для flask run: FLASK_APP=app.app:app

from . import create_app

app = create_app()

if __name__ == "__main__":
    # Локальний dev-запуск: python -m app.app
    app.run(host="0.0.0.0", port=5000, debug=True)