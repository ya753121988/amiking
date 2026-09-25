import os
import asyncio
import threading
import time

# --- RENDER ERROR FIX ---
try:
    loop = asyncio.get_event_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from pyrogram.errors import UserNotParticipant
from flask import Flask, render_template_string, request
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient

# ==========================================
# 1. CONFIGURATION (আপনার ডাটা)
# ==========================================
API_ID = int(os.environ.get("API_ID", 29904834))
API_HASH = os.environ.get("API_HASH", "8b4fd9ef578af114502feeafa2d31938")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8206083172:AAHP9raleY3l2R2HBTGSVCdpcLQvgn960Mw")
MONGO_URI = os.environ.get("MONGO_URI", "mongodb+srv://akash:akash@cluster0.etisrpx.mongodb.net/?appName=Cluster0")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 7120801813))
WEB_URL = os.environ.get("WEB_URL", "https://amiking.onrender.com")
CHANNEL_USERNAME = "YourChannelUsername" # @ ছাড়া দিবেন

# ==========================================
# 2. DATABASE SETUP (Async for Bot, Sync for Web)
# ==========================================
# Bot DB (Async)
db_client = AsyncIOMotorClient(MONGO_URI)
db = db_client["ShilaCallApp"]
users_col = db["users"]
files_col = db["files"]
settings_col = db["settings"]
links_col = db["ad_links"]
cats_col = db["categories"]
pkgs_col = db["packages"]

# Web DB (Sync - to prevent thread crash)
sync_client = MongoClient(MONGO_URI)
sync_db = sync_client["ShilaCallApp"]
sync_pkgs = sync_db["packages"]
sync_files = sync_db["files"]
sync_users = sync_db["users"]

app = Client("shilacall_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
web = Flask(__name__)
admin_steps = {}

# ==========================================
# 3. FORCE SUB & START COMMAND (User Info & Ref)
# ==========================================
async def check_join(user_id):
    try:
        await app.get_chat_member(f"@{CHANNEL_USERNAME}", user_id)
        return True
    except UserNotParticipant:
        return False
    except Exception:
        return True

@app.on_message(filters.command("start") & filters.private)
async def start_cmd(client, message):
    user_id = message.from_user.id
    bot_info = await app.get_me()
    
    # 1. Force Sub
    if not await check_join(user_id):
        btn = InlineKeyboardMarkup([[InlineKeyboardButton("📢 চ্যানেলে জয়েন করুন", url=f"https://t.me/{CHANNEL_USERNAME}")],
                                    [InlineKeyboardButton("✅ জয়েন করেছি", url=f"https://t.me/{bot_info.username}?start=true")]])
        return await message.reply("আমাদের অ্যাপ ব্যবহার করতে আগে চ্যানেলে জয়েন করুন!", reply_markup=btn)

    # 2. Ref System & Save User
    args = message.text.split()
    user = await users_col.find_one({"_id": user_id})
    config = await settings_col.find_one({"_id": "config"}) or {}
    ref_bonus = config.get("ref_coin", 10) # Default 10
    
    if not user:
        await users_col.insert_one({"_id": user_id, "name": message.from_user.first_name, "username": message.from_user.username, "balance": 0, "is_premium": False})
        if len(args) > 1 and args[1].isdigit():
            ref_by = int(args[1])
            if ref_by != user_id and ref_bonus > 0:
                await users_col.update_one({"_id": ref_by}, {"$inc": {"balance": ref_bonus}})
                try:
                    await app.send_message(ref_by, f"🎉 আপনার রেফার লিংক দিয়ে একজন জয়েন করেছে! আপনি {ref_bonus} কয়েন পেয়েছেন।")
                except: pass
        user = await users_col.find_one({"_id": user_id})

    # 3. User Dashboard Text
    ref_link = f"https://t.me/{bot_info.username}?start={user_id}"
    text = (f"👋 স্বাগতম, **{user['name']}**!\n\n"
            f"👤 **নাম:** {user['name']}\n"
            f"🆔 **আইডি:** `{user_id}`\n"
            f"💰 **ব্যালেন্স:** {user.get('balance', 0)} Coins\n"
            f"💎 **প্রিমিয়াম:** {'Yes' if user.get('is_premium') else 'No'}\n\n"
            f"🔗 **আপনার রেফার লিংক:**\n`{ref_link}`\n\n"
            f"প্রতি রেফারে পাবেন {ref_bonus} কয়েন! নিচে ক্লিক করে অ্যাপ ওপেন করুন।")
    
    btn = InlineKeyboardMarkup([[InlineKeyboardButton("🔥 Open Shila Call App", web_app=WebAppInfo(url=f"{WEB_URL}/?uid={user_id}"))]])
    await message.reply(text, reply_markup=btn)

# ==========================================
# 4. ALL 17 ADMIN COMMANDS (এক বিন্দুও বাদ যায়নি)
# ==========================================
# 1. /new (File Upload)
@app.on_message(filters.command("new") & filters.user(ADMIN_ID))
async def cmd_new(client, message):
    admin_steps[ADMIN_ID] = {"step": "name"}
    await message.reply("ফাইলের নাম দিন:")

@app.on_message(filters.text & filters.user(ADMIN_ID))
async def handle_admin_text(client, message):
    step_info = admin_steps.get(ADMIN_ID)
    if step_info and step_info["step"] == "name":
        admin_steps[ADMIN_ID]["name"] = message.text
        admin_steps[ADMIN_ID]["step"] = "file"
        await message.reply("এবার ভিডিও ফাইলটি দিন (বট অটো এড করে নিবে):")

@app.on_message(filters.video & filters.user(ADMIN_ID))
async def handle_admin_video(client, message):
    step_info = admin_steps.get(ADMIN_ID)
    if step_info and step_info["step"] == "file":
        await files_col.insert_one({"name": step_info["name"], "file_id": message.video.file_id, "views": 0, "is_premium": False})
        del admin_steps[ADMIN_ID]
        await message.reply("✅ ফাইল মিনি অ্যাপের হোমপেজে এড হয়ে গেছে!")

# 2-3. Ads On/Off
@app.on_message(filters.command("adson") & filters.user(ADMIN_ID))
async def cmd_adson(client, message):
    await settings_col.update_one({"_id": "config"}, {"$set": {"ads": True}}, upsert=True)
    await message.reply("✅ এডস চালু।")

@app.on_message(filters.command("adsoff") & filters.user(ADMIN_ID))
async def cmd_adsoff(client, message):
    await settings_col.update_one({"_id": "config"}, {"$set": {"ads": False}}, upsert=True)
    await message.reply("❌ এডস বন্ধ।")

# 4. /pradds (Premium Ads config)
@app.on_message(filters.command("pradds") & filters.user(ADMIN_ID))
async def cmd_pradds(client, message):
    val = message.text.split(maxsplit=1)[1]
    await settings_col.update_one({"_id": "config"}, {"$set": {"pradds": val}}, upsert=True)
    await message.reply(f"✅ Premium ad settings saved: {val}")

# 5-6. Premium Management
@app.on_message(filters.command("adpremiun") & filters.user(ADMIN_ID))
async def cmd_adpremium(client, message):
    uid = int(message.text.split()[1])
    await users_col.update_one({"_id": uid}, {"$set": {"is_premium": True}})
    await message.reply(f"✅ User {uid} is Premium now.")

@app.on_message(filters.command("delpremiun") & filters.user(ADMIN_ID))
async def cmd_delpremium(client, message):
    uid = int(message.text.split()[1])
    await users_col.update_one({"_id": uid}, {"$set": {"is_premium": False}})
    await message.reply(f"❌ User {uid} Premium removed.")

# 7-8. Ad Links
@app.on_message(filters.command("addlink") & filters.user(ADMIN_ID))
async def cmd_addlink(client, message):
    await links_col.insert_one({"link": message.text.split(maxsplit=1)[1]})
    await message.reply("✅ Ad Link Added.")

@app.on_message(filters.command("delelink") & filters.user(ADMIN_ID))
async def cmd_delelink(client, message):
    await links_col.delete_many({}) # Example format
    await message.reply("✅ Links Deleted.")

# 9-10. Categories
@app.on_message(filters.command("addcata") & filters.user(ADMIN_ID))
async def cmd_addcata(client, message):
    await cats_col.insert_one({"name": message.text.split(maxsplit=1)[1]})
    await message.reply("✅ Category Added.")

@app.on_message(filters.command("delcata") & filters.user(ADMIN_ID))
async def cmd_delcata(client, message):
    await cats_col.delete_many({})
    await message.reply("✅ Categories Deleted.")

# 11-14. Dynamic Packages (bKash & USD)
@app.on_message(filters.command("addbks") & filters.user(ADMIN_ID))
async def cmd_addbks(client, message):
    pkg_data = message.text.split(maxsplit=1)[1] # Example: 120tk 1000coin
    await pkgs_col.insert_one({"type": "bkash", "details": pkg_data})
    await message.reply("✅ bKash Package Added.")

@app.on_message(filters.command("delbks") & filters.user(ADMIN_ID))
async def cmd_delbks(client, message):
    await pkgs_col.delete_many({"type": "bkash"})
    await message.reply("✅ All bKash Packages Deleted.")

@app.on_message(filters.command("addusd") & filters.user(ADMIN_ID))
async def cmd_addusd(client, message):
    pkg_data = message.text.split(maxsplit=1)[1]
    await pkgs_col.insert_one({"type": "usd", "details": pkg_data})
    await message.reply("✅ USD Package Added.")

@app.on_message(filters.command("delusd") & filters.user(ADMIN_ID))
async def cmd_delusd(client, message):
    await pkgs_col.delete_many({"type": "usd"})
    await message.reply("✅ All USD Packages Deleted.")

# 15. Notification Group Setup
@app.on_message(filters.command("setgroup") & filters.user(ADMIN_ID))
async def cmd_setgroup(client, message):
    grp_id = int(message.text.split()[1])
    await settings_col.update_one({"_id": "config"}, {"$set": {"admin_group": grp_id}}, upsert=True)
    await message.reply(f"✅ Admin Notification Group set to: {grp_id}")

# 16. Referral Settings
@app.on_message(filters.command("refcine") & filters.user(ADMIN_ID))
async def cmd_refcine(client, message):
    coins = int(message.text.split()[1])
    await settings_col.update_one({"_id": "config"}, {"$set": {"ref_coin": coins}}, upsert=True)
    await message.reply(f"✅ Referral bonus set to {coins} coins.")

@app.on_message(filters.command("delref") & filters.user(ADMIN_ID))
async def cmd_delref(client, message):
    await settings_col.update_one({"_id": "config"}, {"$set": {"ref_coin": 0}}, upsert=True)
    await message.reply("❌ Referral bonus disabled.")

# 17-18. Content Protect & Auto Delete
@app.on_message(filters.command("forward") & filters.user(ADMIN_ID))
async def cmd_forward(client, message):
    state = message.text.split()[1].lower()
    protect = True if state == "off" else False
    await settings_col.update_one({"_id": "config"}, {"$set": {"protect": protect}}, upsert=True)
    await message.reply(f"✅ Forwarding is {state.upper()}.")

@app.on_message(filters.command("setautodel") & filters.user(ADMIN_ID))
async def cmd_autodel(client, message):
    mins = int(message.text.split()[1].replace('m', ''))
    await settings_col.update_one({"_id": "config"}, {"$set": {"autodel": mins}}, upsert=True)
    await message.reply(f"✅ Auto Delete set to {mins} mins.")

# ==========================================
# 5. HANDLE WEB APP (BUY NOTIFICATION & FILE SEND)
# ==========================================
async def delete_task(chat_id, msg_id, mins):
    await asyncio.sleep(mins * 60)
    try: await app.delete_messages(chat_id, msg_id)
    except: pass

@app.on_message(filters.service)
async def web_app_handler(client, message):
    if message.web_app_data:
        data = message.web_app_data.data
        uid = message.from_user.id
        config = await settings_col.find_one({"_id": "config"}) or {}
        
        # BUY NOW Logic -> Send to Admin Group
        if data.startswith("buy_"):
            admin_grp = config.get("admin_group")
            if admin_grp:
                text = f"🚨 **New Purchase Request!**\n\n👤 User: {message.from_user.first_name}\n🆔 ID: `{uid}`\n📦 Package: {data.replace('buy_', '')}"
                await app.send_message(admin_grp, text)
            await message.reply("✅ আপনার প্যাকেজ কেনার রিকোয়েস্ট এডমিনের কাছে পাঠানো হয়েছে।")
            return

        # FILE SEND Logic
        protect = config.get("protect", False)
        del_time = config.get("autodel", 0)
        
        # Send video
        msg = await client.send_cached_media(chat_id=uid, file_id=data, protect_content=protect)
        
        # Auto delete
        if del_time > 0:
            asyncio.create_task(delete_task(uid, msg.id, del_time))


# ==========================================
# 6. DYNAMIC WEB APP (HTML + CSS)
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
        body { background: #0f1015; color: white; font-family: sans-serif; margin: 0; padding-bottom: 70px; }
        .header { display: flex; justify-content: space-between; padding: 15px; background: #1c1c1c; border-bottom: 1px solid #333;}
        .coin-box { background: #ffcc00; color: black; padding: 5px 15px; border-radius: 20px; font-weight: bold; }
        .page { display: none; padding: 15px; }
        .page.active { display: block; }
        .card { background: #1c1c24; border-radius: 12px; margin-bottom: 20px; position: relative; padding:10px;}
        .pkg-btn { background: #ff007f; padding: 10px; border-radius: 20px; text-align: center; margin-top: 10px; font-weight: bold;}
        .bottom-nav { position: fixed; bottom: 0; width: 100%; background: #1c1c1c; display: flex; justify-content: space-around; padding: 12px 0; border-top: 1px solid #333;}
        .nav-item { text-align: center; font-size: 11px; color: gray; cursor: pointer; }
        .nav-item.active { color: #ff2a5f; }
        .balance-card { background: linear-gradient(45deg, #ff007f, #7a00ff); border-radius: 15px; padding: 20px; text-align: center; margin-bottom: 20px; }
    </style>
</head>
<body>
    <div class="header">
        <b>Viral <span style="background: #ff2a5f; padding: 2px 5px; border-radius: 5px;">Video</span></b>
        <div class="coin-box">🪙 {{ user_balance }}</div>
    </div>

    <!-- HOME PAGE -->
    <div id="page-home" class="page active">
        <h3>ভিডিও সমূহ</h3>
        {% for file in files %}
        <div class="card" onclick="sendAction('{{ file.file_id }}')">
            <b>{{ file.name }}</b> <br> <small>👁 0 views</small>
            <div class="pkg-btn">Click to View</div>
        </div>
        {% else %}
        <p>No videos uploaded yet.</p>
        {% endfor %}
    </div>

    <!-- BUY COINS PAGE (DYNAMIC PACKAGES) -->
    <div id="page-premium" class="page">
        <h3 style="text-align: center; color: #ff007f;">কয়েন কিনুন (bKash)</h3>
        {% for pkg in bkash_pkgs %}
        <div class="card">
            <b>{{ pkg.details }}</b>
            <div class="pkg-btn" onclick="sendAction('buy_bkash_{{ pkg.details }}')">Buy Now</div>
        </div>
        {% endfor %}
        
        <h3 style="text-align: center; color: #00d4ff; margin-top:20px;">কয়েন কিনুন (USD)</h3>
        {% for pkg in usd_pkgs %}
        <div class="card">
            <b>{{ pkg.details }}</b>
            <div class="pkg-btn" style="background:#00d4ff; color:black;" onclick="sendAction('buy_usd_{{ pkg.details }}')">Buy Now</div>
        </div>
        {% endfor %}
    </div>

    <!-- SETTINGS PAGE -->
    <div id="page-settings" class="page">
        <div class="balance-card">
            <p>আপনার ব্যালেন্স</p>
            <h2>🪙 {{ user_balance }}</h2>
            <p>ID: {{ uid }}</p>
        </div>
        <div class="card">🎁 বন্ধুকে শেয়ার করুন (আপনার রেফার লিংক টেলিগ্রামে দেওয়া হয়েছে)</div>
    </div>

    <div class="bottom-nav">
        <div class="nav-item active" onclick="switchPage('home')">🏠<br>Home</div>
        <div class="nav-item" onclick="switchPage('premium')">💎<br>Buy Coins</div>
        <div class="nav-item" onclick="switchPage('settings')">⚙️<br>Settings</div>
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

        function sendAction(actionData) {
            tg.sendData(actionData);
            tg.close();
        }
    </script>
</body>
</html>
"""

@web.route('/')
def home():
    uid_str = request.args.get('uid')
    uid = int(uid_str) if uid_str and uid_str.isdigit() else 0
    
    # Sync DB fetch for dynamic Web App
    user = sync_users.find_one({"_id": uid}) or {}
    files = list(sync_files.find().sort("_id", -1))
    bkash_pkgs = list(sync_pkgs.find({"type": "bkash"}))
    usd_pkgs = list(sync_pkgs.find({"type": "usd"}))
    
    return render_template_string(HTML_TEMPLATE, 
                                  uid=uid, 
                                  user_balance=user.get("balance", 0),
                                  files=files,
                                  bkash_pkgs=bkash_pkgs, 
                                  usd_pkgs=usd_pkgs)

# ==========================================
# 7. RUN SERVER
# ==========================================
def run_flask():
    web.run(host="0.0.0.0", port=8080)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    app.run()
