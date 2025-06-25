# bot.py
import os
import requests
import time
import logging
import uuid
import asyncio
import nest_asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from dotenv import load_dotenv

load_dotenv()
nest_asyncio.apply()

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
API_USER = os.getenv("API_USER")
API_PASSWORD = os.getenv("API_PASSWORD")
OWNER_ID = int(os.getenv("OWNER_ID"))
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

TOKEN_URL = "https://auth.contabo.com/auth/realms/contabo/protocol/openid-connect/token"
INSTANCES_URL = "https://api.contabo.com/v1/compute/instances"
REBOOT_URL = "https://api.contabo.com/v1/compute/instances/{}/reboot"

access_token = None
last_token_time = 0
telegram_to_instance = {}

# Logs
logging.basicConfig(level=logging.INFO)

# 🔐 Obtener token
async def get_access_token():
    global access_token, last_token_time
    if access_token and time.time() - last_token_time < 500:
        return access_token

    payload = {
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'username': API_USER,
        'password': API_PASSWORD,
        'grant_type': 'password'
    }
    response = requests.post(TOKEN_URL, data=payload)
    response.raise_for_status()
    access_token = response.json()['access_token']
    last_token_time = time.time()
    return access_token

# 🖥️ Obtener instancias
# 🖥️ Obtener instancias
async def get_instances():
    token = await get_access_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "x-request-id": str(uuid.uuid4()),
        "x-trace-id": str(uuid.uuid4()),
    }

    try:
        response = requests.get(INSTANCES_URL, headers=headers)
        response.raise_for_status()
        data = response.json()
        print("✅ Respuesta completa:", data)
        return data.get("instances", [])
    except requests.exceptions.RequestException as e:
        print("❌ Error al consultar instancias:", e)
        print("❌ Respuesta:", response.text if response else "Sin respuesta")
        return []

# 🔁 Reboot
async def reboot_instance(instance_id):
    token = await get_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    url = REBOOT_URL.format(instance_id)
    response = requests.post(url, headers=headers)
    return response.status_code == 202

# 👤 Registrar usuario
async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("No autorizado.")
        return

    if len(context.args) != 2:
        await update.message.reply_text("Uso: /register <telegram_id> <nombre_vps>")
        return

    telegram_id = int(context.args[0])
    nombre_vps = context.args[1]
    instances = await get_instances()

    for i in instances:
        if i['name'] == nombre_vps:
            telegram_to_instance[telegram_id] = i['instanceId']
            await update.message.reply_text(f"Registrado: {telegram_id} -> {nombre_vps}")
            return

    await update.message.reply_text("No se encontró esa VPS.")

# 🔁 Comando reboot
async def reboot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    instance_id = telegram_to_instance.get(user_id)
    if not instance_id:
        await update.message.reply_text("Tu RDP no está registrada.")
        return

    ok = await reboot_instance(instance_id)
    if ok:
        await update.message.reply_text("Tu RDP está reiniciándose... 🔁")
    else:
        await update.message.reply_text("Error al reiniciar la RDP.")

# 📋 Comando instances
async def instances(update: Update, context: ContextTypes.DEFAULT_TYPE):
    insts = await get_instances()

    if not insts:
        await update.message.reply_text("❌ No se encontraron instancias o hubo un error con la API.")
        return

    msg = "💻 Instancias encontradas:\n\n"
    for inst in insts:
        try:
            msg += f"➡️ {inst['name']} | ID: {inst['instanceId']}\n"
        except Exception as e:
            print("❌ Error al procesar una instancia:", inst)
            print("❌ Excepción:", e)

    await update.message.reply_text(msg)

# 🚀 Iniciar bot
if __name__ == '__main__':
    async def main():
        app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

        app.add_handler(CommandHandler("register", register))
        app.add_handler(CommandHandler("reboot", reboot))
        app.add_handler(CommandHandler("instances", instances))

        await app.bot.delete_webhook(drop_pending_updates=True)
        print("✅ Webhook eliminado")
        print("Bot corriendo...")
        await app.run_polling()

    asyncio.run(main())
