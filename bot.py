import os, sys, asyncio, threading, random, string, time, requests, json
from datetime import datetime

# --- Asyncio & Event Loop Fix ---
try: loop = asyncio.get_event_loop()
except RuntimeError: loop = asyncio.new_event_loop(); asyncio.set_event_loop(loop)

# --- OpenCV (Screenshot) Setup ---
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

# Clean Webhook to prevent bot freeze
try: requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook?drop_pending_updates=True")
except: pass

# ==========================================
# 2. DATABASE & BOT INITIALIZATION
# ==========================================
# Pyrogram in_memory=True is CRITICAL to prevent server hanging!
app = Client("shilacall_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, in_memory=True)
web = Flask(__name__)
admin_steps = {}

db_client, db = None, None
users_col, files_col, cats_col = None, None, None
pkgs_col, links_col, config_col, channels_col, coupons_col = None, None, None, None, None

sync_db = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)["ShilaCallApp"]

# Lazy DB Initialization to prevent Asyncio loop crash
async def get_db():
    global db_client, db, users_col, files_col, cats_col, pkgs_col, links_col, config_col, channels_col, coupons_col
    if db_client is None:
        db_client = AsyncIOMotorClient(MONGO_URI)
        db = db_client["ShilaCallApp"]
        users_col, files_col, cats_col = db["users"], db["files"], db["categories"]
        pkgs_col, links_col, config_col = db["packages"], db["ad_links"], db["config"]
        channels_col, coupons_col = db["channels"], db["coupons"]
    return db

async def get_config():
    await get_db()
    conf = await config_col.find_one({"_id": "settings"})
    if not conf:
        conf = {"_id": "settings", "ref_coin": 10, "auto_del_time": 0, "ads_on": True, "direk_wait": [5]}
        await config_col.insert_one(conf)
    return conf

not_cmd_filter = filters.create(lambda _, __, message: bool(message.text and not message.text.startswith("/")))

# ==========================================
# 3. COMMAND: MYID (Tests if bot is alive)
# ==========================================
@app.on_message(filters.command("myid"))
async def cmd_myid(client, message):
    await message.reply(f"✅ বট ঠিকভাবে কাজ করছে!\n🆔 আপনার আইডি: `{message.from_user.id}`")

# ==========================================
# 4. USER START & MUST JOIN
# ==========================================
@app.on_message(filters.command("start") & filters.private)
async def start_cmd(client, message):
    await get_db()
    user_id = message.from_user.id
    args = message.text.split()
    config = await get_config()
    
    user = await users_col.find_one({"_id": user_id})
    if not user:
        await users_col.insert_one({"_id": user_id, "name": message.from_user.first_name, "balance": 0, "pending_file": None})
        if len(args) > 1 and args[1].isdigit() and int(args[1]) != user_id:
            ref_by = int(args[1])
            await users_col.update_one({"_id": ref_by}, {"$inc": {"balance": config.get("ref_coin", 10)}})
            try: await client.send_message(ref_by, f"🎉 আপনার রেফারে একজন জয়েন করেছে! +{config.get('ref_coin', 10)} Coins")
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

    # Send file if pending
    if user.get("pending_file"):
        file_id = user["pending_file"]
        await users_col.update_one({"_id": user_id}, {"$set": {"pending_file": None}})
        file_data = await files_col.find_one({"_id": file_id})
        if file_data:
            await files_col.update_one({"_id": file_id}, {"$inc": {"views": 1}})
            msg = await message.reply("⏳ আপনার ভিডিও পাঠানো হচ্ছে...")
            try:
                await client.send_cached_media(chat_id=user_id, file_id=file_data["file_id"], caption=f"🎬 **{file_data['title']}**", protect_content=True)
                await msg.delete()
            except Exception as e: await msg.edit_text(f"❌ ফাইল পাঠাতে সমস্যা হয়েছে! {e}")
        else: await message.reply("❌ ফাইলটি পাওয়া যায়নি!")
        return

    profile_text = f"👋 **স্বাগতম Glow Top-এ!**\n\n🆔 **আপনার আইডি:** `{user_id}`\n💰 **আপনার ব্যালেন্স:** {user.get('balance', 0)} Coins\n\nনিচের বাটনে ক্লিক করে অ্যাপ ওপেন করুন 👇"
    btn = InlineKeyboardMarkup([[InlineKeyboardButton("🔥 Open Glow Top", web_app=WebAppInfo(url=f"{WEB_URL}/"))]])
    await message.reply(profile_text, reply_markup=btn)

@app.on_callback_query(filters.regex("check_join"))
async def check_join_cb(client, query):
    await get_db()
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
# 5. ADMIN COMMANDS (All working 100%)
# ==========================================
@app.on_message(filters.command("delpost") & filters.user(ADMIN_ID))
async def cmd_delpost(client, message):
    await get_db()
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
    await get_db()
    try:
        parts = message.text.split()
        await channels_col.insert_one({"chat_id": int(parts[1]), "link": parts[2]}); await message.reply("✅ Channel Added!")
    except: await message.reply("Format: /addchannel -100xxx https://t.me/xyz")

@app.on_message(filters.command("delchannel") & filters.user(ADMIN_ID))
async def cmd_delchannel(client, message):
    await get_db()
    chs = await channels_col.find().to_list(100)
    buttons = [[InlineKeyboardButton(f"❌ {c['chat_id']}", callback_data=f"delch_{c['_id']}")] for c in chs]
    await message.reply("ডিলিট করতে ক্লিক করুন:", reply_markup=InlineKeyboardMarkup(buttons) if buttons else None)

@app.on_callback_query(filters.regex(r"^delch_") & filters.user(ADMIN_ID))
async def delch_cb(client, query):
    await get_db()
    from bson.objectid import ObjectId
    await channels_col.delete_one({"_id": ObjectId(query.data.split("_")[1])}); await query.message.edit_text("✅ ডিলিট সম্পন্ন হয়েছে!")

@app.on_message(filters.command("broadcast") & filters.user(ADMIN_ID))
async def cmd_broadcast(client, message):
    await get_db()
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
    await get_db()
    try:
        parts = message.text.split()
        await coupons_col.insert_one({"code": parts[1], "coins": int(parts[2]), "limit": int(parts[3]), "used_by": []})
        await message.reply(f"✅ কুপন অ্যাড হয়েছে: {parts[1]}")
    except: await message.reply("Format: /addcoupon CODE 50 100")

# ==========================================
# 6. UPLOAD POST & SCREENSHOT (FIXED FOR ALL MEDIA)
# ==========================================
def upload_to_telegraph(file_path):
    try:
        with open(file_path, 'rb') as f:
            res = requests.post('https://telegra.ph/upload', files={'file': ('file.jpg', f, 'image/jpeg')}).json()
        return "https://telegra.ph" + res[0]['src']
    except Exception as e:
        print(f"Telegraph Error: {e}")
        return None

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
        await message.reply("৪. এবার ভিডিও, ডকুমেন্ট, বা অডিও সেন্ড করুন:")

@app.on_message((filters.video | filters.document | filters.audio) & filters.user(ADMIN_ID) & filters.private)
async def handle_admin_file(client, message):
    step = admin_steps.get(ADMIN_ID, {}).get("step")
    if step == "file":
        await get_db()
        msg = await message.reply("⏳ ফাইল প্রসেস হচ্ছে, স্ক্রিনশট নিচ্ছি...")
        short_id = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
        
        file_id = message.video.file_id if message.video else (message.document.file_id if message.document else message.audio.file_id)
        thumb_url = ""

        # Attempt 1: Pyrogram native thumbnail
        media_obj = message.video or message.document
        if media_obj and hasattr(media_obj, 'thumbs') and media_obj.thumbs:
            try:
                thumb_path = f"{short_id}.jpg"
                await client.download_media(media_obj.thumbs[0].file_id, file_name=thumb_path)
                thumb_url = await asyncio.to_thread(upload_to_telegraph, thumb_path)
                os.remove(thumb_path)
            except: pass
            
        # Attempt 2: OpenCV Screenshot (10th frame)
        if not thumb_url and not message.audio and HAS_CV2:
            try:
                await msg.edit_text("⏳ সার্ভারে ফাইলটি ডাউনলোড করা হচ্ছে (একটু সময় লাগতে পারে)...")
                video_path = await client.download_media(file_id, file_name=f"{short_id}.mp4")
                
                await msg.edit_text("⏳ স্ক্রিনশট ফ্রেম কাটা হচ্ছে...")
                cap = cv2.VideoCapture(video_path)
                cap.set(cv2.CAP_PROP_POS_FRAMES, 10) # Black screen এড়াতে ১০ নাম্বার ফ্রেম
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
            except Exception as e: print(f"CV2 Error: {e}")

        # Fallback if no screenshot found
        if not thumb_url:
            thumb_url = "https://placehold.co/600x400/1c1c24/ff007f?text=Media"

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
        await msg.edit_text(f"✅ মিডিয়া সফলভাবে সেভ হয়েছে!\nPost ID: `{short_id}`")

# ==========================================
# 7. WEB API (FLASK)
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
    if not coupon: return jsonify({"status": "error", "msg": "❌ Invalid Coupon Code!"})
    if uid in coupon.get("used_by", []): return jsonify({"status": "error", "msg": "❌ You already used this!"})
    if len(coupon.get("used_by", [])) >= coupon.get("limit", 0): return jsonify({"status": "error", "msg": "❌ Coupon limit reached!"})
    
    sync_db["coupons"].update_one({"code": code}, {"$push": {"used_by": uid}})
    sync_db["users"].update_one({"_id": uid}, {"$inc": {"balance": coupon["coins"]}})
    try: asyncio.run_coroutine_threadsafe(app.send_message(uid, f"🎉 কুপন রিডিম সফল! +{coupon['coins']} Coins"), loop)
    except: pass
    return jsonify({"status": "success", "msg": f"✅ Successfully redeemed {coupon['coins']} coins!"})

@web.route('/api/user/<int:user_id>')
def get_user(user_id):
    user = sync_db["users"].find_one({"_id": user_id})
    return jsonify({"balance": user.get("balance", 0) if user else 0})

# ==========================================
# 8. HTML UI (EXACT GLOW TOP DESIGN & LOGIC)
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
        @import url('https://fonts.googleapis.com/css2?family=Hind+Siliguri:wght@400;600;700&display=swap');
        
        body { 
            background: linear-gradient(180deg, #18091c 0%, #081016 100%); 
            color: #fff; font-family: 'Hind Siliguri', sans-serif; 
            margin: 0; padding-bottom: 90px; min-height: 100vh;
        }
        * { box-sizing: border-box; }
        
        /* HEADER */
        .header { display: flex; justify-content: space-between; padding: 15px 20px; align-items: center; }
        .logo { font-size: 20px; font-weight: bold; }
        .coin-pill { background: #ffb703; color: #000; padding: 5px 12px; border-radius: 20px; font-weight: bold; font-size: 14px;}
        
        /* PAGE & NAV */
        .page { display: none; padding: 15px; }
        .page.active { display: block; animation: fadeIn 0.3s ease-in-out; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
        
        .bottom-nav { position: fixed; bottom: 0; width: 100%; background: rgba(14,20,30,0.95); display: flex; justify-content: space-around; padding: 10px 0; border-top: 1px solid rgba(255,255,255,0.05); backdrop-filter: blur(10px); z-index:100;}
        .nav-item { display: flex; flex-direction: column; align-items: center; font-size: 11px; color: #777; cursor: pointer; padding: 5px 20px; border-radius: 12px;}
        .nav-item.active { color: #fff; background: rgba(255,255,255,0.05); }
        .nav-item span { font-size: 22px; margin-bottom: 2px; filter: grayscale(100%); }
        .nav-item.active span { filter: grayscale(0%); }

        /* SEARCH & CATEGORIES */
        .search-box { width: 100%; padding: 14px 20px; border-radius: 12px; border: 1px solid rgba(255,255,255,0.1); background: rgba(0,0,0,0.4); color: white; outline: none; margin-bottom: 15px; font-size: 15px; font-family: 'Hind Siliguri', sans-serif;}
        .cat-scroll { display: flex; overflow-x: auto; gap: 10px; padding-bottom: 10px; margin-bottom: 15px; scrollbar-width: none; }
        .cat-btn { background: rgba(255,255,255,0.05); padding: 8px 18px; border-radius: 25px; font-size: 13px; cursor: pointer; white-space: nowrap; border: 1px solid rgba(255,255,255,0.1);}
        .cat-btn.active { background: linear-gradient(90deg, #f02d73, #00d4ff); color: white; border:none; font-weight:bold;}

        /* VIDEO CARDS */
        .video-card { background: rgba(25,25,35,0.8); border-radius: 12px; margin-bottom: 20px; overflow: hidden; position: relative; border: 1px solid rgba(255,255,255,0.05);}
        .video-card img { width: 100%; height: 210px; object-fit: cover; }
        .tag-premium { position: absolute; top: 12px; left: 12px; background: #c72cff; padding: 4px 12px; border-radius: 15px; font-size: 11px; font-weight: bold; box-shadow: 0 2px 10px rgba(199,44,255,0.5);}
        .play-btn-overlay { position: absolute; top: 40%; left: 50%; transform: translate(-50%, -50%); width: 55px; height: 55px; background: rgba(0,123,255,0.8); border-radius: 50%; display: flex; justify-content: center; align-items: center; cursor: pointer; backdrop-filter: blur(5px); box-shadow: 0 0 15px rgba(0,123,255,0.4);}
        .play-btn-overlay::after { content: '▶'; color: white; font-size: 22px; margin-left: 4px;}
        .video-info { padding: 15px; }

        /* PAGINATION */
        .pagination { display: flex; justify-content: space-between; align-items: center; margin-top: 15px; }
        .page-btn { background: linear-gradient(90deg, #f02d73, #ff6b6b); color: white; border: none; padding: 10px 20px; border-radius: 8px; cursor: pointer; font-weight:bold;}
        .page-btn:disabled { background: rgba(255,255,255,0.1); color:#666;}

        /* SETTINGS & SHARE PAGES (Exact Design) */
        .balance-card { background: linear-gradient(135deg, #4b2354, #1b1c29); border-radius: 15px; padding: 25px; text-align: center; margin-bottom: 20px; border: 1px solid rgba(255,255,255,0.05);}
        .set-item { display: flex; align-items: center; background: rgba(255,255,255,0.03); padding: 15px; border-radius: 12px; border: 1px solid rgba(255,255,255,0.05); margin-bottom: 12px; cursor:pointer;}
        .set-icon { width: 45px; height: 45px; border-radius: 12px; display: flex; justify-content: center; align-items: center; font-size: 20px; margin-right: 15px;}
        
        .share-banner { background: rgba(0,255,100,0.05); border: 1px solid rgba(0,255,100,0.2); padding: 20px; border-radius: 12px; font-size: 14px; line-height: 1.6; margin-bottom: 25px;}
        .ref-box { display: flex; background: rgba(255,255,255,0.05); border-radius: 10px; border: 1px solid rgba(255,255,255,0.1); margin-bottom: 25px; overflow:hidden;}
        .ref-box input { flex: 1; background: transparent; border: none; color: white; padding: 15px; font-size: 14px; outline:none;}
        .ref-box button { background: rgba(255,255,255,0.1); color: #00d4ff; border: none; padding: 0 20px; font-weight:bold; cursor:pointer;}

        /* BUTTONS & MODALS */
        .btn-main { width: 100%; background: linear-gradient(90deg, #f02d73, #ff6b6b); padding: 16px; border-radius: 12px; font-weight: bold; border: none; color: white; font-size: 16px; cursor: pointer; font-family: 'Hind Siliguri', sans-serif;}
        .modal-overlay { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(8,16,22,0.95); z-index: 999; justify-content: center; align-items: center; backdrop-filter: blur(5px);}
        .modal-box { background: rgba(30, 30, 45, 0.95); padding: 30px 25px; border-radius: 20px; text-align: center; width: 90%; max-width: 400px; border: 1px solid rgba(255,255,255,0.05);}
        .alert-box { background: rgba(255,0,0,0.1); border: 1px solid #ff4d4d; color: #ffb3b3; padding: 15px; border-radius: 12px; font-size: 13px; margin: 15px 0;}
    </style>
</head>
<body>
    <div class="header">
        <div class="logo">Glow Top</div>
        <div class="coin-pill">🏛 <span id="hdr-balance">0</span></div>
    </div>

    <!-- 18+ AGE MODAL -->
    <div id="age-modal" class="modal-overlay">
        <div class="modal-box">
            <div style="font-size: 55px; margin-bottom:10px;">🔞</div>
            <h2 style="margin-top:0;">বয়স নিশ্চিতকরণ</h2>
            <p style="font-size:14px; color:#aaa;">এই ওয়েবসাইটের কনটেন্ট শুধুমাত্র <b style="color:#00d4ff;">১৮ বছর বা তার বেশি বয়সী</b> ব্যবহারকারীদের জন্য প্রযোজ্য।</p>
            <div class="alert-box">⚠️ আপনার বয়স ১৮ বছরের কম হলে অনুগ্রহ করে এই সাইট ব্যবহার করবেন না এবং এখনই প্রস্থান করুন।</div>
            <button class="btn-main" style="background: linear-gradient(90deg, #00d4ff, #00ffcc); color:black; margin-bottom:10px;" onclick="confirmAge()">✅ হ্যাঁ, আমার বয়স ১৮+ বছর</button>
            <button class="btn-main" style="background: transparent; border: 1px solid #555; color: #888;" onclick="tg.close()">❌ না, আমার বয়স ১৮ বছরের কম</button>
        </div>
    </div>

    <!-- AD TIMER MODAL -->
    <div id="ad-overlay" class="modal-overlay">
        <div class="modal-box" style="background:transparent; border:none; box-shadow:none;">
            <h1 id="timer-count" style="font-size:90px; color:#f02d73; margin:0;">5</h1>
            <p style="font-size:16px; color:#aaa;">অ্যাড দেখার পর ফাইলটি ইনবক্সে পাবেন</p>
            <button id="get-file-btn" class="btn-main" style="background: linear-gradient(90deg, #00d4ff, #00ffcc); color:black; display:none;">Get File Now</button>
        </div>
    </div>

    <!-- PAGE: HOME -->
    <div id="page-home" class="page active">
        <input type="text" id="search-bar" class="search-box" placeholder="🔍 Search videos..." onkeyup="handleSearch()">
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
            <span id="page-info" style="color:#888; font-size:14px;">Page 1</span>
            <button class="page-btn" id="next-btn" onclick="changePage(1)">Next →</button>
        </div>
    </div>

    <!-- PAGE: SETTINGS -->
    <div id="page-settings" class="page">
        <div class="balance-card">
            <p style="margin:0; color:#aaa; font-size:12px; letter-spacing:1px;">আপনার ব্যালেন্স (YOUR BALANCE)</p>
            <h1 style="color:#ffb703; margin:15px 0 10px 0; font-size:48px;">🏛 <span id="set-balance">0</span></h1>
            <p style="margin:0; color:#666; font-size:12px;">ID: <span id="set-id"></span></p>
        </div>
        
        <div class="set-item" onclick="switchNav('premium')">
            <div class="set-icon" style="background: linear-gradient(135deg, #ff9a9e, #fecfef);">🪙</div>
            <div>
                <b style="display:block; font-size:16px;">কয়েন কিনুন (Buy Coins)</b>
                <span style="color:#aaa; font-size:12px;">প্যাকেজ বেছে নিয়ে পেমেন্ট করুন</span>
            </div>
        </div>
        <div class="set-item" onclick="switchNav('coupon')">
            <div class="set-icon" style="background: linear-gradient(135deg, #a18cd1, #fbc2eb);">🎟</div>
            <div>
                <b style="display:block; font-size:16px;">কুপন কোড (Coupon Code)</b>
                <span style="color:#aaa; font-size:12px;">কোড রিডিম করে ফ্রি কয়েন নিন</span>
            </div>
        </div>
        <div class="set-item" onclick="switchNav('share')">
            <div class="set-icon" style="background: linear-gradient(135deg, #ffecd2, #fcb69f);">🎁</div>
            <div>
                <b style="display:block; font-size:16px;">বন্ধুকে শেয়ার করুন (Share Friend)</b>
                <span style="color:#aaa; font-size:12px;">ইনভাইট করে ফ্রি কয়েন জিতুন</span>
            </div>
        </div>
    </div>

    <!-- PAGE: COUPON -->
    <div id="page-coupon" class="page">
        <h2 style="margin-top:0;">🎟 কুপন কোড (Coupon Code)</h2>
        <div style="text-align:center; margin:40px 0;">
            <div style="font-size:70px; background: rgba(240, 45, 115, 0.1); width:130px; height:130px; line-height:130px; border-radius:35px; margin:0 auto;">🎁</div>
        </div>
        <div style="display:flex; gap:10px; margin-bottom:20px;">
            <input type="text" id="coupon-input" class="search-box" style="margin:0; border-radius:12px;" placeholder="কুপন কোড লিখুন (Enter coupon)">
            <button class="btn-main" style="width:auto; margin:0; padding:0 25px;" onclick="redeemCoupon()">Redeem</button>
        </div>
        <p style="color:#888; font-size:13px; text-align:center; line-height:1.6;">
            প্রতিটি কুপন কোড শুধুমাত্র একবারই ব্যবহার করা যাবে। কোড না জানলে আমাদের চ্যানেল/সাপোর্টে চোখ রাখুন!
        </p>
    </div>

    <!-- PAGE: SHARE -->
    <div id="page-share" class="page">
        <h2 style="margin-top:0;">🎁 বন্ধুকে শেয়ার করুন (Share)</h2>
        <div class="share-banner">
            🥳 আপনার বন্ধুকে ইনভাইট করুন! প্রতিজন বন্ধু আপনার লিংক দিয়ে বট স্টার্ট করলেই আপনি সাথে সাথে <b style="color:#ffb703;">🏛 10 Coins একদম ফ্রি</b> পেয়ে যাবেন — কোনো লিমিট নেই! 🚀
        </div>
        <p style="color:#aaa; font-size:12px; margin-bottom:8px;">আপনার রেফার লিংক (YOUR REFERRAL LINK)</p>
        <div class="ref-box">
            <input type="text" id="ref-link" readonly>
            <button onclick="copyRef()">📋 Copy</button>
        </div>
        <button class="btn-main" style="background: #ffb703; color: black; font-size: 17px;" onclick="reqBuy()">🚀 বন্ধুকে শেয়ার করুন</button>
    </div>

    <!-- PAGE: PREMIUM -->
    <div id="page-premium" class="page">
        <h2 style="margin-top:0;">কয়েন কিনুন (Buy Coins)</h2>
        <div style="display:flex; gap:10px; margin-bottom:20px;">
            <div class="cat-btn active" style="flex:1; text-align:center; border-radius:12px;" onclick="togglePkg('bks', this)">📱 বিকাশ/নগদ</div>
            <div class="cat-btn" style="flex:1; text-align:center; border-radius:12px;" onclick="togglePkg('usd', this)">⚡ Instant (USD)</div>
        </div>
        
        <div id="pkg-bks">
            {% for pkg in pkgs if pkg.type == 'bkash' %}
            <div style="background: rgba(255,255,255,0.03); border: 1px solid #ffb703; padding: 20px; border-radius: 15px; margin-bottom: 15px; text-align: center; position: relative;">
                <div style="position: absolute; top: -12px; left: 50%; transform: translateX(-50%); background: #ffb703; color: black; font-size: 11px; font-weight: bold; padding: 4px 15px; border-radius: 12px;">⭐ Most Popular</div>
                <div style="font-size:35px; margin-bottom:10px;">🏛</div>
                <h2 style="margin:0 0 5px 0; font-size:24px;">{{ pkg.details.split('=')[0] if '=' in pkg.details else pkg.details }}</h2>
                <p style="color:#aaa; font-size:14px; margin:0 0 15px 0;">{{ pkg.details.split('=')[1] if '=' in pkg.details else pkg.details }} Coins</p>
                <button class="btn-main" style="margin:0; padding:12px;" onclick="reqBuy()">কিনুন (Buy)</button>
            </div>
            {% endfor %}
        </div>
        
        <div id="pkg-usd" style="display:none;">
            {% for pkg in pkgs if pkg.type == 'usd' %}
            <div style="background: rgba(255,255,255,0.03); border: 1px solid #00d4ff; padding: 20px; border-radius: 15px; margin-bottom: 15px; text-align: center; position: relative;">
                <div style="position: absolute; top: -12px; left: 50%; transform: translateX(-50%); background: #00d4ff; color: black; font-size: 11px; font-weight: bold; padding: 4px 15px; border-radius: 12px;">⚡ Instant</div>
                <div style="font-size:35px; margin-bottom:10px;">💲</div>
                <h2 style="margin:0 0 5px 0; font-size:24px;">{{ pkg.details.split('=')[0] if '=' in pkg.details else pkg.details }}</h2>
                <p style="color:#aaa; font-size:14px; margin:0 0 15px 0;">{{ pkg.details.split('=')[1] if '=' in pkg.details else pkg.details }} Coins</p>
                <button class="btn-main" style="margin:0; padding:12px; background:linear-gradient(90deg, #00d4ff, #00ffcc); color:black;" onclick="reqBuy()">কিনুন (Buy)</button>
            </div>
            {% endfor %}
        </div>
    </div>

    <!-- BOTTOM NAV -->
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
        function confirmAge() { localStorage.setItem('ageVerified', 'true'); document.getElementById('age-modal').style.display = 'none'; }

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
            document.querySelectorAll('.cat-btn').forEach(t => t.classList.remove('active'));
            element.classList.add('active');
            document.getElementById('pkg-bks').style.display = type === 'bks' ? 'block' : 'none';
            document.getElementById('pkg-usd').style.display = type === 'usd' ? 'block' : 'none';
        }

        // Search & Pagination Logic
        let allFiles = {{ files_json | safe }};
        let filteredFiles = [...allFiles];
        let currentPage = 1;
        let itemsPerPage = 10;

        function renderVideos() {
            let start = (currentPage - 1) * itemsPerPage;
            let end = start + itemsPerPage;
            let pageFiles = filteredFiles.slice(start, end);
            
            let html = "";
            if(pageFiles.length === 0) { html = "<p style='text-align:center; color:#666; margin-top:40px; font-size:16px;'>কোনো ভিডিও পাওয়া যায়নি!</p>"; }
            
            pageFiles.forEach(f => {
                html += `<div class="video-card">
                    <img src="${f.thumb_url || 'https://placehold.co/600x400/1c1c24/ff007f?text=Media'}">
                    ${f.is_premium ? '<div class="tag-premium">💎 PREMIUM</div>' : ''}
                    <div class="play-btn-overlay" onclick="playVideo('${f._id}')"></div>
                    <div class="video-info">
                        <b style="font-size:15px; display:block; margin-bottom:5px;">${f.title}</b>
                        <small style="color:#aaa;">👁 ${f.views} views</small>
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

        // Ads & Play
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

        // Actions
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
# 9. RUN SERVERS
# ==========================================
def run_flask(): 
    port = int(os.environ.get("PORT", 8080))
    web.run(host="0.0.0.0", port=port, debug=False)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    while True:
        try:
            print("🚀 Starting Bot & UI (Safe Mode)...")
            app.run()
            break  
        except FloodWait as e:
            print(f"⚠️ Rate Limit: Waiting {e.value} seconds...")
            time.sleep(e.value) 
        except Exception as e:
            print(f"❌ Core Error: {e}")
            break
