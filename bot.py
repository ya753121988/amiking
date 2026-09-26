import os
import sys
import asyncio
import threading
import random
import string
import time
import requests
import cv2
from datetime import datetime, timedelta

# --- RENDER ASYNCIO FIX ---
try:
    loop = asyncio.get_event_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo, MenuButtonWebApp
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
WEB_URL = os.environ.get("WEB_URL", "https://amiking.onrender.com") # আপনার ওয়েব ইউআরএল দিন

BOT_USERNAME = "PronWaliZone_Bot" 

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
    coupons_col = db["coupons"]

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
            "direk_wait": [5]
        }
        await config_col.insert_one(conf)
    return conf

def is_not_command(_, __, message):
    return bool(message.text and not message.text.startswith("/"))
not_cmd_filter = filters.create(is_not_command)

# ==========================================
# 3. USER START & DEEP LINK LOGIC
# ==========================================
@app.on_message(filters.command("start") & filters.private)
async def start_cmd(client, message):
    user_id = message.from_user.id
    args = message.text.split()
    config = await get_config()
    
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

    user = await users_col.find_one({"_id": user_id})
    if not user:
        await users_col.insert_one({
            "_id": user_id, 
            "name": message.from_user.first_name, 
            "balance": 0, 
            "is_premium": False
        })
        if len(args) > 1 and args[1].isdigit():
            ref_by = int(args[1])
            if ref_by != user_id and config.get("ref_coin", 0) > 0:
                await users_col.update_one({"_id": ref_by}, {"$inc": {"balance": config["ref_coin"]}})
                try: await client.send_message(ref_by, f"🎉 আপনার রেফারে একজন জয়েন করেছে! +{config['ref_coin']} Coins যোগ হয়েছে।")
                except: pass
        user = await users_col.find_one({"_id": user_id})

    # --- DEEP LINK: SENDING FILE AFTER AD ---
    if len(args) > 1 and args[1].startswith("file_"):
        file_id = args[1].replace("file_", "")
        file_data = await files_col.find_one({"_id": file_id})
        
        if file_data:
            await files_col.update_one({"_id": file_id}, {"$inc": {"views": 1}})
            prot = config.get("forward_off", True)
            msg = await message.reply("⏳ আপনার ভিডিও পাঠানো হচ্ছে...")
            
            try:
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
            except Exception as e:
                await msg.edit_text("❌ ফাইল পাঠাতে সমস্যা হয়েছে!")
        else:
            await message.reply("❌ ফাইলটি পাওয়া যায়নি!")
        return

    profile_text = (
        f"👋 **স্বাগতম Glow Top-এ!**\n\n"
        f"🆔 **আপনার আইডি:** `{user_id}`\n"
        f"💰 **আপনার ব্যালেন্স:** {user.get('balance', 0)} Coins\n\n"
        f"নিচের বাটনে ক্লিক করে অ্যাপ ওপেন করুন 👇"
    )
    btn = InlineKeyboardMarkup([[InlineKeyboardButton("🔥 Open Glow Top", web_app=WebAppInfo(url=f"{WEB_URL}/"))]])
    try: await client.set_chat_menu_button(chat_id=user_id, menu_button=MenuButtonWebApp(text="🚀 Open App", web_app=WebAppInfo(url=f"{WEB_URL}/")))
    except: pass
    await message.reply(profile_text, reply_markup=btn)

@app.on_callback_query(filters.regex("check_join"))
async def check_join_cb(client, query):
    await query.message.delete()
    await start_cmd(client, query.message)

# ==========================================
# 4. ADMIN COMMANDS (BROADCAST & COUPON ADDED)
# ==========================================
@app.on_message(filters.command("broadcast") & filters.user(ADMIN_ID))
async def cmd_broadcast(client, message):
    if not message.reply_to_message:
        return await message.reply("❌ কোনো মেসেজ রিপ্লাই করে /broadcast লিখুন।")
    
    msg = await message.reply("⏳ ব্রডকাস্ট শুরু হয়েছে...")
    users = await users_col.find().to_list(None)
    success = 0
    for u in users:
        try:
            await message.reply_to_message.copy(u["_id"])
            success += 1
            await asyncio.sleep(0.05) # FloodWait এড়াতে
        except FloodWait as e:
            await asyncio.sleep(e.value)
        except: pass
    await msg.edit_text(f"✅ ব্রডকাস্ট সম্পন্ন! মোট {success} জন ইউজারকে মেসেজ পাঠানো হয়েছে।")

@app.on_message(filters.command("addcoupon") & filters.user(ADMIN_ID))
async def cmd_addcoupon(client, message):
    # Format: /addcoupon CODE COINS LIMIT
    try:
        parts = message.text.split()
        code = parts[1]
        coins = int(parts[2])
        limit = int(parts[3])
        await coupons_col.insert_one({"code": code, "coins": coins, "limit": limit, "used_by": []})
        await message.reply(f"✅ কুপন অ্যাড হয়েছে: {code} | Coins: {coins} | Limit: {limit}")
    except: await message.reply("Format: /addcoupon NEWYEAR2026 50 100")

@app.on_message(filters.command("addbks") & filters.user(ADMIN_ID))
async def cmd_addbks(client, message):
    try:
        await pkgs_col.insert_one({"type": "bkash", "details": message.text.split(" ", 1)[1]})
        await message.reply("✅ bKash Package Added.")
    except: pass

@app.on_message(filters.command("addusd") & filters.user(ADMIN_ID))
async def cmd_addusd(client, message):
    try:
        await pkgs_col.insert_one({"type": "usd", "details": message.text.split(" ", 1)[1]})
        await message.reply("✅ USD Package Added.")
    except: pass

@app.on_message(filters.command("addcata") & filters.user(ADMIN_ID))
async def cmd_addcata(client, message):
    try:
        await cats_col.insert_one({"name": message.text.split(" ", 1)[1]})
        await message.reply("✅ Category Added.")
    except: pass

# ==========================================
# 5. TELEGRAPH SCREENSHOT & AUTO NOTIFICATION
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
        admin_steps[ADMIN_ID]["step"] = "file"
        await message.reply("৩. এবার ভিডিওটি সেন্ড করুন (OpenCV দিয়ে অটো স্ক্রিনশট নেওয়া হবে):")

@app.on_message(filters.video & filters.user(ADMIN_ID) & filters.private)
async def handle_admin_video(client, message):
    step = admin_steps.get(ADMIN_ID, {}).get("step")
    if step == "file":
        msg = await message.reply("⏳ স্ক্রিনশট তৈরি করা হচ্ছে (এতে একটু সময় লাগতে পারে)...")
        
        short_id = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
        file_id = message.video.file_id
        thumb_url = ""
        
        # Method 1: Pyrogram native thumbnail
        if message.video.thumbs:
            thumb_path = f"{short_id}.jpg"
            await client.download_media(message.video.thumbs[0].file_id, file_name=thumb_path)
            thumb_url = await asyncio.to_thread(upload_to_telegraph, thumb_path)
            try: os.remove(thumb_path)
            except: pass
            
        # Method 2: OpenCV Fallback (যদি টেলিগ্রাম থাম্ব না দেয়)
        if not thumb_url:
            video_path = await client.download_media(message.video.file_id)
            cap = cv2.VideoCapture(video_path)
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

        title = admin_steps[ADMIN_ID]["title"]
        await files_col.insert_one({
            "_id": short_id,
            "title": title, 
            "category": admin_steps[ADMIN_ID]["category"], 
            "file_id": file_id, 
            "thumb_url": thumb_url,
            "views": 0,
            "is_premium": False # Premium tag if needed
        })
        del admin_steps[ADMIN_ID]
        await msg.edit_text("✅ ভিডিও ডাটাবেসে সেভ হয়েছে! এখন অটো-নোটিফিকেশন পাঠানো হচ্ছে...")

        # AUTO BROADCAST TO ALL USERS
        users = await users_col.find().to_list(None)
        btn = InlineKeyboardMarkup([[InlineKeyboardButton("🔥 Watch Now", web_app=WebAppInfo(url=f"{WEB_URL}/"))]])
        broadcast_msg = f"🆕 **নতুন ভিডিও আপলোড করা হয়েছে!**\n\n🎬 Title: {title}\n\nতাড়াতাড়ি অ্যাপে গিয়ে দেখে নিন 👇"
        for u in users:
            try:
                await client.send_message(u["_id"], broadcast_msg, reply_markup=btn)
                await asyncio.sleep(0.05)
            except: pass
        await message.reply("✅ সব ইউজারকে নোটিফিকেশন পাঠানো সম্পন্ন হয়েছে!")

# ==========================================
# 6. WEB API FOR MINI APP
# ==========================================
@web.route('/api/get_ad/<int:user_id>')
def get_ad_api(user_id):
    config = sync_db["config"].find_one({"_id": "settings"}) or {}
    user = sync_db["users"].find_one({"_id": user_id})
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
    uid = data['uid']
    code = data['code']
    coupon = sync_db["coupons"].find_one({"code": code})
    
    if not coupon: return jsonify({"status": "error", "msg": "Invalid Coupon Code!"})
    if uid in coupon.get("used_by", []): return jsonify({"status": "error", "msg": "You already used this coupon!"})
    if len(coupon.get("used_by", [])) >= coupon.get("limit", 0): return jsonify({"status": "error", "msg": "Coupon limit reached!"})
    
    sync_db["coupons"].update_one({"code": code}, {"$push": {"used_by": uid}})
    sync_db["users"].update_one({"_id": uid}, {"$inc": {"balance": coupon["coins"]}})
    
    # Notify user in bot
    try: asyncio.run_coroutine_threadsafe(app.send_message(uid, f"🎉 কুপন সফলভাবে রিডিম হয়েছে! আপনি পেয়েছেন {coupon['coins']} Coins!"), loop)
    except: pass
    return jsonify({"status": "success", "msg": f"Successfully redeemed {coupon['coins']} coins!"})

@web.route('/api/user/<int:user_id>')
def get_user(user_id):
    user = sync_db["users"].find_one({"_id": user_id})
    return jsonify({"balance": user.get("balance", 0) if user else 0})

# ==========================================
# 7. GLOW TOP HTML UI FRONTEND
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
        :root { 
            --bg-grad: linear-gradient(135deg, #1b0f1a, #0b141d); 
            --card-bg: rgba(30, 30, 45, 0.7); 
            --text-color: #ffffff; 
            --primary: #f02d73; 
            --secondary: #17c3b2;
            --btn-grad: linear-gradient(90deg, #ff007f, #00d4ff);
            --gold: #ffb703;
        }
        body { background: var(--bg-grad); color: var(--text-color); font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding-bottom: 70px; min-height: 100vh;}
        * { box-sizing: border-box; }

        /* HEADER */
        .header { display: flex; justify-content: space-between; padding: 15px 20px; align-items: center; background: rgba(0,0,0,0.3); backdrop-filter: blur(10px);}
        .logo { font-size: 18px; font-weight: bold; display: flex; align-items: center; gap: 8px;}
        .coin-pill { background: var(--gold); color: #000; padding: 4px 12px; border-radius: 20px; font-weight: bold; font-size: 14px;}

        /* PAGE SYSTEM */
        .page { display: none; padding: 15px; animation: fadeIn 0.3s ease-in-out;}
        .page.active { display: block; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }

        /* HOME SCREEN */
        .video-card { background: var(--card-bg); border-radius: 12px; margin-bottom: 20px; overflow: hidden; position: relative; border: 1px solid rgba(255,255,255,0.05);}
        .video-card img { width: 100%; height: 200px; object-fit: cover; }
        .tag-premium { position: absolute; top: 10px; left: 10px; background: #c72cff; padding: 3px 10px; border-radius: 12px; font-size: 12px; font-weight: bold; display: flex; align-items: center; gap:5px;}
        .play-btn-overlay { position: absolute; top: 40%; left: 50%; transform: translate(-50%, -50%); width: 50px; height: 50px; background: rgba(0,123,255,0.8); border-radius: 50%; display: flex; justify-content: center; align-items: center; cursor: pointer; box-shadow: 0 0 15px rgba(0,123,255,0.5);}
        .play-btn-overlay::after { content: '▶'; color: white; font-size: 20px; margin-left: 4px;}
        .video-info { padding: 15px; }
        .video-title { font-weight: bold; font-size: 15px; margin-bottom: 5px; }
        .video-views { color: #aaa; font-size: 12px; display: flex; align-items: center; gap: 5px;}
        .search-fab { position: fixed; bottom: 80px; right: 20px; width: 55px; height: 55px; background: var(--primary); border-radius: 50%; display: flex; justify-content: center; align-items: center; font-size: 24px; box-shadow: 0 4px 15px rgba(240, 45, 115, 0.5); z-index: 10;}

        /* CATEGORY FILTER */
        .cat-scroll { display: flex; overflow-x: auto; gap: 10px; padding-bottom: 10px; margin-bottom: 15px; scrollbar-width: none;}
        .cat-btn { background: rgba(255,255,255,0.1); padding: 8px 16px; border-radius: 20px; white-space: nowrap; font-size: 13px; cursor: pointer;}
        .cat-btn.active { background: var(--btn-grad); color: white; font-weight:bold; }

        /* SETTINGS PAGE */
        .balance-card { background: linear-gradient(135deg, #4b2354, #2a1f43); border-radius: 15px; padding: 25px; text-align: center; margin-bottom: 20px; border: 1px solid rgba(255,255,255,0.1);}
        .balance-card h3 { margin: 0; color: #ccc; font-size: 14px; font-weight: normal;}
        .balance-card h1 { margin: 10px 0; font-size: 40px; color: var(--gold); display: flex; justify-content: center; align-items: center; gap: 10px;}
        .menu-list { display: flex; flex-direction: column; gap: 12px; }
        .menu-item { display: flex; align-items: center; justify-content: space-between; background: var(--card-bg); padding: 18px; border-radius: 12px; cursor: pointer; border: 1px solid rgba(255,255,255,0.05);}
        .menu-left { display: flex; align-items: center; gap: 15px; font-size: 16px;}
        .menu-left span.icon { width: 40px; height: 40px; background: linear-gradient(135deg, #ff7e5f, #feb47b); border-radius: 10px; display: flex; justify-content: center; align-items: center; font-size: 20px;}

        /* COUPON & SHARE */
        .input-box { width: 100%; background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); padding: 15px; border-radius: 10px; color: white; font-size: 16px; margin-bottom: 20px; outline: none;}
        .btn-main { width: 100%; background: var(--primary); padding: 15px; border-radius: 10px; text-align: center; font-weight: bold; font-size: 16px; cursor: pointer; border: none; color: white; box-shadow: 0 4px 15px rgba(240, 45, 115, 0.4);}
        .share-box { background: rgba(0,255,100,0.1); border: 1px solid rgba(0,255,100,0.3); padding: 15px; border-radius: 12px; font-size: 14px; line-height: 1.6; margin-bottom: 20px;}
        .copy-box { display: flex; background: rgba(255,255,255,0.05); padding: 10px 15px; border-radius: 10px; justify-content: space-between; align-items: center; margin-bottom: 20px;}
        .copy-btn { background: rgba(255,255,255,0.2); padding: 5px 12px; border-radius: 5px; font-size: 12px; cursor: pointer;}

        /* BUY COINS */
        .pkg-tabs { display: flex; gap: 10px; margin-bottom: 20px;}
        .pkg-tab { flex: 1; text-align: center; padding: 12px; background: rgba(255,255,255,0.1); border-radius: 10px; cursor: pointer; color:#ccc;}
        .pkg-tab.active { background: var(--primary); color: white; font-weight: bold;}
        .pkg-grid { display: grid; grid-template-columns: 1fr; gap: 15px;}
        .pkg-card { background: var(--card-bg); padding: 15px; border-radius: 12px; border: 1px solid rgba(255,255,255,0.1); text-align: center; position: relative;}
        .pkg-card h2 { margin: 10px 0; color: white; font-size: 24px;}
        .pkg-card p { margin: 0 0 15px 0; color: #aaa; font-size: 13px;}
        .btn-buy { background: var(--btn-grad); width: 100%; padding: 10px; border-radius: 8px; font-weight: bold; border: none; color: white;}
        .most-popular { position: absolute; top: -10px; left: 50%; transform: translateX(-50%); background: var(--gold); color: black; font-size: 10px; padding: 3px 10px; border-radius: 10px; font-weight: bold;}

        /* BOTTOM NAV */
        .bottom-nav { position: fixed; bottom: 0; width: 100%; background: #13141f; display: flex; justify-content: space-around; padding: 10px 0; border-top: 1px solid rgba(255,255,255,0.05); z-index: 100; border-radius: 20px 20px 0 0;}
        .nav-item { display: flex; flex-direction: column; align-items: center; font-size: 11px; color: #666; cursor: pointer; padding: 5px 10px;}
        .nav-item.active { color: var(--text-color); background: rgba(255,255,255,0.05); border-radius: 12px;}
        .nav-item span { font-size: 22px; margin-bottom: 4px; filter: grayscale(100%); transition: 0.3s;}
        .nav-item.active span { filter: none;}

        /* MODALS */
        .modal-overlay { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.9); z-index: 999; justify-content: center; align-items: center; backdrop-filter: blur(5px);}
        .modal-box { background: #1a1b26; padding: 25px; border-radius: 15px; width: 90%; max-width: 400px; text-align: center; border: 1px solid rgba(255,255,255,0.1);}
        .modal-btn { width: 100%; padding: 12px; margin-top: 10px; border-radius: 8px; font-weight: bold; border: none; cursor: pointer;}
        .btn-yes { background: var(--secondary); color: white; }
        .btn-no { background: transparent; border: 1px solid #ff4d4d; color: #ff4d4d; }

        /* AD OVERLAY */
        #ad-overlay .modal-box { background: transparent; border: none; box-shadow: none;}
        #timer-count { font-size: 70px; color: var(--primary); margin: 10px 0;}
    </style>
</head>
<body>
    <div class="header">
        <div class="logo">✨ Glow Top <span style="background:var(--primary); font-size:10px; padding:2px 6px; border-radius:5px;">BOT</span></div>
        <div class="coin-pill">🏛 <span id="hdr-balance">0</span></div>
    </div>

    <!-- 18+ AGE VERIFICATION MODAL -->
    <div id="age-modal" class="modal-overlay">
        <div class="modal-box">
            <div style="background:linear-gradient(45deg, #ff416c, #ff4b2b); width: 60px; height: 60px; border-radius:50%; display:flex; justify-content:center; align-items:center; margin: 0 auto 15px; font-size: 24px;">🔞</div>
            <h2>বয়স নিশ্চিতকরণ</h2>
            <p style="color:#aaa; font-size:14px; line-height:1.5;">এই ওয়েবসাইটের কনটেন্ট শুধুমাত্র <b>১৮ বছর বা তার বেশি বয়সী</b> ব্যবহারকারীদের জন্য প্রযোজ্য।</p>
            <div style="background:rgba(255,0,0,0.1); border:1px solid red; padding:10px; border-radius:8px; margin: 15px 0; font-size:13px; color:#ffb3b3;">
                ⚠️ আপনার বয়স ১৮ বছরের কম হলে সাইট ব্যবহার করবেন না।
            </div>
            <button class="modal-btn btn-yes" onclick="confirmAge(true)">✅ হ্যাঁ, আমার বয়স ১৮+ বছর</button>
            <button class="modal-btn btn-no" onclick="confirmAge(false)">❌ না, আমার বয়স ১৮ বছরের কম</button>
        </div>
    </div>

    <!-- AD TIMER MODAL -->
    <div id="ad-overlay" class="modal-overlay">
        <div class="modal-box">
            <h2>Please Wait...</h2>
            <p style="color: #aaa;">অ্যাডটি দেখুন। ফাইলটি টেলিগ্রামে পাঠানো হচ্ছে</p>
            <h1 id="timer-count">5</h1>
            <p style="color: #aaa;">সেকেন্ড পর ফাইল ইনবক্সে পাবেন</p>
            <button id="get-file-btn" class="modal-btn btn-yes" style="display:none;">Get File Now</button>
        </div>
    </div>

    <!-- PAGE: HOME -->
    <div id="page-home" class="page active">
        <div class="cat-scroll">
            <div class="cat-btn active" onclick="filterCat('All', this)">All Videos</div>
            {% for cat in cats %}
            <div class="cat-btn" onclick="filterCat('{{ cat.name }}', this)">{{ cat.name }}</div>
            {% endfor %}
        </div>

        <div id="video-list">
            {% for file in files %}
            <div class="video-card" data-cat="{{ file.category }}">
                {% if file.thumb_url %}
                    <img src="{{ file.thumb_url }}" alt="Video">
                {% else %}
                    <img src="https://placehold.co/600x400/1e1e2d/f02d73?text=Video" alt="Video">
                {% endif %}
                <div class="tag-premium">💎 PREMIUM</div>
                <div class="play-btn-overlay" onclick="playVideo('{{ file._id }}')"></div>
                <div class="video-info">
                    <div class="video-title">{{ file.title }}</div>
                    <div class="video-views">👁 {{ file.views }} views</div>
                </div>
            </div>
            {% else %}
            <p style="text-align:center; color:#aaa; margin-top:50px;">কোনো ভিডিও নেই।</p>
            {% endfor %}
        </div>
        
        <div class="search-fab">🔍</div>
    </div>

    <!-- PAGE: PREMIUM (BUY COINS) -->
    <div id="page-premium" class="page">
        <div style="display:flex; align-items:center; gap:10px; margin-bottom:20px;">
            <div onclick="switchPage('settings')" style="background:rgba(255,255,255,0.1); width:35px; height:35px; border-radius:50%; display:flex; justify-content:center; align-items:center; cursor:pointer;">←</div>
            <h2 style="margin:0;">কয়েন কিনুন (Buy Coins)</h2>
        </div>
        
        <div class="pkg-tabs">
            <div class="pkg-tab active" onclick="togglePkg('bks', this)">📱 বিকাশ/নগদ</div>
            <div class="pkg-tab" onclick="togglePkg('usd', this)">⚡ Instant (USD)</div>
        </div>

        <!-- BKASH PACKAGES -->
        <div id="pkg-bks" class="pkg-grid">
            <div class="pkg-card">
                <div class="most-popular">⭐ Most Popular</div>
                <div style="background:var(--gold); width:40px; height:40px; border-radius:50%; margin:0 auto; display:flex; justify-content:center; align-items:center; font-size:20px;">🏛</div>
                <h2>৳120</h2>
                <p>🏛 1000 Coins + 10 Bonus</p>
                <button class="btn-buy" onclick="reqBuy('bKash 120 BDT')">কিনুন (Buy)</button>
            </div>
            <div class="pkg-card">
                <div style="background:var(--gold); width:40px; height:40px; border-radius:50%; margin:0 auto; display:flex; justify-content:center; align-items:center; font-size:20px;">🏛</div>
                <h2>৳240</h2>
                <p>🏛 2000 Coins + 50 Bonus</p>
                <button class="btn-buy" onclick="reqBuy('bKash 240 BDT')">কিনুন (Buy)</button>
            </div>
        </div>

        <!-- USD PACKAGES -->
        <div id="pkg-usd" class="pkg-grid" style="display:none;">
            <div class="pkg-card">
                <div class="most-popular">⭐ Most Popular</div>
                <h2>$1</h2>
                <p>🏛 1000 Coins</p>
                <button class="btn-buy" onclick="reqBuy('USD $1')">কিনুন (Buy)</button>
            </div>
        </div>
    </div>

    <!-- PAGE: SETTINGS -->
    <div id="page-settings" class="page">
        <h2 style="margin-top:0;">⚙️ Settings</h2>
        
        <div class="balance-card">
            <h3>আপনার ব্যালেন্স (YOUR BALANCE)</h3>
            <h1>🏛 <span id="set-balance">0</span></h1>
            <p style="margin:0; color:#aaa; font-size:12px;">ID: <span id="set-id"></span></p>
        </div>

        <div class="menu-list">
            <div class="menu-item" onclick="switchPage('premium')">
                <div class="menu-left">
                    <span class="icon" style="background:#ff9a9e;">🪙</span>
                    <div>
                        <b style="display:block;">কয়েন কিনুন (Buy Coins)</b>
                        <small style="color:#aaa;">প্যাকেজ বেছে নিয়ে পেমেন্ট করুন</small>
                    </div>
                </div>
                <div>></div>
            </div>
            
            <div class="menu-item" onclick="switchPage('coupon')">
                <div class="menu-left">
                    <span class="icon" style="background:#a18cd1;">🎟</span>
                    <div>
                        <b style="display:block;">কুপন কোড (Coupon Code)</b>
                        <small style="color:#aaa;">কোড রিডিম করে ফ্রি কয়েন নিন</small>
                    </div>
                </div>
                <div>></div>
            </div>
            
            <div class="menu-item" onclick="switchPage('share')">
                <div class="menu-left">
                    <span class="icon" style="background:#ffecd2;">🎁</span>
                    <div>
                        <b style="display:block;">বন্ধুকে শেয়ার করুন (Share)</b>
                        <small style="color:#aaa;">ইনভাইট করে ফ্রি কয়েন জিতুন</small>
                    </div>
                </div>
                <div>></div>
            </div>
        </div>
    </div>

    <!-- PAGE: COUPON -->
    <div id="page-coupon" class="page">
        <div style="display:flex; align-items:center; gap:10px; margin-bottom:20px;">
            <div onclick="switchPage('settings')" style="background:rgba(255,255,255,0.1); width:35px; height:35px; border-radius:50%; display:flex; justify-content:center; align-items:center; cursor:pointer;">←</div>
            <h2 style="margin:0;">🎟 কুপন কোড</h2>
        </div>
        
        <div style="text-align:center; margin-bottom:20px;">
            <span style="font-size:60px;">🎁</span>
        </div>
        
        <input type="text" id="coupon-input" class="input-box" placeholder="কুপন কোড লিখুন (Enter coupon)">
        <button class="btn-main" onclick="redeemCoupon()">Redeem</button>
        
        <p style="color:#aaa; font-size:13px; text-align:center; margin-top:20px; line-height:1.6;">
            প্রতিটি কুপন কোড শুধুমাত্র একবারই ব্যবহার করা যাবে। কোড না জানলে আমাদের চ্যানেল/সাপোর্টে চোখ রাখুন।
        </p>
    </div>

    <!-- PAGE: SHARE -->
    <div id="page-share" class="page">
        <div style="display:flex; align-items:center; gap:10px; margin-bottom:20px;">
            <div onclick="switchPage('settings')" style="background:rgba(255,255,255,0.1); width:35px; height:35px; border-radius:50%; display:flex; justify-content:center; align-items:center; cursor:pointer;">←</div>
            <h2 style="margin:0;">🎁 বন্ধুকে শেয়ার করুন</h2>
        </div>
        
        <div style="text-align:center; margin-bottom:20px;">
            <span style="font-size:60px;">🎁</span>
        </div>

        <div class="share-box">
            🥳 আপনার বন্ধুকে ইনভাইট করুন! প্রতিজন বন্ধু আপনার লিংক দিয়ে বট স্টার্ট করলেই আপনি সাথে সাথে <b>🏛 10 Coins একদম ফ্রি</b> পেয়ে যাবেন — কোনো লিমিট নেই!
        </div>

        <p style="color:#aaa; font-size:12px; margin-bottom:5px;">আপনার রেফার লিংক (YOUR REFERRAL LINK)</p>
        <div class="copy-box">
            <span id="ref-link" style="font-size:13px; word-break:break-all;">https://t.me/{{ bot_username }}?start=</span>
            <div class="copy-btn" onclick="copyRef()">📋 Copy</div>
        </div>

        <button class="btn-main" style="background:var(--gold); color:black;" onclick="shareTg()">🚀 বন্ধুকে শেয়ার করুন</button>
    </div>

    <!-- BOTTOM NAVIGATION -->
    <div class="bottom-nav">
        <div class="nav-item active" onclick="switchNav('home', this)">
            <span>🏠</span> Home
        </div>
        <div class="nav-item" onclick="switchNav('premium', this)">
            <span>💎</span> Premium
        </div>
        <div class="nav-item" onclick="switchNav('settings', this)">
            <span>⚙️</span> Settings
        </div>
    </div>

    <script>
        let tg = window.Telegram.WebApp;
        tg.expand();
        let botUsername = "{{ bot_username }}";
        let userId = tg.initDataUnsafe.user ? tg.initDataUnsafe.user.id : 123456789; // Fallback for browser test
        
        // Initialize Data
        document.getElementById('set-id').innerText = userId;
        document.getElementById('ref-link').innerText += userId;
        
        // Fetch Balance
        async function loadUser() {
            let res = await fetch('/api/user/' + userId);
            let data = await res.json();
            document.getElementById('hdr-balance').innerText = data.balance;
            document.getElementById('set-balance').innerText = data.balance;
        }
        loadUser();

        // Check 18+ Modal
        if(!localStorage.getItem('ageVerified')){
            document.getElementById('age-modal').style.display = 'flex';
        }

        function confirmAge(isAdult) {
            if(isAdult) {
                localStorage.setItem('ageVerified', 'true');
                document.getElementById('age-modal').style.display = 'none';
            } else {
                tg.close();
            }
        }

        // Navigation Logic
        function switchPage(pageId) {
            document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
            document.getElementById('page-' + pageId).classList.add('active');
        }

        function switchNav(pageId, element) {
            switchPage(pageId);
            document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
            element.classList.add('active');
        }

        // Category Filter Logic (Fixing mixup issue)
        function filterCat(catName, btn) {
            document.querySelectorAll('.cat-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            
            let cards = document.querySelectorAll('.video-card');
            cards.forEach(card => {
                if(catName === 'All' || card.getAttribute('data-cat') === catName) {
                    card.style.display = 'block';
                } else {
                    card.style.display = 'none';
                }
            });
        }

        // Packages Tab Toggle
        function togglePkg(type, btn) {
            document.querySelectorAll('.pkg-tab').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            document.getElementById('pkg-bks').style.display = type === 'bks' ? 'grid' : 'none';
            document.getElementById('pkg-usd').style.display = type === 'usd' ? 'grid' : 'none';
        }

        // Video Play & Ad Logic (Fixed file sending)
        let currentDeepLink = "";
        async function playVideo(fileId) {
            currentDeepLink = 'https://t.me/' + botUsername + '?start=file_' + fileId;
            let res = await fetch('/api/get_ad/' + userId);
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
                        btn.onclick = () => {
                            tg.openTelegramLink(currentDeepLink);
                            setTimeout(() => { tg.close(); }, 500);
                        };
                    }
                }, 1000);
            } else {
                tg.openTelegramLink(currentDeepLink);
                setTimeout(() => { tg.close(); }, 500);
            }
        }

        // Coupon Logic
        async function redeemCoupon() {
            let code = document.getElementById('coupon-input').value;
            if(!code) return tg.showAlert("Please enter a code!");
            
            let res = await fetch('/api/redeem', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ uid: userId, code: code })
            });
            let data = await res.json();
            tg.showAlert(data.msg);
            if(data.status === 'success') {
                loadUser();
                document.getElementById('coupon-input').value = "";
            }
        }

        // Copy / Share Logic
        function copyRef() {
            let link = document.getElementById('ref-link').innerText;
            navigator.clipboard.writeText(link);
            tg.showAlert("✅ Link Copied!");
        }
        function shareTg() {
            let link = document.getElementById('ref-link').innerText;
            let text = encodeURIComponent("এই বটে জয়েন করে ফ্রি ১৮+ ভিডিও দেখুন! 🔥");
            tg.openTelegramLink(`https://t.me/share/url?url=${link}&text=${text}`);
        }

        // Buy Request
        function reqBuy(pkg) {
            tg.showAlert("✅ আপনি " + pkg + " সিলেক্ট করেছেন। এডমিনকে পেমেন্ট করুন।");
            // You can implement API call to send admin a notification here
        }
    </script>
</body>
</html>
"""

@web.route('/')
def home():
    files = list(sync_db["files"].find().sort("_id", -1))
    cats = list(sync_db["categories"].find())
    return render_template_string(HTML_TEMPLATE, files=files, cats=cats, bot_username=BOT_USERNAME)

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
            wait_time = e.value
            print(f"⚠️ Telegram Rate Limit! Waiting for {wait_time} seconds before retrying...")
            time.sleep(wait_time) 
        except Exception as e:
            print(f"❌ Core Error: {e}")
            break
