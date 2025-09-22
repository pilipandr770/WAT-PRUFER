# app/services/scheduler.py
# Хуки для періодичних тасків (викликаються Celery beat)

def cron_tick():
    # Викликається із Celery beat, щоб ініціювати daily checks
    return "tick"