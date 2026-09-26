import os
import sys
import asyncio
import threading
import random
import string
import time
import requests
import json
from datetime import datetime

try:
    loop = asyncio.get_event_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False
    print("⚠️ cv2 (opencv-python-headless) ইনস্টল করা নেই!")

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from pyrogram.errors import UserNotParticipant, FloodWait
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

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "Sudo_king") 
BOT_USERNAME = "PronWaliZone_Bot" 

try: requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook")
except: pass

# ==========================================
# 2. DATABASE SETUP
# ==========================================
db_client = AsyncIOMotorClient(MONGO_URI, serverSelectionTimeoutMS=5000)
db = db_client["ShilaCallApp"]
users_col, files_col, cats_col = db["users"], db["files"], db["categories"]
pkgs_col, links_col, config_col = db["packages"], db["ad_links"], db["config"]
channels_col, coupons_col = db["channels"], db["coupons"]

sync_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
sync_db = sync_client["ShilaCallApp"]

app = Client("shilacall_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
web = Flask(__name__)
admin_steps = {}

async def get_config():
    conf = await config_col.find_one({"_id": "settings"})
    if not conf:
        conf = {"_id": "settings", "ref_coin": 10, "auto_del_time": 0, "ads_on": True, "direk_wait": [5]}
        await config_col.insert_one(conf)
    return conf

not_cmd_filter = filters.create(lambda _, __, message: bool(message.text and not message.text.startswith("/")))

# ==========================================
# 3. USER START & MUST JOIN (BYPASS FIXED)
# ==========================================
@app.on_message(filters.command("start") & filters.private)
async def start_cmd(client, message):
    user_id = message.from_user.id
    args = message.text.split()
    config = await get_config()
    
    user = await users_col.find_one({"_id": user_id})
    if not user:
        await users_col.insert_one({"_id": user_id, "name": message.from_user.first_name, "balance": 0, "pending_file": None})
        if len(args) > 1 and args[1].isdigit():
            ref_by = int(args[1])
            if ref_by != user_id and config.get("ref_coin", 0) > 0:
                await users_col.update_one({"_id": ref_by}, {"$inc": {"balance": config["ref_coin"]}})
                try: await client.send_message(ref_by, f"🎉 আপনার রেফারে একজন জয়েন করেছে! +{config['ref_coin']} Coins")
                except: pass
        user = await users_col.find_one({"_id": user_id})

    # Save pending file if deep linked
    if len(args) > 1 and args[1].startswith("file_"):
        pending_file = args[1].replace("file_", "")
        await users_col.update_one({"_id": user_id}, {"$set": {"pending_file": pending_file}})
        user["pending_file"] = pending_file

    # Must Join Check
    channels = await channels_col.find().to_list(100)
    not_joined = []
    for ch in channels:
        try: await client.get_chat_member(ch["chat_id"], user_id)
        except UserNotParticipant: not_joined.append(ch["link"])
        except: pass

    if not_joined:
        buttons = [[InlineKeyboardButton("📢 Join Channel", url=link)] for link in not_joined]
        buttons.append([InlineKeyboardButton("✅ Joined", callback_data="check_join")])
        return await message.reply("❌ আপনাকে আগে আমাদের চ্যানেলগুলোতে জয়েন করতে হবে:", reply_markup=InlineKeyboardMarkup(buttons))

    # Send pending file after join verification
    if user.get("pending_file"):
        file_id = user["pending_file"]
        await users_col.update_one({"_id": user_id}, {"$set": {"pending_file": None}})
        file_data = await files_col.find_one({"_id": file_id})
        if file_data:
            await files_col.update_one({"_id": file_id}, {"$inc": {"views": 1}})
            msg = await message.reply("⏳ আপনার ভিডিও পাঠানো হচ্ছে...")
            try:
                await client.send_cached_media(chat_id=user_id, file_id=file_data["file_id"], caption=f"🎬 **{file_data['title']}**\n👁 Views: {file_data.get('views', 0) + 1}", protect_content=True)
                await msg.delete()
            except: await msg.edit_text("❌ ফাইল পাঠাতে সমস্যা হয়েছে!")
        else: await message.reply("❌ ফাইলটি পাওয়া যায়নি!")
        return

    profile_text = f"👋 **স্বাগতম Glow Top-এ!**\n\n🆔 **আপনার আইডি:** `{user_id}`\n💰 **আপনার ব্যালেন্স:** {user.get('balance', 0)} Coins\n\nনিচের বাটনে ক্লিক করে অ্যাপ ওপেন করুন 👇"
    btn = InlineKeyboardMarkup([[InlineKeyboardButton("🔥 Open Glow Top", web_app=WebAppInfo(url=f"{WEB_URL}/"))]])
    await message.reply(profile_text, reply_markup=btn)

@app.on_callback_query(filters.regex("check_join"))
async def check_join_cb(client, query):
    user_id = query.from_user.id
    channels = await channels_col.find().to_list(100)
    not_joined = False
    for ch in channels:
        try: await client.get_chat_member(ch["chat_id"], user_id)
        except: not_joined = True; break
    
    if not_joined: return await query.answer("❌ আপনি এখনো সব চ্যানেলে জয়েন করেননি!", show_alert=True)
    await query.message.delete()
    
    class FakeMsg:
        def __init__(self, from_user): self.from_user = from_user; self.text = "/start"
        async def reply(self, *args, **kwargs): return await client.send_message(user_id, *args, **kwargs)
    
    await start_cmd(client, FakeMsg(query.from_user))

# ==========================================
# 4. ADMIN COMMANDS (ALL FIXED)
# ==========================================
@app.on_message(filters.command("myid"))
async def cmd_myid(client, message): await message.reply(f"🆔 আপনার আইডি: `{message.from_user.id}`")

@app.on_message(filters.command("delpost") & filters.user(ADMIN_ID))
async def cmd_delpost(client, message):
    parts = message.text.split()
    if len(parts) > 1:
        res = await files_col.delete_one({"_id": parts[1]})
        if res.deleted_count > 0: await message.reply(f"✅ পোস্ট {parts[1]} ডিলিট হয়েছে!")
        else: await message.reply("❌ পোস্ট পাওয়া যায়নি!")
    else:
        posts = await files_col.find().sort("_id", -1).limit(10).to_list(10)
        text = "📝 **Last 10 Posts:**\n\n"
        for p in posts: text += f"ID: `{p['_id']}` | Title: {p['title'][:15]}\n"
        text += "\nডিলিট করতে লিখুন: `/delpost ID`"
        await message.reply(text)

@app.on_message(filters.command("addchannel") & filters.user(ADMIN_ID))
async def cmd_addchannel(client, message):
    try:
        parts = message.text.split()
        await channels_col.insert_one({"chat_id": int(parts[1]), "link": parts[2]}); await message.reply("✅ Channel Added!")
    except: await message.reply("Format: /addchannel -100xxx https://t.me/xyz")

@app.on_message(filters.command("delchannel") & filters.user(ADMIN_ID))
async def cmd_delchannel(client, message):
    chs = await channels_col.find().to_list(100)
    buttons = [[InlineKeyboardButton(f"❌ {c['chat_id']}", callback_data=f"delch_{c['_id']}")] for c in chs]
    await message.reply("ডিলিট করতে ক্লিক করুন:", reply_markup=InlineKeyboardMarkup(buttons) if buttons else None)

@app.on_callback_query(filters.regex(r"^delch_") & filters.user(ADMIN_ID))
async def delch_cb(client, query):
    from bson.objectid import ObjectId
    await channels_col.delete_one({"_id": ObjectId(query.data.split("_")[1])}); await query.message.edit_text("✅ ডিলিট সম্পন্ন হয়েছে!")

@app.on_message(filters.command("broadcast") & filters.user(ADMIN_ID))
async def cmd_broadcast(client, message):
    if not message.reply_to_message: return await message.reply("❌ কোনো মেসেজ রিপ্লাই করে /broadcast লিখুন।")
    msg = await message.reply("⏳ ব্রডকাস্ট শুরু হয়েছে...")
    users = await users_col.find().to_list(None)
    success = 0
    for u in users:
        try: await message.reply_to_message.copy(u["_id"]); success += 1; await asyncio.sleep(0.05)
        except: pass
    await msg.edit_text(f"✅ ব্রডকাস্ট সম্পন্ন! {success} জনকে পাঠানো হয়েছে।")

@app.on_message(filters.command("addcoupon") & filters.user(ADMIN_ID))
async def cmd_addcoupon(client, message):
    try:
        parts = message.text.split()
        await coupons_col.insert_one({"code": parts[1], "coins": int(parts[2]), "limit": int(parts[3]), "used_by": []})
        await message.reply(f"✅ কুপন অ্যাড হয়েছে: {parts[1]}")
    except: await message.reply("Format: /addcoupon CODE 50 100")

@app.on_message(filters.command("addbks") & filters.user(ADMIN_ID))
async def cmd_addbks(client, message):
    try: await pkgs_col.insert_one({"type": "bkash", "details": message.text.split(" ", 1)[1]}); await message.reply("✅ bKash Package Added.")
    except: pass

@app.on_message(filters.command("addusd") & filters.user(ADMIN_ID))
async def cmd_addusd(client, message):
    try: await pkgs_col.insert_one({"type": "usd", "details": message.text.split(" ", 1)[1]}); await message.reply("✅ USD Package Added.")
    except: pass

@app.on_message(filters.command("addcata") & filters.user(ADMIN_ID))
async def cmd_addcata(client, message):
    try: await cats_col.insert_one({"name": message.text.split(" ", 1)[1]}); await message.reply("✅ Category Added.")
    except: pass

# ==========================================
# 5. UPLOAD POST & SCREENSHOT (DOC/VIDEO FIX)
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

@app.on_message(filters.text & filters.user(ADMIN_ID) & filters.private & not_cmd_filter)
async def handle_admin_text(client, message):
    step = admin_steps.get(ADMIN_ID, {}).get("step")
    if step == "title":
        admin_steps[ADMIN_ID]["title"] = message.text
        admin_steps[ADMIN_ID]["step"] = "category"
        await message.reply("২. ক্যাটাগরির নাম দিন (অথবা All লিখুন):")
    elif step == "category":
        admin_steps[ADMIN_ID]["category"] = message.text
        admin_steps[ADMIN_ID]["step"] = "premium"
        await message.reply("৩. এটি কি প্রিমিয়াম ভিডিও? (yes/no):")
    elif step == "premium":
        admin_steps[ADMIN_ID]["is_premium"] = message.text.lower() == "yes"
        admin_steps[ADMIN_ID]["step"] = "file"
        await message.reply("৪. এবার ভিডিওটি বা ডকুমেন্টটি সেন্ড করুন:")

@app.on_message((filters.video | filters.document) & filters.user(ADMIN_ID) & filters.private)
async def handle_admin_file(client, message):
    step = admin_steps.get(ADMIN_ID, {}).get("step")
    if step == "file":
        msg = await message.reply("⏳ স্ক্রিনশট তৈরি করা হচ্ছে...")
        short_id = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
        file_id = message.video.file_id if message.video else message.document.file_id
        thumb_url = ""

        # Telegram Native Thumb
        if message.video and message.video.thumbs:
            thumb_path = f"{short_id}.jpg"
            await client.download_media(message.video.thumbs[0].file_id, file_name=thumb_path)
            thumb_url = await asyncio.to_thread(upload_to_telegraph, thumb_path)
            try: os.remove(thumb_path)
            except: pass
            
        # CV2 Screenshot from 10th Frame (For Document/Video)
        if not thumb_url and HAS_CV2:
            try:
                video_path = await client.download_media(file_id, file_name=f"{short_id}.mp4")
                cap = cv2.VideoCapture(video_path)
                cap.set(cv2.CAP_PROP_POS_FRAMES, 10)
                ret, frame = cap.read()
                if ret:
                    thumb_path = f"{short_id}_cv2.jpg"
                    cv2.imwrite(thumb_path, frame)
                    thumb_url = await asyncio.to_thread(upload_to_telegraph, thumb_path)
                    try: os.remove(thumb_path)
                    except: pass
                cap.release()
                try: os.remove(video_path)
                except: pass
            except Exception as e: print(f"OpenCV Error: {e}")

        await files_col.insert_one({
            "_id": short_id,
            "title": admin_steps[ADMIN_ID]["title"], 
            "category": admin_steps[ADMIN_ID]["category"], 
            "is_premium": admin_steps[ADMIN_ID]["is_premium"],
            "file_id": file_id, 
            "thumb_url": thumb_url,
            "views": 0
        })
        del admin_steps[ADMIN_ID]
        await msg.edit_text(f"✅ ভিডিও সেভ হয়েছে! Post ID: `{short_id}`")

# ==========================================
# 6. WEB API
# ==========================================
@web.route('/api/get_ad/<int:user_id>')
def get_ad_api(user_id):
    config = sync_db["config"].find_one({"_id": "settings"}) or {}
    if config.get("ads_on", True):
        links = list(sync_db["ad_links"].find())
        if links:
            ad_link = random.choice(links)["link"]
            wait_times = config.get("direk_wait", [5])
            wait_time = random.choice(wait_times)
            return jsonify({"show_ad": True, "ad_link": ad_link, "wait_time": wait_time})
    return jsonify({"show_ad": False})

@web.route('/api/redeem', methods=['POST'])
def redeem_coupon():
    data = request.json
    uid, code = data['uid'], data['code']
    coupon = sync_db["coupons"].find_one({"code": code})
    
    if not coupon: return jsonify({"status": "error", "msg": "Invalid Coupon Code!"})
    if uid in coupon.get("used_by", []): return jsonify({"status": "error", "msg": "You already used this coupon!"})
    if len(coupon.get("used_by", [])) >= coupon.get("limit", 0): return jsonify({"status": "error", "msg": "Coupon limit reached!"})
    
    sync_db["coupons"].update_one({"code": code}, {"$push": {"used_by": uid}})
    sync_db["users"].update_one({"_id": uid}, {"$inc": {"balance": coupon["coins"]}})
    try: asyncio.run_coroutine_threadsafe(app.send_message(uid, f"🎉 কুপন সফলভাবে রিডিম হয়েছে! আপনি পেয়েছেন {coupon['coins']} Coins!"), loop)
    except: pass
    return jsonify({"status": "success", "msg": f"Successfully redeemed {coupon['coins']} coins!"})

@web.route('/api/user/<int:user_id>')
def get_user(user_id):
    user = sync_db["users"].find_one({"_id": user_id})
    return jsonify({"balance": user.get("balance", 0) if user else 0})

# ==========================================
# 7. HTML FRONTEND (Pagination, Search, Premium)
# ==========================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Glow Top</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        body { background: #0b141d; color: #fff; font-family: sans-serif; margin: 0; padding-bottom: 80px; }
        * { box-sizing: border-box; }
        .header { display: flex; justify-content: space-between; padding: 15px; background: rgba(0,0,0,0.3); }
        .coin-pill { background: #ffb703; color: #000; padding: 4px 12px; border-radius: 20px; font-weight: bold; }
        .search-bar { width: 100%; padding: 12px; border-radius: 20px; border: 1px solid rgba(255,255,255,0.2); background: rgba(0,0,0,0.4); color: white; outline: none; margin-bottom: 15px; }
        .page { display: none; padding: 15px; }
        .page.active { display: block; }
        .cat-scroll { display: flex; overflow-x: auto; gap: 10px; padding-bottom: 10px; margin-bottom: 15px; }
        .cat-btn { background: rgba(255,255,255,0.1); padding: 8px 16px; border-radius: 20px; font-size: 13px; cursor: pointer; white-space: nowrap; }
        .cat-btn.active { background: #f02d73; color: white; font-weight:bold; }
        .video-card { background: rgba(30, 30, 45, 0.7); border-radius: 12px; margin-bottom: 20px; overflow: hidden; position: relative; }
        .video-card img { width: 100%; height: 200px; object-fit: cover; }
        .tag-premium { position: absolute; top: 10px; left: 10px; background: #c72cff; padding: 3px 10px; border-radius: 12px; font-size: 12px; font-weight: bold; }
        .play-btn-overlay { position: absolute; top: 40%; left: 50%; transform: translate(-50%, -50%); width: 50px; height: 50px; background: rgba(0,123,255,0.8); border-radius: 50%; display: flex; justify-content: center; align-items: center; cursor: pointer; }
        .play-btn-overlay::after { content: '▶'; color: white; font-size: 20px; }
        .video-info { padding: 15px; }
        .pagination { display: flex; justify-content: space-between; align-items: center; margin-top: 15px; }
        .page-btn { background: #f02d73; color: white; border: none; padding: 8px 15px; border-radius: 8px; cursor: pointer; }
        .page-btn:disabled { background: gray; }
        .btn-main { width: 100%; background: #f02d73; padding: 15px; border-radius: 10px; font-weight: bold; border: none; color: white; margin-top: 10px; }
        .input-box { width: 100%; background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); padding: 15px; border-radius: 10px; color: white; margin-bottom: 20px; }
        .bottom-nav { position: fixed; bottom: 0; width: 100%; background: #13141f; display: flex; justify-content: space-around; padding: 10px 0; border-top: 1px solid rgba(255,255,255,0.05); }
        .nav-item { display: flex; flex-direction: column; align-items: center; font-size: 11px; color: #666; cursor: pointer; padding: 5px 10px; }
        .nav-item.active { color: #fff; background: rgba(255,255,255,0.05); border-radius: 12px; }
        .modal-overlay { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.9); z-index: 999; justify-content: center; align-items: center; }
        .modal-box { background: #1a1b26; padding: 25px; border-radius: 15px; text-align: center; width: 90%; max-width: 400px; }
    </style>
</head>
<body>
    <div class="header">
        <b>✨ Glow Top</b>
        <div class="coin-pill">🏛 <span id="hdr-balance">0</span></div>
    </div>

    <div id="age-modal" class="modal-overlay">
        <div class="modal-box">
            <h2>🔞 বয়স নিশ্চিতকরণ</h2>
            <p>এই সাইট শুধুমাত্র ১৮+ ব্যবহারকারীদের জন্য।</p>
            <button class="btn-main" style="background:#17c3b2;" onclick="confirmAge(true)">✅ আমি ১৮+</button>
            <button class="btn-main" style="background:transparent; border:1px solid red; color:red;" onclick="tg.close()">❌ আমি ১৮ এর নিচে</button>
        </div>
    </div>

    <div id="ad-overlay" class="modal-overlay">
        <div class="modal-box" style="background:transparent; border:none;">
            <h1 id="timer-count" style="font-size:60px; color:#f02d73;">5</h1>
            <p>অ্যাড দেখার পর ফাইল পাবেন</p>
            <button id="get-file-btn" class="btn-main" style="background:#17c3b2; display:none;">Get File Now</button>
        </div>
    </div>

    <!-- HOME PAGE -->
    <div id="page-home" class="page active">
        <input type="text" id="search-bar" class="search-bar" placeholder="🔍 Search videos..." onkeyup="handleSearch()">
        <div class="cat-scroll">
            <div class="cat-btn active" onclick="filterCat('All', this)">All</div>
            <div class="cat-btn" onclick="filterCat('Premium', this)">💎 Premium</div>
            {% for cat in cats %}
            <div class="cat-btn" onclick="filterCat('{{ cat.name }}', this)">{{ cat.name }}</div>
            {% endfor %}
        </div>
        <div id="video-list"></div>
        <div class="pagination">
            <button class="page-btn" id="prev-btn" onclick="changePage(-1)">← Prev</button>
            <span id="page-info" style="color:gray; font-size:14px;">Page 1</span>
            <button class="page-btn" id="next-btn" onclick="changePage(1)">Next →</button>
        </div>
    </div>

    <!-- PREMIUM PAGE -->
    <div id="page-premium" class="page">
        <h2>কয়েন কিনুন (Buy Coins)</h2>
        {% for pkg in pkgs %}
        <div style="background:rgba(255,255,255,0.05); padding:15px; border-radius:10px; margin-bottom:15px; border:1px solid #333;">
            <b style="color:#ffb703; font-size:12px;">{{ pkg.type | upper }}</b>
            <h3 style="margin:5px 0;">{{ pkg.details }}</h3>
            <button class="btn-main" onclick="reqBuy()">কিনুন (Admin)</button>
        </div>
        {% endfor %}
    </div>

    <!-- SETTINGS PAGE -->
    <div id="page-settings" class="page">
        <div style="background:#2a1f43; padding:20px; border-radius:15px; text-align:center; margin-bottom:20px;">
            <p style="margin:0; color:#aaa;">ID: <span id="set-id"></span></p>
            <h1 style="color:#ffb703; margin:10px 0;">🏛 <span id="set-balance">0</span></h1>
        </div>
        <h3>🎟 কুপন কোড</h3>
        <input type="text" id="coupon-input" class="input-box" placeholder="Code">
        <button class="btn-main" onclick="redeemCoupon()">Redeem</button>
        <h3 style="margin-top:20px;">🎁 রেফার লিংক</h3>
        <input type="text" id="ref-link" class="input-box" readonly>
        <button class="btn-main" style="background:#ffb703; color:black;" onclick="copyRef()">📋 Copy Link</button>
    </div>

    <div class="bottom-nav">
        <div class="nav-item active" onclick="switchNav('home', this)"><span>🏠</span> Home</div>
        <div class="nav-item" onclick="switchNav('premium', this)"><span>💎</span> Premium</div>
        <div class="nav-item" onclick="switchNav('settings', this)"><span>⚙️</span> Settings</div>
    </div>

    <script>
        let tg = window.Telegram.WebApp;
        tg.expand();
        let botUsername = "{{ bot_username }}";
        let adminUsername = "{{ admin_username }}";
        let userId = tg.initDataUnsafe.user ? tg.initDataUnsafe.user.id : 123456789; 
        
        document.getElementById('set-id').innerText = userId;
        document.getElementById('ref-link').value = `https://t.me/${botUsername}?start=${userId}`;
        
        async function loadUser() {
            let res = await fetch('/api/user/' + userId);
            let data = await res.json();
            document.getElementById('hdr-balance').innerText = data.balance;
            document.getElementById('set-balance').innerText = data.balance;
        }
        loadUser();

        if(!localStorage.getItem('ageVerified')) { document.getElementById('age-modal').style.display = 'flex'; }
        function confirmAge(isAdult) {
            if(isAdult) { localStorage.setItem('ageVerified', 'true'); document.getElementById('age-modal').style.display = 'none'; }
        }

        function switchNav(pageId, element) {
            document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
            document.getElementById('page-' + pageId).classList.add('active');
            document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
            element.classList.add('active');
        }

        let allFiles = {{ files_json | safe }};
        let filteredFiles = [...allFiles];
        let currentPage = 1;
        let itemsPerPage = 10;

        function renderVideos() {
            let start = (currentPage - 1) * itemsPerPage;
            let end = start + itemsPerPage;
            let pageFiles = filteredFiles.slice(start, end);
            
            let html = "";
            if(pageFiles.length === 0) { html = "<p style='text-align:center; color:gray;'>কোনো ভিডিও পাওয়া যায়নি!</p>"; }
            
            pageFiles.forEach(file => {
                html += `<div class="video-card">
                    <img src="${file.thumb_url || 'https://placehold.co/600x400/1e1e2d/f02d73'}">
                    ${file.is_premium ? '<div class="tag-premium">💎 PREMIUM</div>' : ''}
                    <div class="play-btn-overlay" onclick="playVideo('${file._id}')"></div>
                    <div class="video-info"><b>${file.title}</b><br><small style="color:gray;">👁 ${file.views} views</small></div>
                </div>`;
            });
            document.getElementById('video-list').innerHTML = html;
            
            document.getElementById('page-info').innerText = `Page ${currentPage} of ${Math.ceil(filteredFiles.length / itemsPerPage) || 1}`;
            document.getElementById('prev-btn').disabled = currentPage === 1;
            document.getElementById('next-btn').disabled = end >= filteredFiles.length;
        }

        function handleSearch() {
            let q = document.getElementById('search-bar').value.toLowerCase();
            applyFilters(document.querySelector('.cat-btn.active').innerText.replace('💎 ', ''), q);
        }

        function filterCat(catName, btn) {
            document.querySelectorAll('.cat-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            applyFilters(catName, document.getElementById('search-bar').value.toLowerCase());
        }

        function applyFilters(cat, query) {
            filteredFiles = allFiles.filter(f => {
                let matchCat = (cat === 'All') || (cat === 'Premium' && f.is_premium) || (f.category === cat);
                let matchQuery = f.title.toLowerCase().includes(query);
                return matchCat && matchQuery;
            });
            if(cat === 'All') { filteredFiles.sort((a,b) => b.views - a.views); }
            currentPage = 1;
            renderVideos();
        }
        renderVideos();

        function changePage(dir) { currentPage += dir; renderVideos(); }

        let currentDeepLink = "";
        async function playVideo(fileId) {
            currentDeepLink = `https://t.me/${botUsername}?start=file_${fileId}`;
            let res = await fetch(`/api/get_ad/${userId}`);
            let adData = await res.json();

            if (adData.show_ad) {
                document.getElementById('ad-overlay').style.display = 'flex';
                document.getElementById('get-file-btn').style.display = 'none';
                document.getElementById('timer-count').style.display = 'block';
                window.open(adData.ad_link, '_blank');

                let timeLeft = adData.wait_time;
                document.getElementById('timer-count').innerText = timeLeft;

                let timer = setInterval(() => {
                    timeLeft--;
                    document.getElementById('timer-count').innerText = timeLeft;
                    if (timeLeft <= 0) {
                        clearInterval(timer);
                        document.getElementById('timer-count').style.display = 'none';
                        let btn = document.getElementById('get-file-btn');
                        btn.style.display = 'block';
                        btn.onclick = () => { tg.openTelegramLink(currentDeepLink); setTimeout(()=>tg.close(), 500); };
                    }
                }, 1000);
            } else {
                tg.openTelegramLink(currentDeepLink);
                setTimeout(() => tg.close(), 500);
            }
        }

        async function redeemCoupon() {
            let code = document.getElementById('coupon-input').value;
            if(!code) return tg.showAlert("কোড দিন!");
            let res = await fetch('/api/redeem', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ uid: userId, code: code }) });
            let data = await res.json();
            tg.showAlert(data.msg);
            if(data.status === 'success') { loadUser(); document.getElementById('coupon-input').value = ""; }
        }

        function copyRef() {
            navigator.clipboard.writeText(document.getElementById('ref-link').value);
            tg.showAlert("✅ Link Copied!");
        }

        function reqBuy() {
            tg.openTelegramLink(`https://t.me/${adminUsername}`);
            tg.showAlert("✅ অ্যাডমিনকে মেসেজ দিন।");
        }
    </script>
</body>
</html>
"""

@web.route('/')
def home():
    files = list(sync_db["files"].find().sort("_id", -1))
    for f in files: f["_id"] = str(f["_id"])
    cats = list(sync_db["categories"].find())
    pkgs = list(sync_db["packages"].find())
    return render_template_string(HTML_TEMPLATE, files_json=json.dumps(files), cats=cats, pkgs=pkgs, bot_username=BOT_USERNAME, admin_username=ADMIN_USERNAME)

# ==========================================
# 8. RUN SERVERS
# ==========================================
def run_flask(): 
    port = int(os.environ.get("PORT", 8080))
    web.run(host="0.0.0.0", port=port, debug=False)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    while True:
        try:
            print("🚀 Starting Bot & UI...")
            app.run()
            break  
        except FloodWait as e:
            time.sleep(e.value) 
        except Exception as e:
            print(f"❌ Core Error: {e}")
            break
