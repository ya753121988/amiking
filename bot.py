import os
import sys
import asyncio
import threading
import random
import string
import requests
from datetime import datetime, timedelta

# --- RENDER ASYNCIO FIX ---
try:
    loop = asyncio.get_event_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo, MenuButtonWebApp
from pyrogram.errors import UserNotParticipant
from flask import Flask, render_template_string, jsonify, request
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient

# ==========================================
# 1. CONFIGURATION
# ==========================================
API_ID = int(os.environ.get("API_ID", 29904834))
API_HASH = os.environ.get("API_HASH", "8b4fd9ef578af114502feeafa2d31938")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8206083172:AAHP9raleY3l2R2HBTGSVCdpcLQvgn960Mw")
MONGO_URI = os.environ.get("MONGO_URI", "mongodb+srv://akash:akash@cluster0.etisrpx.mongodb.net/?appName=Cluster0")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 7120801813))
WEB_URL = os.environ.get("WEB_URL", "https://amiking.onrender.com")

BOT_USERNAME = "PronWaliZone_Bot" # আপনার বটের ইউজারনেম

# --- Webhook Delete For Polling ---
try:
    requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook")
except: pass

# ==========================================
# 2. DATABASE SETUP
# ==========================================
try:
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
    print("✅ Database Connected Successfully!")
except Exception as e:
    print(f"❌ Database Error: {e}")

app = Client("shilacall_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
web = Flask(__name__)
admin_steps = {}

async def get_config():
    conf = await config_col.find_one({"_id": "settings"})
    if not conf:
        conf = {
            "_id": "settings", "ref_coin": 10, "auto_del_time": 0, 
            "ads_on": True, "admin_group": None, "forward_off": True, 
            "pradds": ["1","3","8"], "direk_wait": [5]
        }
        await config_col.insert_one(conf)
    return conf

# ==========================================
# 3. GET ADMIN ID COMMAND (সবার জন্য ওপেন)
# ==========================================
@app.on_message(filters.command("myid") & filters.private)
async def cmd_myid(client, message):
    await message.reply(
        f"👤 **আপনার টেলিগ্রাম আইডি হলো:** `{message.from_user.id}`\n\n"
        f"💡 **নির্দেশনা:** আপনি যদি অ্যাডমিন কমান্ডগুলো ব্যবহার করতে চান, তবে Render-এ গিয়ে `Environment Variables` অপশনে `ADMIN_ID` এর ভ্যালু হিসেবে এই আইডিটি বসিয়ে Save দিন।"
    )

# ==========================================
# 4. USER START & DEEP LINK LOGIC
# ==========================================
@app.on_message(filters.command("start") & filters.private)
async def start_cmd(client, message):
    user_id = message.from_user.id
    args = message.text.split()
    config = await get_config()
    
    # --- 1. MUST JOIN CHANNEL VERIFICATION ---
    channels = await channels_col.find().to_list(100)
    not_joined = []
    for ch in channels:
        try:
            await client.get_chat_member(ch["chat_id"], user_id)
        except UserNotParticipant:
            not_joined.append(ch["link"])
        except: pass

    if not_joined:
        buttons = [[InlineKeyboardButton("📢 Join Channel", url=link)] for link in not_joined]
        buttons.append([InlineKeyboardButton("✅ Joined", callback_data="check_join")])
        return await message.reply("❌ আপনাকে আগে আমাদের মাস্ট চ্যানেলে জয়েন করতে হবে:", reply_markup=InlineKeyboardMarkup(buttons))

    # --- 2. USER REGISTRATION & REFERRAL ---
    user = await users_col.find_one({"_id": user_id})
    if not user:
        await users_col.insert_one({
            "_id": user_id, 
            "name": message.from_user.first_name, 
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

    # --- 3. DEEP LINK: SENDING FILE AFTER AD ---
    if len(args) > 1 and args[1].startswith("file_"):
        file_id = args[1].replace("file_", "")
        file_data = await files_col.find_one({"_id": file_id})
        
        if file_data:
            await files_col.update_one({"_id": file_id}, {"$inc": {"views": 1}})
            prot = config.get("forward_off", True)
            msg = await message.reply("⏳ আপনার ফাইল প্রসেস হচ্ছে...")
            
            sent_file = await client.send_cached_media(
                chat_id=user_id, 
                file_id=file_data["file_id"], 
                caption=f"🎬 **{file_data['title']}**\n\n👁 Views: {file_data.get('views', 0) + 1}", 
                protect_content=prot
            )
            await msg.delete()
            
            del_time = config.get("auto_del_time", 0)
            if del_time > 0:
                await asyncio.sleep(del_time * 60)
                try: await sent_file.delete()
                except: pass
        else:
            await message.reply("❌ ফাইলটি পাওয়া যায়নি!")
        return

    # --- 4. PROFILE GENERATION ---
    is_prem = False
    if user.get("is_premium") and user.get("premium_expiry"):
        if datetime.now() < user["premium_expiry"]:
            is_prem = True
        else:
            await users_col.update_one({"_id": user_id}, {"$set": {"is_premium": False}})

    profile_text = (
        f"👋 **স্বাগতম!**\n\n"
        f"👤 **ইউজার ফুল নাম:** {message.from_user.first_name}\n"
        f"🔗 **ইউজার নাম:** @{message.from_user.username or 'N/A'}\n"
        f"🆔 **ইউজার আইডি:** `{user_id}`\n"
        f"💰 **ইউজার ব্যালেন্স:** {user.get('balance', 0)} Coins\n"
        f"✅ **মাস্ট চ্যানেল জয়েন ভেরিফাই:** Verified\n"
        f"👑 **প্রিমিয়াম:** {'Yes ✅' if is_prem else 'No ❌'}\n\n"
        f"📢 **রেফার লিংক:**\n`https://t.me/{BOT_USERNAME}?start={user_id}`"
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
# 5. TELEGRAPH SCREENSHOT UPLOAD & FILE ADD
# ==========================================
def upload_to_telegraph(file_path):
    try:
        with open(file_path, 'rb') as f:
            res = requests.post('https://telegra.ph/upload', files={'file': ('file.jpg', f, 'image/jpeg')}).json()
        return "https://telegra.ph" + res[0]['src']
    except: return None

@app.on_message(filters.command("new") & filters.user(ADMIN_ID))
async def cmd_new(client, message):
    admin_steps[ADMIN_ID] = {"step": "title"}
    await message.reply("১. ভিডিওর টাইটেল দিন:")

@app.on_message(filters.text & filters.user(ADMIN_ID) & filters.private)
async def handle_admin_text(client, message):
    step = admin_steps.get(ADMIN_ID, {}).get("step")
    if step == "title":
        admin_steps[ADMIN_ID]["title"] = message.text
        admin_steps[ADMIN_ID]["step"] = "category"
        await message.reply("২. ক্যাটাগরির নাম দিন (অথবা All লিখুন):")
    elif step == "category":
        admin_steps[ADMIN_ID]["category"] = message.text
        admin_steps[ADMIN_ID]["step"] = "file"
        await message.reply("৩. এবার ভিডিওটি সেন্ড করুন (অটো স্ক্রিনশট নেওয়া হবে):")

@app.on_message(filters.video & filters.user(ADMIN_ID) & filters.private)
async def handle_admin_video(client, message):
    step = admin_steps.get(ADMIN_ID, {}).get("step")
    if step == "file":
        msg = await message.reply("⏳ স্ক্রিনশট তৈরি করে ডাটাবেসে সেভ করা হচ্ছে...")
        
        short_id = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
        file_id = message.video.file_id
        
        thumb_url = ""
        if message.video.thumbs:
            thumb_path = f"{short_id}.jpg"
            await client.download_media(message.video.thumbs[0].file_id, file_name=thumb_path)
            uploaded_url = await asyncio.to_thread(upload_to_telegraph, thumb_path)
            if uploaded_url: thumb_url = uploaded_url
            try: os.remove(thumb_path)
            except: pass
            
        await files_col.insert_one({
            "_id": short_id,
            "title": admin_steps[ADMIN_ID]["title"], 
            "category": admin_steps[ADMIN_ID]["category"], 
            "file_id": file_id, 
            "thumb_url": thumb_url,
            "views": 0
        })
        del admin_steps[ADMIN_ID]
        await msg.edit_text("✅ ভিডিও ও স্ক্রিনশট সফলভাবে মিনি-অ্যাপে এড হয়েছে!")

# ==========================================
# 6. ALL 30+ ADMIN COMMANDS 
# ==========================================
@app.on_message(filters.command("addchannel") & filters.user(ADMIN_ID))
async def cmd_addchannel(client, message):
    try:
        parts = message.text.split()
        await channels_col.insert_one({"chat_id": int(parts[1]), "link": parts[2]})
        await message.reply("✅ Must Join Channel Added!")
    except: await message.reply("Format: /addchannel -100xxx https://t.me/xyz")

@app.on_message(filters.command("delchannel") & filters.user(ADMIN_ID))
async def cmd_delchannel(client, message):
    chs = await channels_col.find().to_list(100)
    buttons = [[InlineKeyboardButton(f"❌ {c['chat_id']}", callback_data=f"delch_{c['_id']}")] for c in chs]
    await message.reply("ডিলিট করতে ক্লিক করুন:", reply_markup=InlineKeyboardMarkup(buttons) if buttons else None)

@app.on_message(filters.command("adson") & filters.user(ADMIN_ID))
async def cmd_adson(client, message):
    await config_col.update_one({"_id": "settings"}, {"$set": {"ads_on": True}}, upsert=True)
    await message.reply("✅ Ads On (অ্যাড চালু)")

@app.on_message(filters.command("adsoff") & filters.user(ADMIN_ID))
async def cmd_adsoff(client, message):
    await config_col.update_one({"_id": "settings"}, {"$set": {"ads_on": False}}, upsert=True)
    await message.reply("✅ Ads Off (অ্যাড বন্ধ)")

@app.on_message(filters.command("addlink") & filters.user(ADMIN_ID))
async def cmd_addlink(client, message):
    try:
        await links_col.insert_one({"link": message.text.split(" ", 1)[1]})
        await message.reply("✅ Ad Link Added.")
    except: await message.reply("Format: /addlink https://ad.com")

@app.on_message(filters.command("delelink") & filters.user(ADMIN_ID))
async def cmd_delelink(client, message):
    links = await links_col.find().to_list(100)
    buttons = [[InlineKeyboardButton(f"❌ {l['link'][:15]}", callback_data=f"dellink_{l['_id']}")] for l in links]
    await message.reply("Delete Link:", reply_markup=InlineKeyboardMarkup(buttons) if buttons else None)

@app.on_message(filters.command("direkfile") & filters.user(ADMIN_ID))
async def cmd_direkfile(client, message):
    try:
        times_str = message.text.split(" ", 1)[1].replace("s","")
        times = [int(x.strip()) for x in times_str.split(",")]
        await config_col.update_one({"_id": "settings"}, {"$set": {"direk_wait": times}}, upsert=True)
        await message.reply(f"✅ Ad wait times set to: {times} seconds")
    except: await message.reply("Format: /direkfile 1,3,5 s")

@app.on_message(filters.command("adpremiun") & filters.user(ADMIN_ID))
async def cmd_adpremium(client, message):
    try:
        parts = message.text.split()
        uid = int(parts[1])
        days = int(parts[2].replace("day", "").replace("month", "30").replace("year", "365"))
        expiry = datetime.now() + timedelta(days=days)
        await users_col.update_one({"_id": uid}, {"$set": {"is_premium": True, "premium_expiry": expiry}})
        await message.reply(f"✅ User {uid} is Premium for {days} days.")
        try: await app.send_message(uid, f"🎉 আপনাকে {days} দিনের জন্য Premium দেওয়া হয়েছে!")
        except: pass
    except: await message.reply("Format: /adpremiun userid 1day")

@app.on_message(filters.command("delpremiun") & filters.user(ADMIN_ID))
async def cmd_delpremium(client, message):
    try:
        uid = int(message.text.split()[1])
        await users_col.update_one({"_id": uid}, {"$set": {"is_premium": False}})
        await message.reply("✅ Premium removed.")
    except: await message.reply("Format: /delpremiun userid")

@app.on_message(filters.command("addbks") & filters.user(ADMIN_ID))
async def cmd_addbks(client, message):
    try:
        await pkgs_col.insert_one({"type": "bkash", "details": message.text.split(" ", 1)[1]})
        await message.reply("✅ bKash Package Added.")
    except: await message.reply("Format: /addbks 10 day 109 coin")

@app.on_message(filters.command("delbks") & filters.user(ADMIN_ID))
async def cmd_delbks(client, message):
    pkgs = await pkgs_col.find({"type": "bkash"}).to_list(100)
    buttons = [[InlineKeyboardButton(f"❌ {p['details'][:20]}", callback_data=f"delpkg_{p['_id']}")] for p in pkgs]
    await message.reply("Delete bKash Pkg:", reply_markup=InlineKeyboardMarkup(buttons) if buttons else None)

@app.on_message(filters.command("addusd") & filters.user(ADMIN_ID))
async def cmd_addusd(client, message):
    try:
        await pkgs_col.insert_one({"type": "usd", "details": message.text.split(" ", 1)[1]})
        await message.reply("✅ USD Package Added.")
    except: await message.reply("Format: /addusd 10 day 2 usd")

@app.on_message(filters.command("delusd") & filters.user(ADMIN_ID))
async def cmd_delusd(client, message):
    pkgs = await pkgs_col.find({"type": "usd"}).to_list(100)
    buttons = [[InlineKeyboardButton(f"❌ {p['details'][:20]}", callback_data=f"delpkg_{p['_id']}")] for p in pkgs]
    await message.reply("Delete USD Pkg:", reply_markup=InlineKeyboardMarkup(buttons) if buttons else None)

@app.on_message(filters.command("addcata") & filters.user(ADMIN_ID))
async def cmd_addcata(client, message):
    try:
        await cats_col.insert_one({"name": message.text.split(" ", 1)[1]})
        await message.reply("✅ Category Added.")
    except: await message.reply("Format: /addcata Name")

@app.on_message(filters.command("delcata") & filters.user(ADMIN_ID))
async def cmd_delcata(client, message):
    cats = await cats_col.find().to_list(100)
    buttons = [[InlineKeyboardButton(f"❌ {c['name']}", callback_data=f"delcat_{c['_id']}")] for c in cats]
    await message.reply("Delete Category:", reply_markup=InlineKeyboardMarkup(buttons) if buttons else None)

@app.on_message(filters.command("refcine") & filters.user(ADMIN_ID))
async def cmd_refcine(client, message):
    try:
        coins = int(message.text.split()[2])
        await config_col.update_one({"_id": "settings"}, {"$set": {"ref_coin": coins}}, upsert=True)
        await message.reply(f"✅ Ref Bonus Set: {coins} coins")
    except: await message.reply("Format: /refcine 1user 10 coine")

@app.on_message(filters.command("delref") & filters.user(ADMIN_ID))
async def cmd_delref(client, message):
    await config_col.update_one({"_id": "settings"}, {"$set": {"ref_coin": 0}}, upsert=True)
    await message.reply("✅ Ref Bonus Removed (0 coin).")

@app.on_message(filters.command("forward") & filters.user(ADMIN_ID))
async def cmd_forward(client, message):
    try:
        state = message.text.split()[1].lower()
        is_off = state == "off"
        await config_col.update_one({"_id": "settings"}, {"$set": {"forward_off": is_off}}, upsert=True)
        await message.reply(f"✅ Forwarding is {'OFF (Protected)' if is_off else 'ON'}.")
    except: await message.reply("Format: /forward off অথবা on")

@app.on_message(filters.command("setautodel") & filters.user(ADMIN_ID))
async def cmd_autodel(client, message):
    try:
        val = int(message.text.split()[1].replace("munit", "").replace("m", ""))
        await config_col.update_one({"_id": "settings"}, {"$set": {"auto_del_time": val}}, upsert=True)
        await message.reply(f"✅ Auto delete set to {val} mins.")
    except: await message.reply("Format: /setautodel 10munit")

@app.on_message(filters.command("setgroup") & filters.user(ADMIN_ID))
async def cmd_setgrp(client, message):
    try:
        grp = int(message.text.split()[1])
        await config_col.update_one({"_id": "settings"}, {"$set": {"admin_group": grp}}, upsert=True)
        await message.reply(f"✅ Admin group set to {grp}")
    except: await message.reply("Format: /setgroup -100xxx")

@app.on_callback_query(filters.regex(r"^(delcat_|dellink_|delpkg_|delch_)") & filters.user(ADMIN_ID))
async def universal_deleter(client, query):
    from bson.objectid import ObjectId
    action, obj_id = query.data.split("_")
    
    if action == "delcat": await cats_col.delete_one({"_id": ObjectId(obj_id)})
    elif action == "dellink": await links_col.delete_one({"_id": ObjectId(obj_id)})
    elif action == "delpkg": await pkgs_col.delete_one({"_id": ObjectId(obj_id)})
    elif action == "delch": await channels_col.delete_one({"_id": ObjectId(obj_id)})
    
    await query.message.edit_text("✅ ডিলিট সম্পন্ন হয়েছে!")

# ==========================================
# 7. WEB API FOR MINI APP
# ==========================================
@web.route('/api/get_ad/<int:user_id>')
def get_ad_api(user_id):
    config = sync_db["config"].find_one({"_id": "settings"}) or {}
    user = sync_db["users"].find_one({"_id": user_id})
    is_premium = user.get("is_premium", False) if user else False
    
    if config.get("ads_on", True) and not is_premium:
        links = list(sync_db["ad_links"].find())
        if links:
            ad_link = random.choice(links)["link"]
            wait_times = config.get("direk_wait", [5])
            wait_time = random.choice(wait_times)
            return jsonify({"show_ad": True, "ad_link": ad_link, "wait_time": wait_time})
            
    return jsonify({"show_ad": False})

@web.route('/api/buy', methods=['POST'])
def buy_package_api():
    data = request.json
    config = sync_db["config"].find_one({"_id": "settings"}) or {}
    grp = config.get("admin_group")
    
    if grp:
        msg = f"🚨 **New Buy Order!**\n🆔 User ID: `{data['uid']}`\n📦 Package: {data['pkg']}"
        try: app.send_message(grp, msg)
        except: pass
    return jsonify({"status": "success"})


# ==========================================
# 8. SUPER ADVANCED FRONTEND HTML/UI
# ==========================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Viral Video Hub</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        :root { --bg-color: #0f1015; --card-bg: #1c1c24; --text-color: #ffffff; --primary: #ff007f; --secondary: #00d4ff;}
        body { background: var(--bg-color); color: var(--text-color); font-family: sans-serif; margin: 0; padding-bottom: 80px; }
        
        .header { padding: 15px; background: var(--card-bg); border-bottom: 1px solid #333; text-align: center;}
        
        .page { display: none; padding: 15px; }
        .page.active { display: block; }
        
        .cat-scroll { display: flex; overflow-x: auto; gap: 10px; padding-bottom: 10px; margin-bottom: 15px; scrollbar-width: none;}
        .cat-btn { background: #333; padding: 10px 18px; border-radius: 20px; white-space: nowrap; font-size: 13px; font-weight: bold; cursor: pointer;}
        .cat-btn.active { background: var(--primary); color: white; }
        
        .card { background: var(--card-bg); border-radius: 15px; margin-bottom: 25px; overflow: hidden; position: relative; border: 1px solid #333;}
        .card img { width: 100%; height: 220px; object-fit: cover; }
        .card-info { padding: 15px; }
        .play-btn { position: absolute; top: 35%; left: 50%; transform: translate(-50%, -50%); background: rgba(255,0,127,0.8); color: white; padding: 20px 25px; border-radius: 50%; font-size: 24px; cursor: pointer; backdrop-filter: blur(5px);}
        
        .btn { background: var(--primary); color: white; padding: 12px; text-align: center; border-radius: 8px; font-weight: bold; margin-top: 10px; cursor: pointer;}
        .btn-usd { background: var(--secondary); color: black; }
        
        .bottom-nav { position: fixed; bottom: 0; width: 100%; background: var(--card-bg); display: flex; justify-content: space-around; padding: 12px 0; border-top: 1px solid #333; z-index: 100;}
        .nav-item { text-align: center; font-size: 12px; color: gray; cursor: pointer; flex: 1;}
        .nav-item.active { color: var(--primary); }
        .nav-item span { display: block; font-size: 20px; margin-bottom: 5px;}
        
        #ad-overlay { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(15, 16, 21, 0.95); z-index: 999; flex-direction: column; justify-content: center; align-items: center; text-align: center; backdrop-filter: blur(10px);}
        #timer-count { color: var(--primary); font-size: 60px; margin: 10px 0;}
    </style>
</head>
<body>
    <div class="header">
        <b style="font-size: 20px;">🎬 Viral<span style="color: var(--primary)">Video</span></b>
    </div>

    <!-- Ad Timer Overlay -->
    <div id="ad-overlay">
        <h2>Please Wait...</h2>
        <p style="color: gray;">অ্যাডটি দেখুন। ফাইলটি টেলিগ্রামে পাঠানো হচ্ছে</p>
        <h1 id="timer-count">5</h1>
        <p style="color: gray;">সেকেন্ড পর অটোমেটিক ফাইল পাবেন</p>
    </div>

    <!-- HOME PAGE -->
    <div id="page-home" class="page active">
        <div class="cat-scroll">
            <div class="cat-btn active">All Videos</div>
            {% for cat in cats %}
            <div class="cat-btn">{{ cat.name }}</div>
            {% endfor %}
        </div>

        {% for file in files %}
        <div class="card">
            <!-- SAFE IMAGE FALLBACK SYSTEM -->
            {% if file.thumb_url %}
                <img src="{{ file.thumb_url }}" alt="Video">
            {% else %}
                <img src="https://placehold.co/600x400/1c1c24/ff007f?text=No+Thumbnail+Available" alt="Video">
            {% endif %}
            
            <div class="play-btn" onclick="playVideo('{{ file._id }}')">▶</div>
            <div class="card-info">
                <b>{{ file.title }}</b><br>
                <small style="color: gray; display: block; margin-top:5px;">👁 {{ file.views }} views • {{ file.category }}</small>
            </div>
        </div>
        {% else %}
        <p style="text-align:center; color: gray; margin-top: 50px;">কোনো ভিডিও আপলোড করা হয়নি।</p>
        {% endfor %}
    </div>

    <!-- PREMIUM PAGE -->
    <div id="page-premium" class="page">
        <h2 style="color: var(--primary); border-bottom: 1px solid #333; padding-bottom: 10px;">bKash Packages</h2>
        {% for pkg in bkash_pkgs %}
        <div class="card card-info">
            <b style="font-size: 18px;">🟢 {{ pkg.details }}</b>
            <div class="btn" onclick="buyPackage('{{ pkg.details }}')">Buy with bKash</div>
        </div>
        {% endfor %}

        <h2 style="color: var(--secondary); border-bottom: 1px solid #333; padding-bottom: 10px; margin-top: 30px;">USD Packages</h2>
        {% for pkg in usd_pkgs %}
        <div class="card card-info">
            <b style="font-size: 18px;">💲 {{ pkg.details }}</b>
            <div class="btn btn-usd" onclick="buyPackage('{{ pkg.details }}')">Buy with USD</div>
        </div>
        {% endfor %}
    </div>

    <div class="bottom-nav">
        <div class="nav-item active" onclick="switchPage('home', this)">
            <span>🏠</span> Home
        </div>
        <div class="nav-item" onclick="switchPage('premium', this)">
            <span>💎</span> Buy Premium
        </div>
    </div>

    <script>
        let tg = window.Telegram.WebApp;
        tg.expand();
        let botUsername = "{{ bot_username }}";
        let userId = tg.initDataUnsafe.user ? tg.initDataUnsafe.user.id : 0;

        function switchPage(pageId, element) {
            document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
            document.getElementById('page-' + pageId).classList.add('active');
            document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
            element.classList.add('active');
        }

        async function playVideo(fileId) {
            let res = await fetch('/api/get_ad/' + userId);
            let adData = await res.json();
            
            let deepLink = 'https://t.me/' + botUsername + '?start=file_' + fileId;

            if (adData.show_ad) {
                document.getElementById('ad-overlay').style.display = 'flex';
                window.open(adData.ad_link, '_blank');

                let timeLeft = adData.wait_time;
                document.getElementById('timer-count').innerText = timeLeft;

                let timer = setInterval(() => {
                    timeLeft--;
                    document.getElementById('timer-count').innerText = timeLeft;
                    
                    if (timeLeft <= 0) {
                        clearInterval(timer);
                        tg.openTelegramLink(deepLink);
                        setTimeout(() => { tg.close(); }, 500);
                    }
                }, 1000);
            } else {
                tg.openTelegramLink(deepLink);
                setTimeout(() => { tg.close(); }, 500);
            }
        }

        async function buyPackage(pkgDetails) {
            await fetch('/api/buy', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ uid: userId, pkg: pkgDetails })
            });
            tg.showAlert("✅ আপনার রিকোয়েস্ট এডমিনের কাছে পাঠানো হয়েছে।");
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
    return render_template_string(HTML_TEMPLATE, files=files, cats=cats, bkash_pkgs=bkash_pkgs, usd_pkgs=usd_pkgs, bot_username=BOT_USERNAME)

# ==========================================
# 9. RUN SERVERS
# ==========================================
def run_flask(): 
    port = int(os.environ.get("PORT", 8080))
    web.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    app.run()
