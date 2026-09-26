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

# Asyncio Fix
try: loop = asyncio.get_event_loop()
except RuntimeError: loop = asyncio.new_event_loop(); asyncio.set_event_loop(loop)

# OpenCV for Screenshots
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

# ==========================================
# 3. USER START & MUST JOIN
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
                try: await client.send_message(ref_by, f"🎉 আপনার রেফার লিংকে একজন জয়েন করেছে! +{config['ref_coin']} Coins")
                except: pass
        user = await users_col.find_one({"_id": user_id})

    # Save deep link file request
    if len(args) > 1 and args[1].startswith("file_"):
        pending_file = args[1].replace("file_", "")
        await users_col.update_one({"_id": user_id}, {"$set": {"pending_file": pending_file}})
        user["pending_file"] = pending_file

    # Must Join Checking
    channels = await channels_col.find().to_list(100)
    not_joined = []
    for ch in channels:
        try: await client.get_chat_member(ch["chat_id"], user_id)
        except UserNotParticipant: not_joined.append(ch["link"])
        except: pass

    if not_joined:
        buttons = [[InlineKeyboardButton("📢 Join Channel", url=link)] for link in not_joined]
        buttons.append([InlineKeyboardButton("✅ Joined", callback_data="check_join")])
        return await message.reply("❌ ভিডিও দেখতে হলে আগে আমাদের চ্যানেলগুলোতে জয়েন করতে হবে:", reply_markup=InlineKeyboardMarkup(buttons))

    # Send file if pending and joined
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
            except Exception as e: await msg.edit_text(f"❌ ফাইল পাঠাতে সমস্যা হয়েছে! {e}")
        else: await message.reply("❌ ফাইলটি ডাটাবেসে পাওয়া যায়নি!")
        return

    profile_text = f"👋 **স্বাগতম Glow Top-এ!**\n\n🆔 **আপনার আইডি:** `{user_id}`\n💰 **আপনার ব্যালেন্স:** {user.get('balance', 0)} Coins\n\nনিচের বাটনে ক্লিক করে অ্যাপ ওপেন করুন 👇"
    btn = InlineKeyboardMarkup([[InlineKeyboardButton("🔥 Open Glow Top", web_app=WebAppInfo(url=f"{WEB_URL}/"))]])
    await message.reply(profile_text, reply_markup=btn)

@app.on_callback_query(filters.regex("check_join"))
async def check_join_cb(client, query):
    user_id = query.from_user.id
    channels = await channels_col.find().to_list(100)
    for ch in channels:
        try: await client.get_chat_member(ch["chat_id"], user_id)
        except: return await query.answer("❌ আপনি এখনো সব চ্যানেলে জয়েন করেননি!", show_alert=True)
    
    await query.message.delete()
    class FakeMsg:
        def __init__(self, from_user): self.from_user = from_user; self.text = "/start"
        async def reply(self, *args, **kwargs): return await client.send_message(user_id, *args, **kwargs)
    await start_cmd(client, FakeMsg(query.from_user))

# ==========================================
# 4. ADMIN COMMANDS
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

@app.on_message(filters.command("addcoupon") & filters.user(ADMIN_ID))
async def cmd_addcoupon(client, message):
    try:
        parts = message.text.split()
        await coupons_col.insert_one({"code": parts[1], "coins": int(parts[2]), "limit": int(parts[3]), "used_by": []})
        await message.reply(f"✅ কুপন অ্যাড হয়েছে: {parts[1]}")
    except: await message.reply("Format: /addcoupon CODE 50 100")

@app.on_message(filters.command("addbks") & filters.user(ADMIN_ID))
async def cmd_addbks(client, message):
    try: await pkgs_col.insert_one({"type": "bkash", "details": message.text.split(" ", 1)[1]}); await message.reply("✅ bKash Pkg Added.")
    except: pass

@app.on_message(filters.command("addusd") & filters.user(ADMIN_ID))
async def cmd_addusd(client, message):
    try: await pkgs_col.insert_one({"type": "usd", "details": message.text.split(" ", 1)[1]}); await message.reply("✅ USD Pkg Added.")
    except: pass

@app.on_message(filters.command("addcata") & filters.user(ADMIN_ID))
async def cmd_addcata(client, message):
    try: await cats_col.insert_one({"name": message.text.split(" ", 1)[1]}); await message.reply("✅ Category Added.")
    except: pass

# ==========================================
# 5. ACTUAL FILE DOWNLOAD & SCREENSHOT LOGIC
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
    if message.text.startswith("/"): return # Ignore commands
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
        await message.reply("৪. এবার ভিডিওটি, ডকুমেন্টটি বা অডিওটি সেন্ড করুন:")

@app.on_message((filters.video | filters.document | filters.audio) & filters.user(ADMIN_ID) & filters.private)
async def handle_admin_file(client, message):
    step = admin_steps.get(ADMIN_ID, {}).get("step")
    if step == "file":
        msg = await message.reply("⏳ মিডিয়া প্রসেস হচ্ছে, ফাইল ডাউনলোড করে স্ক্রিনশট নিচ্ছি...")
        short_id = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
        
        file_id = message.video.file_id if message.video else (message.document.file_id if message.document else message.audio.file_id)
        thumb_url = ""

        # 1. Check if Telegram already provided a thumbnail
        if (message.video and message.video.thumbs) or (message.document and message.document.thumbs):
            thumb = message.video.thumbs[0] if message.video else message.document.thumbs[0]
            thumb_path = f"{short_id}.jpg"
            await client.download_media(thumb.file_id, file_name=thumb_path)
            thumb_url = await asyncio.to_thread(upload_to_telegraph, thumb_path)
            try: os.remove(thumb_path)
            except: pass

        # 2. Extract frame using OpenCV for Videos/Documents if no thumb exists
        if not thumb_url and not message.audio and HAS_CV2:
            try:
                await msg.edit_text("⏳ সার্ভারে ফাইল ডাউনলোড হচ্ছে, দয়া করে অপেক্ষা করুন...")
                file_path = await client.download_media(message, file_name=f"{short_id}.mp4")
                
                await msg.edit_text("⏳ ফ্রেম কাটা হচ্ছে...")
                cap = cv2.VideoCapture(file_path)
                cap.set(cv2.CAP_PROP_POS_FRAMES, 15) # ১৫ নাম্বার ফ্রেম (কালো স্ক্রিন এড়াতে)
                ret, frame = cap.read()
                if ret:
                    thumb_path = f"{short_id}_cv2.jpg"
                    cv2.imwrite(thumb_path, frame)
                    thumb_url = await asyncio.to_thread(upload_to_telegraph, thumb_path)
                    try: os.remove(thumb_path)
                    except: pass
                cap.release()
                try: os.remove(file_path)
                except: pass
            except Exception as e:
                print(f"OpenCV Error: {e}")
                
        # Default Thumbnail for Audio or failed extraction
        if not thumb_url:
            thumb_url = "https://placehold.co/600x400/1c1c24/ff007f?text=Media+File"

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
            wait_time = random.choice(config.get("direk_wait", [5]))
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
    try: asyncio.run_coroutine_threadsafe(app.send_message(uid, f"🎉 কুপন রিডিম হয়েছে! +{coupon['coins']} Coins!"), loop)
    except: pass
    return jsonify({"status": "success", "msg": f"Successfully redeemed {coupon['coins']} coins!"})

@web.route('/api/user/<int:user_id>')
def get_user(user_id):
    user = sync_db["users"].find_one({"_id": user_id})
    return jsonify({"balance": user.get("balance", 0) if user else 0})


# ==========================================
# 7. EXACT UI HTML/CSS (Glow Top Design)
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
        /* Exact Design Match */
        body { background: linear-gradient(180deg, #1f0b1f 0%, #0a1015 100%); color: #fff; font-family: sans-serif; margin: 0; padding-bottom: 80px; min-height: 100vh;}
        * { box-sizing: border-box; }
        
        .header { display: flex; justify-content: space-between; padding: 15px 20px; align-items: center; background: rgba(0,0,0,0.2); }
        .logo { font-size: 20px; font-weight: bold; }
        .coin-pill { background: #ffb703; color: #000; padding: 5px 15px; border-radius: 20px; font-weight: bold; font-size: 14px;}
        
        .page { display: none; padding: 15px; }
        .page.active { display: block; }
        
        /* Search & Filter */
        .search-bar { width: 100%; padding: 12px 15px; border-radius: 10px; border: 1px solid rgba(255,255,255,0.1); background: rgba(255,255,255,0.05); color: white; outline: none; margin-bottom: 15px; font-size: 15px;}
        .cat-scroll { display: flex; overflow-x: auto; gap: 10px; padding-bottom: 10px; margin-bottom: 15px; }
        .cat-btn { background: rgba(255,255,255,0.1); padding: 8px 18px; border-radius: 20px; font-size: 13px; cursor: pointer; white-space: nowrap; border: 1px solid rgba(255,255,255,0.1);}
        .cat-btn.active { background: linear-gradient(90deg, #f02d73, #00d4ff); color: white; border:none; }
        
        /* Videos */
        .video-card { background: rgba(255,255,255,0.05); border-radius: 12px; margin-bottom: 20px; overflow: hidden; position: relative; border: 1px solid rgba(255,255,255,0.1);}
        .video-card img { width: 100%; height: 200px; object-fit: cover; }
        .tag-premium { position: absolute; top: 10px; left: 10px; background: #c72cff; padding: 4px 10px; border-radius: 12px; font-size: 11px; font-weight: bold; box-shadow: 0 2px 10px rgba(199,44,255,0.5);}
        .play-btn-overlay { position: absolute; top: 40%; left: 50%; transform: translate(-50%, -50%); width: 55px; height: 55px; background: rgba(0,123,255,0.8); border-radius: 50%; display: flex; justify-content: center; align-items: center; cursor: pointer; backdrop-filter: blur(5px);}
        .play-btn-overlay::after { content: '▶'; color: white; font-size: 22px; margin-left:4px;}
        .video-info { padding: 15px; }
        
        /* Pagination */
        .pagination { display: flex; justify-content: space-between; align-items: center; margin-top: 15px; }
        .page-btn { background: #f02d73; color: white; border: none; padding: 8px 20px; border-radius: 8px; cursor: pointer; font-weight:bold;}
        .page-btn:disabled { background: rgba(255,255,255,0.2); color:#888;}
        
        /* Components */
        .btn-main { width: 100%; background: linear-gradient(90deg, #f02d73, #ff6b6b); padding: 15px; border-radius: 10px; font-weight: bold; border: none; color: white; margin-top: 10px; font-size: 16px; cursor: pointer;}
        .input-box { width: 100%; background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); padding: 15px; border-radius: 10px; color: white; margin-bottom: 20px; font-size:15px;}
        
        /* Modals (18+ & Ads) */
        .modal-overlay { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(11,20,29,0.95); z-index: 999; justify-content: center; align-items: center; }
        .modal-box { background: rgba(30, 30, 45, 0.9); padding: 25px; border-radius: 15px; text-align: center; width: 90%; max-width: 400px; border: 1px solid rgba(255,255,255,0.1);}
        .alert-box { background: rgba(255,0,0,0.1); border: 1px solid #ff4d4d; color: #ffb3b3; padding: 15px; border-radius: 10px; font-size: 13px; margin: 15px 0;}
        
        /* Specific Page Styles */
        .share-banner { background: rgba(0,255,100,0.05); border: 1px solid rgba(0,255,100,0.2); padding: 20px; border-radius: 12px; font-size: 14px; line-height: 1.6; margin-bottom: 20px;}
        .pkg-tab-container { display: flex; gap: 10px; margin-bottom:20px;}
        .pkg-tab { flex: 1; text-align: center; padding: 12px; background: rgba(255,255,255,0.05); border-radius: 10px; font-weight:bold; cursor: pointer;}
        .pkg-tab.active { background: #f02d73; color: white;}
        .pkg-card { background: rgba(255,255,255,0.05); border: 1px solid #ffb703; padding: 20px; border-radius: 12px; margin-bottom: 15px; text-align: center; position: relative;}
        .pkg-badge { position: absolute; top: -10px; left: 50%; transform: translateX(-50%); background: #ffb703; color: black; font-size: 10px; font-weight: bold; padding: 3px 10px; border-radius: 10px;}
        
        .settings-menu { display: flex; flex-direction: column; gap: 12px;}
        .set-item { display: flex; align-items: center; background: rgba(255,255,255,0.05); padding: 15px; border-radius: 12px; border: 1px solid rgba(255,255,255,0.05); cursor:pointer;}
        .set-icon { width: 45px; height: 45px; border-radius: 12px; display: flex; justify-content: center; align-items: center; font-size: 20px; margin-right: 15px;}
        
        .bottom-nav { position: fixed; bottom: 0; width: 100%; background: rgba(11,20,29,0.95); display: flex; justify-content: space-around; padding: 10px 0; border-top: 1px solid rgba(255,255,255,0.1); backdrop-filter: blur(10px);}
        .nav-item { display: flex; flex-direction: column; align-items: center; font-size: 11px; color: #888; cursor: pointer; padding: 5px 15px; border-radius: 12px;}
        .nav-item.active { color: #fff; background: rgba(255,255,255,0.1); }
        .nav-item span { font-size: 22px; margin-bottom: 3px; filter: grayscale(100%);}
        .nav-item.active span { filter: grayscale(0%);}
    </style>
</head>
<body>
    <div class="header">
        <div class="logo">Glow Top</div>
        <div class="coin-pill">🏛 <span id="hdr-balance">0</span></div>
    </div>

    <!-- 18+ Verification Modal (Exact Design) -->
    <div id="age-modal" class="modal-overlay">
        <div class="modal-box">
            <div style="font-size: 50px; margin-bottom:10px;">🔞</div>
            <h2>বয়স নিশ্চিতকরণ</h2>
            <p style="font-size:14px; color:#ccc;">এই ওয়েবসাইটের কনটেন্ট শুধুমাত্র <span style="color:#00d4ff;">১৮ বছর বা তার বেশি বয়সী</span> ব্যবহারকারীদের জন্য প্রযোজ্য।</p>
            <div class="alert-box">
                ⚠️ আপনার বয়স ১৮ বছরের কম হলে অনুগ্রহ করে এই সাইট ব্যবহার করবেন না এবং এখনই প্রস্থান করুন।
            </div>
            <button class="btn-main" style="background: linear-gradient(90deg, #00d4ff, #00ffcc);" onclick="confirmAge(true)">✅ হ্যাঁ, আমার বয়স ১৮+ বছর</button>
            <button class="btn-main" style="background: transparent; border: 1px solid #555; color: #888;" onclick="tg.close()">❌ না, আমার বয়স ১৮ বছরের কম</button>
        </div>
    </div>

    <!-- Ad Timer Overlay -->
    <div id="ad-overlay" class="modal-overlay">
        <div class="modal-box" style="background:transparent; border:none;">
            <h1 id="timer-count" style="font-size:80px; color:#f02d73; margin:0;">5</h1>
            <p style="font-size:16px;">অ্যাড দেখার পর ফাইল পাবেন</p>
            <button id="get-file-btn" class="btn-main" style="background: linear-gradient(90deg, #00d4ff, #00ffcc); display:none;">Get File Now</button>
        </div>
    </div>

    <!-- PAGE 1: HOME (Search & Pagination) -->
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
            <span id="page-info" style="color:#aaa; font-size:14px;">Page 1</span>
            <button class="page-btn" id="next-btn" onclick="changePage(1)">Next →</button>
        </div>
    </div>

    <!-- PAGE 2: PREMIUM BUY (Exact Match) -->
    <div id="page-premium" class="page">
        <h2 style="margin-top:0;">কয়েন কিনুন (Buy Coins)</h2>
        <div class="pkg-tab-container">
            <div class="pkg-tab active" onclick="togglePkg('bks', this)">📱 বিকাশ/নগদ</div>
            <div class="pkg-tab" onclick="togglePkg('usd', this)">⚡ Instant (USD)</div>
        </div>
        
        <div id="pkg-bks">
            {% for pkg in pkgs if pkg.type == 'bkash' %}
            <div class="pkg-card">
                <div class="pkg-badge">⭐ Most Popular</div>
                <div style="font-size:30px; margin-bottom:5px;">🏛</div>
                <h2 style="margin:0 0 5px 0;">{{ pkg.details.split('=')[0] if '=' in pkg.details else pkg.details }}</h2>
                <p style="color:#aaa; font-size:13px; margin:0 0 15px 0;">{{ pkg.details.split('=')[1] if '=' in pkg.details else pkg.details }} Coins</p>
                <button class="btn-main" style="margin:0;" onclick="reqBuy()">কিনুন (Buy)</button>
            </div>
            {% endfor %}
        </div>
        
        <div id="pkg-usd" style="display:none;">
            {% for pkg in pkgs if pkg.type == 'usd' %}
            <div class="pkg-card" style="border-color:#00d4ff;">
                <div class="pkg-badge" style="background:#00d4ff;">⚡ Instant</div>
                <div style="font-size:30px; margin-bottom:5px;">💲</div>
                <h2 style="margin:0 0 5px 0;">{{ pkg.details.split('=')[0] if '=' in pkg.details else pkg.details }}</h2>
                <p style="color:#aaa; font-size:13px; margin:0 0 15px 0;">{{ pkg.details.split('=')[1] if '=' in pkg.details else pkg.details }} Coins</p>
                <button class="btn-main" style="margin:0; background:linear-gradient(90deg, #00d4ff, #00ffcc);" onclick="reqBuy()">কিনুন (Buy)</button>
            </div>
            {% endfor %}
        </div>
    </div>

    <!-- PAGE 3: SETTINGS -->
    <div id="page-settings" class="page">
        <div style="background: linear-gradient(135deg, #4b2354, #1a1b26); padding:25px; border-radius:15px; text-align:center; margin-bottom:20px; border: 1px solid rgba(255,255,255,0.1);">
            <p style="margin:0; color:#aaa; font-size:13px;">আপনার ব্যালেন্স (YOUR BALANCE)</p>
            <h1 style="color:#ffb703; margin:10px 0; font-size:45px;">🏛 <span id="set-balance">0</span></h1>
            <p style="margin:0; color:#888; font-size:12px;">ID: <span id="set-id"></span></p>
        </div>
        
        <div class="settings-menu">
            <div class="set-item" onclick="switchNav('premium')">
                <div class="set-icon" style="background: linear-gradient(135deg, #ff9a9e, #fecfef);">🪙</div>
                <div>
                    <b style="display:block; font-size:15px;">কয়েন কিনুন (Buy Coins)</b>
                    <span style="color:#aaa; font-size:12px;">প্যাকেজ বেছে নিয়ে পেমেন্ট করুন</span>
                </div>
            </div>
            <div class="set-item" onclick="switchNav('coupon')">
                <div class="set-icon" style="background: linear-gradient(135deg, #a18cd1, #fbc2eb);">🎟</div>
                <div>
                    <b style="display:block; font-size:15px;">কুপন কোড (Coupon Code)</b>
                    <span style="color:#aaa; font-size:12px;">কোড রিডিম করে ফ্রি কয়েন নিন</span>
                </div>
            </div>
            <div class="set-item" onclick="switchNav('share')">
                <div class="set-icon" style="background: linear-gradient(135deg, #ffecd2, #fcb69f);">🎁</div>
                <div>
                    <b style="display:block; font-size:15px;">বন্ধুকে শেয়ার করুন (Share Friend)</b>
                    <span style="color:#aaa; font-size:12px;">ইনভাইট করে ফ্রি কয়েন জিতুন</span>
                </div>
            </div>
        </div>
    </div>

    <!-- PAGE 4: COUPON (Exact Match) -->
    <div id="page-coupon" class="page">
        <h2 style="margin-top:0;">🎟 কুপন কোড (Coupon Code)</h2>
        <div style="text-align:center; margin:30px 0;">
            <div style="font-size:70px; background: rgba(240, 45, 115, 0.2); width:120px; height:120px; line-height:120px; border-radius:30px; margin:0 auto;">🎁</div>
        </div>
        <div style="display:flex; gap:10px;">
            <input type="text" id="coupon-input" class="input-box" style="margin:0;" placeholder="কুপন কোড লিখুন (Enter coupon)">
            <button class="btn-main" style="width:auto; margin:0; padding:15px 25px;" onclick="redeemCoupon()">Redeem</button>
        </div>
        <p style="color:#aaa; font-size:13px; text-align:center; line-height:1.6; margin-top:20px;">
            প্রতিটি কুপন কোড শুধুমাত্র একবারই ব্যবহার করা যাবে। কোড না জানলে আমাদের চ্যানেল/সাপোর্টে চোখ রাখুন — মাঝে মাঝে ফ্রি কয়েন কুপন দেওয়া হয়!
        </p>
    </div>

    <!-- PAGE 5: SHARE (Exact Match) -->
    <div id="page-share" class="page">
        <h2 style="margin-top:0;">🎁 বন্ধুকে শেয়ার করুন (Share)</h2>
        <div style="text-align:center; margin:30px 0;">
            <div style="font-size:70px; background: rgba(138, 43, 226, 0.2); width:120px; height:120px; line-height:120px; border-radius:30px; margin:0 auto;">🎁</div>
        </div>
        
        <div class="share-banner">
            🥳 আপনার বন্ধুকে ইনভাইট করুন! প্রতিজন বন্ধু আপনার লিংক দিয়ে বট স্টার্ট করলেই আপনি সাথে সাথে <b style="color:#ffb703;">🏛 10 Coins একদম ফ্রি</b> পেয়ে যাবেন — কোনো লিমিট নেই, যত বেশি বন্ধু ইনভাইট করবেন তত বেশি কয়েন! 🚀
        </div>

        <p style="color:#aaa; font-size:12px; margin-bottom:5px; text-transform:uppercase;">আপনার রেফার লিংক (Your Referral Link)</p>
        <div style="display:flex; align-items:center; background: rgba(255,255,255,0.05); padding:5px 5px 5px 15px; border-radius:10px; border:1px solid rgba(255,255,255,0.1); margin-bottom:20px;">
            <input type="text" id="ref-link" style="background:transparent; border:none; color:white; width:100%; outline:none;" readonly>
            <button style="background:rgba(255,255,255,0.1); color:#00d4ff; border:none; padding:10px 15px; border-radius:8px; cursor:pointer;" onclick="copyRef()">📋 Copy</button>
        </div>
        
        <button class="btn-main" style="background: #ffb703; color: black; font-size: 18px;" onclick="reqBuy()">🚀 বন্ধুকে শেয়ার করুন (Share)</button>
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

        // 18+ Verification
        if(!localStorage.getItem('ageVerified')) { document.getElementById('age-modal').style.display = 'flex'; }
        function confirmAge(isAdult) {
            if(isAdult) { localStorage.setItem('ageVerified', 'true'); document.getElementById('age-modal').style.display = 'none'; }
        }

        // Navigation
        function switchNav(pageId, element=null) {
            document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
            document.getElementById('page-' + pageId).classList.add('active');
            if(element) {
                document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
                element.classList.add('active');
            }
        }
        
        function togglePkg(type, element) {
            document.querySelectorAll('.pkg-tab').forEach(t => t.classList.remove('active'));
            element.classList.add('active');
            document.getElementById('pkg-bks').style.display = type === 'bks' ? 'block' : 'none';
            document.getElementById('pkg-usd').style.display = type === 'usd' ? 'block' : 'none';
        }

        // Search, Filter & Pagination
        let allFiles = {{ files_json | safe }};
        let filteredFiles = [...allFiles];
        let currentPage = 1;
        let itemsPerPage = 10;

        function renderVideos() {
            let start = (currentPage - 1) * itemsPerPage;
            let end = start + itemsPerPage;
            let pageFiles = filteredFiles.slice(start, end);
            
            let html = "";
            if(pageFiles.length === 0) { html = "<p style='text-align:center; color:gray; margin-top:30px;'>কোনো ভিডিও পাওয়া যায়নি!</p>"; }
            
            pageFiles.forEach(file => {
                html += `<div class="video-card">
                    <img src="${file.thumb_url || 'https://placehold.co/600x400/1c1c24/ff007f?text=Media'}">
                    ${file.is_premium ? '<div class="tag-premium">💎 PREMIUM</div>' : ''}
                    <div class="play-btn-overlay" onclick="playVideo('${file._id}')"></div>
                    <div class="video-info">
                        <b style="font-size:15px; display:block; margin-bottom:5px;">${file.title}</b>
                        <small style="color:#aaa;">👁 ${file.views} views</small>
                    </div>
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

        // Ad and File Deep Link
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

        // Coupon & Actions
        async function redeemCoupon() {
            let code = document.getElementById('coupon-input').value;
            if(!code) return tg.showAlert("কোড লিখুন!");
            let res = await fetch('/api/redeem', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ uid: userId, code: code }) });
            let data = await res.json();
            tg.showAlert(data.msg);
            if(data.status === 'success') { loadUser(); document.getElementById('coupon-input').value = ""; }
        }

        function copyRef() {
            let copyText = document.getElementById("ref-link");
            copyText.select();
            copyText.setSelectionRange(0, 99999);
            navigator.clipboard.writeText(copyText.value);
            tg.showAlert("✅ রেফার লিংক কপি হয়েছে!");
        }

        function reqBuy() {
            tg.openTelegramLink(`https://t.me/${adminUsername}`);
            tg.showAlert("✅ পেমেন্ট করতে অ্যাডমিনকে ইনবক্সে মেসেজ দিন।");
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
            print("🚀 Starting Bot & UI (Design Match Mode)...")
            app.run()
            break  
        except FloodWait as e:
            print(f"⚠️ Rate Limit: Waiting {e.value} seconds...")
            time.sleep(e.value) 
        except Exception as e:
            print(f"❌ Error: {e}")
            break
