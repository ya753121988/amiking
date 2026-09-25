import os
import asyncio
import threading
import time

# ==========================================
# 🔴 RENDER ERROR FIX (Event Loop Fix)
# Pyrogram ইমপোর্ট করার আগে এই কোডটি দিতে হবে
# ==========================================
try:
    loop = asyncio.get_event_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

# এবার বাকি ইমপোর্টগুলো হবে
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from flask import Flask, render_template_string
from motor.motor_asyncio import AsyncIOMotorClient

# ==========================================
# 1. CONFIGURATION (আপনার দেওয়া ইনফো)
# ==========================================
API_ID = int(os.environ.get("API_ID", 29904834))
API_HASH = os.environ.get("API_HASH", "8b4fd9ef578af114502feeafa2d31938")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8206083172:AAHP9raleY3l2R2HBTGSVCdpcLQvgn960Mw")
MONGO_URI = os.environ.get("MONGO_URI", "mongodb+srv://akash:akash@cluster0.etisrpx.mongodb.net/?appName=Cluster0")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 7120801813))
WEB_URL = os.environ.get("WEB_URL", "https://আপনার-ওয়েবসাইটের-লিংক.onrender.com") # অ্যাপ লাইভ করার পর এখানে লিংক দিবেন

# ==========================================
# 2. DATABASE SETUP
# ==========================================
db_client = AsyncIOMotorClient(MONGO_URI)
db = db_client["ShilaCallApp"]
users_col = db["users"]
files_col = db["files"]
settings_col = db["settings"]
links_col = db["ad_links"]
cats_col = db["categories"]

# ==========================================
# 3. BOT & WEB SERVER INIT
# ==========================================
app = Client("shilacall_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
web = Flask(__name__)
admin_steps = {}

# ==========================================
# 4. BOT COMMANDS (USER & ADMIN)
# ==========================================
@app.on_message(filters.command("start") & filters.private)
async def start_cmd(client, message):
    user_id = message.from_user.id
    
    # Save User to Database
    user = await users_col.find_one({"_id": user_id})
    if not user:
        await users_col.insert_one({
            "_id": user_id,
            "name": message.from_user.first_name,
            "username": message.from_user.username,
            "balance": 0,
            "is_premium": False
        })

    btn = InlineKeyboardMarkup([[InlineKeyboardButton("🔥 Open Shila Call App", web_app=WebAppInfo(url=f"{WEB_URL}/?uid={user_id}"))]])
    await message.reply(f"হ্যালো {message.from_user.first_name}! আমাদের মিনি অ্যাপে স্বাগতম।", reply_markup=btn)

@app.on_message(filters.command("new") & filters.user(ADMIN_ID))
async def cmd_new(client, message):
    admin_steps[ADMIN_ID] = {"step": "name"}
    await message.reply("ফাইলের নাম দিন:")

@app.on_message(filters.text & filters.user(ADMIN_ID))
async def handle_admin_text(client, message):
    step_info = admin_steps.get(ADMIN_ID)
    if not step_info:
        return
    if step_info["step"] == "name":
        admin_steps[ADMIN_ID]["name"] = message.text
        admin_steps[ADMIN_ID]["step"] = "file"
        await message.reply("এবার ভিডিও ফাইলটি দিন:")

@app.on_message(filters.video & filters.user(ADMIN_ID))
async def handle_admin_video(client, message):
    step_info = admin_steps.get(ADMIN_ID)
    if step_info and step_info["step"] == "file":
        msg = await message.reply("ফাইল প্রসেস হচ্ছে...")
        file_id = message.video.file_id
        file_name = step_info["name"]
        
        await files_col.insert_one({"name": file_name, "file_id": file_id, "views": 0})
        del admin_steps[ADMIN_ID]
        await msg.edit("✅ ফাইল মিনি অ্যাপের হোমপেজে এড হয়ে গেছে!")

@app.on_message(filters.command("adson") & filters.user(ADMIN_ID))
async def cmd_adson(client, message):
    await settings_col.update_one({"_id": "config"}, {"$set": {"ads": True}}, upsert=True)
    await message.reply("✅ এডস চালু করা হয়েছে।")

@app.on_message(filters.command("adsoff") & filters.user(ADMIN_ID))
async def cmd_adsoff(client, message):
    await settings_col.update_one({"_id": "config"}, {"$set": {"ads": False}}, upsert=True)
    await message.reply("❌ এডস বন্ধ করা হয়েছে।")

@app.on_message(filters.command("adpremiun") & filters.user(ADMIN_ID))
async def cmd_adpremium(client, message):
    try:
        args = message.text.split()
        uid = int(args[1])
        await users_col.update_one({"_id": uid}, {"$set": {"is_premium": True}})
        await message.reply(f"✅ User {uid} কে প্রিমিয়াম দেওয়া হলো।")
    except:
        pass

@app.on_message(filters.command("delpremiun") & filters.user(ADMIN_ID))
async def cmd_delpremium(client, message):
    try:
        uid = int(message.text.split()[1])
        await users_col.update_one({"_id": uid}, {"$set": {"is_premium": False}})
        await message.reply(f"❌ User {uid} আন-প্রিমিয়াম করা হলো।")
    except:
        pass

@app.on_message(filters.service)
async def web_app_data_handler(client, message):
    if message.web_app_data:
        file_id = message.web_app_data.data
        uid = message.from_user.id
        await client.send_cached_media(chat_id=uid, file_id=file_id)

# ==========================================
# 5. MASSIVE WEB APP FRONTEND (FLASK + HTML)
# ==========================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Shila Call</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        body { background-color: #0f1015; color: white; font-family: sans-serif; margin: 0; padding-bottom: 70px; }
        .header { display: flex; justify-content: space-between; padding: 15px; background: #1c1c1c; align-items: center; border-bottom: 1px solid #333;}
        .coin-box { background: #ffcc00; color: black; padding: 5px 15px; border-radius: 20px; font-weight: bold; }
        .page { display: none; padding: 15px; }
        .page.active { display: block; }
        .card { background: #1c1c24; border-radius: 12px; margin-bottom: 20px; overflow: hidden; position: relative; }
        .card img { width: 100%; height: 200px; object-fit: cover; }
        .premium-tag { position: absolute; top: 10px; left: 10px; background: #b026ff; padding: 4px 10px; border-radius: 6px; font-size: 11px; font-weight: bold; }
        .card-title { padding: 12px; font-size: 14px; font-weight: bold; }
        .balance-card { background: linear-gradient(45deg, #ff007f, #7a00ff); border-radius: 15px; padding: 20px; text-align: center; margin-bottom: 20px; }
        .balance-card h2 { margin: 0; font-size: 30px; }
        .menu-item { background: linear-gradient(90deg, #3a2a50, #1f1b2e); margin-bottom: 15px; padding: 15px; border-radius: 10px; display: flex; align-items: center; border: 1px solid #4a3b69;}
        .bottom-nav { position: fixed; bottom: 0; left:0; width: 100%; background: #1c1c1c; display: flex; justify-content: space-around; padding: 12px 0; border-top: 1px solid #333;}
        .nav-item { text-align: center; font-size: 11px; color: gray; cursor: pointer; }
        .nav-item.active { color: #ff2a5f; }
        .nav-icon { font-size: 20px; margin-bottom: 3px; display: block;}
    </style>
</head>
<body>
    <div class="header">
        <b>Viral <span style="background: #ff2a5f; padding: 2px 5px; border-radius: 5px;">Video</span></b>
        <div class="coin-box">🪙 0</div>
    </div>

    <!-- HOME PAGE -->
    <div id="page-home" class="page active">
        <div class="card" onclick="getFile('আপনার_ভিডিও_ফাইল_আইডি')">
            <div class="premium-tag">💎 PREMIUM</div>
            <img src="https://images.unsplash.com/photo-1516259762381-22954d7d3ad2?w=500" alt="Thumb">
            <div class="card-title">নিউ ভাইরাল ভিডিও সেরা সেরা ভিডিও</div>
        </div>
    </div>

    <!-- SETTINGS PAGE -->
    <div id="page-settings" class="page">
        <div class="balance-card">
            <p>আপনার ব্যালেন্স (YOUR BALANCE)</p>
            <h2>🪙 0</h2>
        </div>
        <div class="menu-item">🪙 <span style="margin-left: 10px;">কয়েন কিনুন (Buy Coins)</span></div>
        <div class="menu-item">🎁 <span style="margin-left: 10px;">বন্ধুকে শেয়ার করুন</span></div>
    </div>

    <!-- NAVIGATION -->
    <div class="bottom-nav">
        <div class="nav-item active" onclick="switchPage('home')"><span class="nav-icon">🏠</span>Home</div>
        <div class="nav-item" onclick="switchPage('settings')"><span class="nav-icon">⚙️</span>Settings</div>
    </div>

    <script>
        let tg = window.Telegram.WebApp;
        tg.expand();

        function switchPage(pageId) {
            document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
            document.getElementById('page-' + pageId).classList.add('active');
            document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
            event.currentTarget.classList.add('active');
        }

        function getFile(fileId) {
            tg.sendData(fileId);
        }
    </script>
</body>
</html>
"""

@web.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

def run_flask():
    web.run(host="0.0.0.0", port=8080)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    app.run()
