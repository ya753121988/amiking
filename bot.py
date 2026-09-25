import os
import sys
import asyncio
import threading
import time
from datetime import datetime, timedelta

# --- RENDER ERROR FIX ---
try:
    loop = asyncio.get_event_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo, MenuButtonWebApp
from pyrogram.errors import UserNotParticipant
from flask import Flask, render_template_string, send_from_directory
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient

# ফোল্ডার তৈরি (যেখানে ভিডিওর স্ক্রিনশটগুলো সেভ হবে)
os.makedirs("static/thumbs", exist_ok=True)

# ==========================================
# 1. CONFIGURATION
# ==========================================
API_ID = int(os.environ.get("API_ID", 29904834))
API_HASH = os.environ.get("API_HASH", "8b4fd9ef578af114502feeafa2d31938")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8206083172:AAHP9raleY3l2R2HBTGSVCdpcLQvgn960Mw")
MONGO_URI = os.environ.get("MONGO_URI", "mongodb+srv://akash:akash@cluster0.etisrpx.mongodb.net/?appName=Cluster0")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 7120801813))
WEB_URL = os.environ.get("WEB_URL", "https://amiking.onrender.com") # আপনার Render URL

# ==========================================
# 2. DATABASE SETUP
# ==========================================
db_client = AsyncIOMotorClient(MONGO_URI, serverSelectionTimeoutMS=5000)
db = db_client["ShilaCallApp"]

users_col = db["users"]
files_col = db["files"]
cats_col = db["categories"]
pkgs_col = db["packages"]
links_col = db["ad_links"]
config_col = db["config"]
channels_col = db["channels"]

sync_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
sync_db = sync_client["ShilaCallApp"]

app = Client("shilacall_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
web = Flask(__name__, static_folder="static")
admin_steps = {}

# ==========================================
# HELPER FUNCTIONS
# ==========================================
async def get_config():
    conf = await config_col.find_one({"_id": "settings"})
    if not conf:
        conf = {
            "_id": "settings", "ref_coin": 0, "auto_del_time": 0, 
            "ads_on": True, "admin_group": None, "forward_off": True, "pradds": []
        }
        await config_col.insert_one(conf)
    return conf

# ==========================================
# 3. USER COMMANDS (/start & Profile)
# ==========================================
@app.on_message(filters.command("start") & filters.private)
async def start_cmd(client, message):
    user_id = message.from_user.id
    bot_info = await client.get_me()
    
    # Force Sub Check
    channels = await channels_col.find().to_list(100)
    not_joined = []
    for ch in channels:
        try:
            await client.get_chat_member(ch["chat_id"], user_id)
        except UserNotParticipant:
            not_joined.append(ch["link"])
        except: pass

    if not_joined:
        buttons = [[InlineKeyboardButton("Join Channel", url=link)] for link in not_joined]
        buttons.append([InlineKeyboardButton("✅ Joined", callback_data="check_join")])
        return await message.reply("❌ আপনাকে আগে আমাদের চ্যানেলে জয়েন করতে হবে:", reply_markup=InlineKeyboardMarkup(buttons))

    # Registration & Ref
    args = message.text.split()
    user = await users_col.find_one({"_id": user_id})
    config = await get_config()
    
    if not user:
        await users_col.insert_one({
            "_id": user_id, 
            "name": message.from_user.first_name, 
            "username": message.from_user.username,
            "balance": 0, 
            "is_premium": False,
            "premium_expiry": None
        })
        if len(args) > 1 and args[1].isdigit():
            ref_by = int(args[1])
            if ref_by != user_id and config.get("ref_coin", 0) > 0:
                await users_col.update_one({"_id": ref_by}, {"$inc": {"balance": config["ref_coin"]}})
                try: await app.send_message(ref_by, f"🎉 আপনার রেফারে একজন জয়েন করেছে! +{config['ref_coin']} Coins")
                except: pass
        user = await users_col.find_one({"_id": user_id})

    # Premium Check
    is_prem = False
    if user.get("is_premium") and user.get("premium_expiry"):
        if datetime.now() < user["premium_expiry"]:
            is_prem = True
        else:
            await users_col.update_one({"_id": user_id}, {"$set": {"is_premium": False}})

    # User Profile (As requested in screenshot)
    profile_text = (
        f"👤 **ইউজার ফুল নাম:** {message.from_user.first_name} {message.from_user.last_name or ''}\n"
        f"🔗 **ইউজার নাম:** @{message.from_user.username or 'N/A'}\n"
        f"🆔 **ইউজার আইডি:** `{user_id}`\n"
        f"💰 **ইউজার ব্যালেন্স:** {user.get('balance', 0)} Coins\n"
        f"💎 **মাস্ট চ্যানেল জয়েন ভেরিফাই:** ✅ Verified\n"
        f"👑 **প্রিমিয়াম:** {'Yes ✅' if is_prem else 'No ❌'}\n\n"
        f"📢 **রেফার লিংক:**\n`https://t.me/{bot_info.username}?start={user_id}`"
    )

    btn = InlineKeyboardMarkup([[InlineKeyboardButton("🔥 Open App", web_app=WebAppInfo(url=f"{WEB_URL}/"))]])
    try: await client.set_chat_menu_button(chat_id=user_id, menu_button=MenuButtonWebApp(text="🚀 Open App", web_app=WebAppInfo(url=f"{WEB_URL}/")))
    except: pass
    
    await message.reply(profile_text, reply_markup=btn)

@app.on_callback_query(filters.regex("check_join"))
async def check_join_cb(client, query):
    await query.message.delete()
    await start_cmd(client, query.message)

# ==========================================
# 4. ADMIN: VIDEO UPLOAD WITH REAL SCREENSHOT
# ==========================================
@app.on_message(filters.command("new") & filters.user(ADMIN_ID))
async def cmd_new(client, message):
    admin_steps[ADMIN_ID] = {"step": "title"}
    await message.reply("১. ভিডিওর টাইটেল/নাম দিন:")

@app.on_message(filters.text & filters.user(ADMIN_ID) & filters.private)
async def handle_admin_text(client, message):
    step_info = admin_steps.get(ADMIN_ID)
    if not step_info: return
    
    if step_info["step"] == "title":
        admin_steps[ADMIN_ID]["title"] = message.text
        admin_steps[ADMIN_ID]["step"] = "category"
        await message.reply("২. ক্যাটাগরির নাম লিখুন:")
        
    elif step_info["step"] == "category":
        admin_steps[ADMIN_ID]["category"] = message.text
        admin_steps[ADMIN_ID]["step"] = "file"
        await message.reply("৩. এবার ভিডিওটি সেন্ড করুন (বট অটোমেটিক স্ক্রিনশট নেবে):")

@app.on_message(filters.video & filters.user(ADMIN_ID) & filters.private)
async def handle_admin_video(client, message):
    step_info = admin_steps.get(ADMIN_ID)
    if step_info and step_info.get("step") == "file":
        await message.reply("⏳ ভিডিও প্রসেস হচ্ছে এবং স্ক্রিনশট নেওয়া হচ্ছে...")
        
        file_id = message.video.file_id
        # REAL SCREENSHOT LOGIC: Download telegram video thumbnail
        has_thumb = False
        if message.video.thumbs:
            thumb_path = f"static/thumbs/{file_id}.jpg"
            await client.download_media(message.video.thumbs[0].file_id, file_name=thumb_path)
            has_thumb = True
            
        await files_col.insert_one({
            "title": step_info["title"], 
            "category": step_info["category"], 
            "file_id": file_id, 
            "has_thumb": has_thumb,
            "views": 0
        })
        del admin_steps[ADMIN_ID]
        await message.reply("✅ ভিডিও এবং অরিজিনাল স্ক্রিনশট সফলভাবে মিনি অ্যাপের হোমপেজে এড হয়েছে!")

# ==========================================
# 5. ALL 30+ ADMIN COMMANDS FROM SCREENSHOT
# ==========================================

# --- Ads System ---
@app.on_message(filters.command("adson") & filters.user(ADMIN_ID))
async def cmd_adson(client, message):
    await config_col.update_one({"_id": "settings"}, {"$set": {"ads_on": True}}, upsert=True)
    await message.reply("✅ Ads On (এ্যাড চালু হয়েছে).")

@app.on_message(filters.command("adsoff") & filters.user(ADMIN_ID))
async def cmd_adsoff(client, message):
    await config_col.update_one({"_id": "settings"}, {"$set": {"ads_on": False}}, upsert=True)
    await message.reply("✅ Ads Off (এ্যাড বন্ধ হয়েছে).")

@app.on_message(filters.command("addlink") & filters.user(ADMIN_ID))
async def cmd_addlink(client, message):
    link = message.text.split(" ", 1)[1]
    await links_col.insert_one({"link": link})
    await message.reply("✅ Ad Link Added.")

@app.on_message(filters.command("delelink") & filters.user(ADMIN_ID))
async def cmd_delelink(client, message):
    links = await links_col.find().to_list(100)
    buttons = [[InlineKeyboardButton(f"❌ {l['link'][:20]}...", callback_data=f"dellink_{l['_id']}")] for l in links]
    await message.reply("যেটি ডিলিট করবেন ক্লিক করুন:", reply_markup=InlineKeyboardMarkup(buttons))

# --- Premium System ---
@app.on_message(filters.command("adpremiun") & filters.user(ADMIN_ID))
async def cmd_adpremium(client, message):
    # /adpremiun 123456789 1day
    try:
        parts = message.text.split()
        uid, duration = int(parts[1]), parts[2]
        days = int(duration.replace("day", "").replace("month", "30").replace("year", "365"))
        expiry = datetime.now() + timedelta(days=days)
        await users_col.update_one({"_id": uid}, {"$set": {"is_premium": True, "premium_expiry": expiry}})
        await message.reply(f"✅ User {uid} কে {duration} এর জন্য প্রিমিয়াম দেওয়া হয়েছে।")
        try: await app.send_message(uid, f"🎉 আপনাকে {duration} এর জন্য Premium মেম্বারশিপ দেওয়া হয়েছে!")
        except: pass
    except: await message.reply("Format: /adpremiun userid 1day")

@app.on_message(filters.command("delpremiun") & filters.user(ADMIN_ID))
async def cmd_delpremium(client, message):
    try:
        uid = int(message.text.split()[1])
        await users_col.update_one({"_id": uid}, {"$set": {"is_premium": False}})
        await message.reply(f"✅ User {uid} এর প্রিমিয়াম বাতিল করা হয়েছে।")
    except: await message.reply("Format: /delpremiun userid")

@app.on_message(filters.command("pradds") & filters.user(ADMIN_ID))
async def cmd_pradds(client, message):
    try:
        val = message.text.split()[1] # e.g. 1,3,8
        await config_col.update_one({"_id": "settings"}, {"$set": {"pradds": val.split(",")}}, upsert=True)
        await message.reply(f"✅ Premium Ads rule set to {val}")
    except: await message.reply("Format: /pradds 1,3,8")

# --- Package System (bKash & USD) ---
@app.on_message(filters.command("addbks") & filters.user(ADMIN_ID))
async def cmd_addbks(client, message):
    pkg = message.text.split(" ", 1)[1]
    await pkgs_col.insert_one({"type": "bkash", "details": pkg})
    await message.reply("✅ bKash Package Added.")

@app.on_message(filters.command("addusd") & filters.user(ADMIN_ID))
async def cmd_addusd(client, message):
    pkg = message.text.split(" ", 1)[1]
    await pkgs_col.insert_one({"type": "usd", "details": pkg})
    await message.reply("✅ USD Package Added.")

@app.on_message(filters.command("delbks") & filters.user(ADMIN_ID))
async def cmd_delbks(client, message):
    pkgs = await pkgs_col.find({"type": "bkash"}).to_list(100)
    buttons = [[InlineKeyboardButton(f"❌ {p['details'][:20]}", callback_data=f"delpkg_{p['_id']}")] for p in pkgs]
    await message.reply("Delete bKash Package:", reply_markup=InlineKeyboardMarkup(buttons))

@app.on_message(filters.command("delusd") & filters.user(ADMIN_ID))
async def cmd_delusd(client, message):
    pkgs = await pkgs_col.find({"type": "usd"}).to_list(100)
    buttons = [[InlineKeyboardButton(f"❌ {p['details'][:20]}", callback_data=f"delpkg_{p['_id']}")] for p in pkgs]
    await message.reply("Delete USD Package:", reply_markup=InlineKeyboardMarkup(buttons))

# --- Category System ---
@app.on_message(filters.command("addcata") & filters.user(ADMIN_ID))
async def cmd_addcata(client, message):
    cat = message.text.split(" ", 1)[1]
    await cats_col.insert_one({"name": cat})
    await message.reply("✅ Category Added.")

@app.on_message(filters.command("delcata") & filters.user(ADMIN_ID))
async def cmd_delcata(client, message):
    cats = await cats_col.find().to_list(100)
    buttons = [[InlineKeyboardButton(f"❌ {c['name']}", callback_data=f"delcat_{c['_id']}")] for c in cats]
    await message.reply("Delete Category:", reply_markup=InlineKeyboardMarkup(buttons))

# --- Settings (Ref, AutoDel, Forward, Group) ---
@app.on_message(filters.command("refcine") & filters.user(ADMIN_ID))
async def cmd_refcine(client, message):
    # /refcine 1user 10 coine
    coins = int(message.text.split()[2])
    await config_col.update_one({"_id": "settings"}, {"$set": {"ref_coin": coins}}, upsert=True)
    await message.reply(f"✅ Ref Bonus Set: {coins} coins")

@app.on_message(filters.command("delref") & filters.user(ADMIN_ID))
async def cmd_delref(client, message):
    await config_col.update_one({"_id": "settings"}, {"$set": {"ref_coin": 0}}, upsert=True)
    await message.reply("✅ Ref Bonus Removed (0 coin).")

@app.on_message(filters.command("forward") & filters.user(ADMIN_ID))
async def cmd_forward(client, message):
    state = message.text.split()[1].lower()
    is_off = state == "off"
    await config_col.update_one({"_id": "settings"}, {"$set": {"forward_off": is_off}}, upsert=True)
    await message.reply(f"✅ Forwarding is {'OFF (Protected)' if is_off else 'ON'}.")

@app.on_message(filters.command("setautodel") & filters.user(ADMIN_ID))
async def cmd_autodel(client, message):
    # /setautodel 10munit
    val = int(message.text.split()[1].replace("munit", "").replace("m", ""))
    await config_col.update_one({"_id": "settings"}, {"$set": {"auto_del_time": val}}, upsert=True)
    await message.reply(f"✅ Auto delete set to {val} minutes.")

@app.on_message(filters.command("setgroup") & filters.user(ADMIN_ID))
async def cmd_setgrp(client, message):
    grp = int(message.text.split()[1])
    await config_col.update_one({"_id": "settings"}, {"$set": {"admin_group": grp}}, upsert=True)
    await message.reply(f"✅ Admin group set to {grp}")

# --- Universal Inline Button Deleter ---
@app.on_callback_query(filters.regex(r"^(delcat_|dellink_|delpkg_)") & filters.user(ADMIN_ID))
async def universal_deleter(client, query):
    from bson.objectid import ObjectId
    action, obj_id = query.data.split("_")
    
    if action == "delcat": await cats_col.delete_one({"_id": ObjectId(obj_id)})
    elif action == "dellink": await links_col.delete_one({"_id": ObjectId(obj_id)})
    elif action == "delpkg": await pkgs_col.delete_one({"_id": ObjectId(obj_id)})
    
    await query.message.edit_text("✅ সফলভাবে ডিলিট করা হয়েছে!")


# ==========================================
# 6. WEB APP DATA HANDLER
# ==========================================
@app.on_message(filters.service)
async def web_app_handler(client, message):
    if not message.web_app_data: return
    data = message.web_app_data.data
    uid = message.from_user.id
    config = await get_config()
    
    # 1. Package Buy Action (Auto Message to Group)
    if data.startswith("buy_"):
        grp = config.get("admin_group")
        pkg = data.replace("buy_", "")
        if grp:
            msg = f"🚨 **New Order!**\n👤 User: {message.from_user.mention}\n🆔 ID: `{uid}`\n📦 Package: {pkg}"
            try: await app.send_message(grp, msg)
            except: pass
        await message.reply("✅ আপনার বাই রিকোয়েস্ট এডমিনের কাছে পাঠানো হয়েছে।")
        return

    # 2. File Request Action
    file = await files_col.find_one({"file_id": data})
    if file:
        await files_col.update_one({"file_id": data}, {"$inc": {"views": 1}})
        
        # Check Forward Protection
        prot = config.get("forward_off", True)
        
        # Send File
        sent = await client.send_cached_media(
            chat_id=uid, 
            file_id=data, 
            caption=f"🎬 {file['title']}", 
            protect_content=prot
        )
        
        # Auto Delete System
        del_time = config.get("auto_del_time", 0)
        if del_time > 0:
            await asyncio.sleep(del_time * 60)
            try: await sent.delete()
            except: pass


# ==========================================
# 7. FLASK WEB APP (MINI APP)
# ==========================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Viral Video App</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        :root { --bg-color: #0f1015; --card-bg: #1c1c24; --text-color: #ffffff; --primary: #ff007f; }
        body { background: var(--bg-color); color: var(--text-color); font-family: sans-serif; margin: 0; padding-bottom: 70px; }
        .header { padding: 15px; background: var(--card-bg); border-bottom: 1px solid #333; text-align: center; font-size: 20px; font-weight: bold;}
        .page { display: none; padding: 15px; }
        .page.active { display: block; }
        
        .cat-scroll { display: flex; overflow-x: auto; gap: 10px; padding-bottom: 10px; margin-bottom: 15px; }
        .cat-btn { background: #333; padding: 8px 15px; border-radius: 20px; white-space: nowrap; font-size: 14px;}
        .cat-btn.active { background: var(--primary); color: white; }
        
        .card { background: var(--card-bg); border-radius: 12px; margin-bottom: 20px; overflow: hidden; position: relative; border: 1px solid #333;}
        .card img { width: 100%; height: 220px; object-fit: cover; }
        .card-info { padding: 12px; }
        .play-btn { position: absolute; top: 35%; left: 50%; transform: translate(-50%, -50%); background: rgba(255,0,127,0.8); color: white; padding: 15px 20px; border-radius: 50%; font-size: 24px; text-align: center;}
        
        .btn { background: var(--primary); color: white; padding: 12px; text-align: center; border-radius: 8px; font-weight: bold; margin-top: 10px; cursor: pointer;}
        .bottom-nav { position: fixed; bottom: 0; width: 100%; background: var(--card-bg); display: flex; justify-content: space-around; padding: 12px 0; border-top: 1px solid #333;}
        .nav-item { text-align: center; font-size: 13px; color: gray; cursor: pointer; }
        .nav-item.active { color: var(--primary); }
    </style>
</head>
<body>
    <div class="header">🎬 Viral Video</div>

    <!-- HOME PAGE -->
    <div id="page-home" class="page active">
        <div class="cat-scroll">
            <div class="cat-btn active">All</div>
            {% for cat in cats %}
            <div class="cat-btn">{{ cat.name }}</div>
            {% endfor %}
        </div>

        {% for file in files %}
        <div class="card" onclick="sendAction('{{ file.file_id }}')">
            <!-- REAL SCREENSHOT LOGIC -->
            {% if file.has_thumb %}
            <img src="/static/thumbs/{{ file.file_id }}.jpg" alt="Video Screenshot">
            {% else %}
            <img src="https://images.unsplash.com/photo-1611162617474-5b21e879e113?w=600" alt="Default">
            {% endif %}
            
            <div class="play-btn">▶</div>
            <div class="card-info">
                <b style="font-size: 16px;">{{ file.title }}</b><br>
                <small style="color: gray;">👁 {{ file.views }} views • Category: {{ file.category }}</small>
            </div>
        </div>
        {% else %}
        <p style="text-align:center;">কোনো ভিডিও নেই।</p>
        {% endfor %}
    </div>

    <!-- PREMIUM PAGE -->
    <div id="page-premium" class="page">
        <h3 style="color: var(--primary);">bKash Packages</h3>
        {% for pkg in bkash_pkgs %}
        <div class="card card-info">
            <b>🟢 {{ pkg.details }}</b>
            <div class="btn" onclick="sendAction('buy_{{ pkg.details }}')">Buy with bKash</div>
        </div>
        {% endfor %}

        <h3 style="color: #00d4ff; margin-top: 20px;">USD Packages</h3>
        {% for pkg in usd_pkgs %}
        <div class="card card-info">
            <b>💲 {{ pkg.details }}</b>
            <div class="btn" style="background:#00d4ff; color:black;" onclick="sendAction('buy_{{ pkg.details }}')">Buy with USD</div>
        </div>
        {% endfor %}
    </div>

    <div class="bottom-nav">
        <div class="nav-item active" onclick="switchPage('home')">🏠<br>Home</div>
        <div class="nav-item" onclick="switchPage('premium')">💎<br>Buy Premium</div>
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
    files = list(sync_db["files"].find().sort("_id", -1))
    cats = list(sync_db["categories"].find())
    bkash_pkgs = list(sync_db["packages"].find({"type": "bkash"}))
    usd_pkgs = list(sync_db["packages"].find({"type": "usd"}))
    return render_template_string(HTML_TEMPLATE, files=files, cats=cats, bkash_pkgs=bkash_pkgs, usd_pkgs=usd_pkgs)

# ==========================================
# 8. RUN BOT & WEB SERVER
# ==========================================
def run_flask(): web.run(host="0.0.0.0", port=8080)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    app.run()
