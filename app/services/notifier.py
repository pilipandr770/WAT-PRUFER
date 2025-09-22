# app/services/notifier.py
# Повідомлення (заглушки під email/telegram/signal)

def notify_status_change(company_id: int, from_status: str, to_status: str):
    # TODO: підключити email SMTP / Telegram Bot / Signal
    print(f"[NOTIFY] Company {company_id} status changed: {from_status} -> {to_status}")