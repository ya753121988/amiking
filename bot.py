import os, sys, asyncio, threading, random, string, time, requests, json
from datetime import datetime, timedelta

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
from bson.objectid import ObjectId

# ==========================================
# 1. CONFIGURATION
# ==========================================
API_ID = int(os.environ.get("API_ID", 29904834))
API_HASH = os.environ.get("API_HASH", "8b4fd9ef578af114502feeafa2d31938")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8206083172:AAHP9raleY3l2R2HBTGSVCdpcLQvgn960Mw")
MONGO_URI = os.environ.get("MONGO_URI", "mongodb+srv://akash:akash@cluster0.etisrpx.mongodb.net/?appName=Cluster0")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 7120801813))
WEB_URL = os.environ.get("WEB_URL", "https://amiking.onrender.com")

DEFAULT_ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "Sudo_king") 
BOT_USERNAME = "PronWaliZone_Bot" 

try: requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook?drop_pending_updates=True")
except: pass

# ==========================================
# 2. DATABASE & BOT INITIALIZATION
# ==========================================
app = Client("shilacall_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, in_memory=True)
web = Flask(__name__)
admin_steps = {}

db_client, db = None, None
users_col, files_col, cats_col = None, None, None
pkgs_col, links_col, config_col, channels_col, coupons_col = None, None, None, None, None

sync_db = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)["ShilaCallApp"]

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
        conf = {
            "_id": "settings", "ref_coin": 10, "ref_on": True, 
            "auto_del_time": 0, "autodel_text": "⏳ ফাইলটি নির্দিষ্ট সময় পর অটো ডিলিট হয়ে যাবে।",
            "frotect": False, "ads_on": True, "direk_wait": [5], "prem_vid_wait": 10,
            "start_logo": None, "start_text": "", "payment_admin": DEFAULT_ADMIN_USERNAME,
            "autovid_msg_id": None, "autovid_text": "🎬 কিভাবে ভিডিও ডাউনলোড করবেন দেখে নিন!", "autovid_time_min": 0,
            "autopost_time_hr": 0, "autopost_idx": 0
        }
        await config_col.insert_one(conf)
    return conf

not_cmd_filter = filters.create(lambda _, __, message: bool(message.text and not message.text.startswith("/")))

# ==========================================
# AUTO DELETE TASK
# ==========================================
async def delete_msg_later(client, chat_id, msg_id, delay):
    await asyncio.sleep(delay)
    try: await client.delete_messages(chat_id, msg_id)
    except: pass

# ==========================================
# BACKGROUND TASKS (AUTO POST & AUTO VID)
# ==========================================
async def background_tasks():
    await app.start()
    last_autovid = time.time()
    last_autopost = time.time()
    
    while True:
        await asyncio.sleep(60)
        now = time.time()
        try:
            config = await get_config()
            
            # Auto Vid Logic
            av_min = config.get("autovid_time_min", 0)
            if av_min > 0 and config.get("autovid_msg_id") and (now - last_autovid) >= (av_min * 60):
                users = await users_col.find().to_list(None)
                for u in users:
                    if u.get("last_autovid_msg"):
                        try: await app.delete_messages(u["_id"], u["last_autovid_msg"])
                        except: pass
                    try:
                        msg = await app.copy_message(u["_id"], ADMIN_ID, config["autovid_msg_id"])
                        await users_col.update_one({"_id": u["_id"]}, {"$set": {"last_autovid_msg": msg.id}})
                        await asyncio.sleep(0.05)
                    except: pass
                last_autovid = time.time()
            
            # Auto Post Logic
            ap_hr = config.get("autopost_time_hr", 0)
            if ap_hr > 0 and (now - last_autopost) >= (ap_hr * 3600):
                idx = config.get("autopost_idx", 0)
                files = await files_col.find().sort("_id", 1).to_list(None)
                if files:
                    if idx >= len(files): idx = 0
                    tgt_file = files[idx]
                    users = await users_col.find().to_list(None)
                    btn = InlineKeyboardMarkup([[InlineKeyboardButton("🎬 Watch Now", web_app=WebAppInfo(url=f"{WEB_URL}/"))]])
                    for u in users:
                        try:
                            await app.send_photo(u["_id"], photo=tgt_file.get("thumb_url", "https://placehold.co/600x400/1c1c24/ff007f?text=Media"), caption=f"🔥 **New Video Available!**\n\nTitle: {tgt_file['title']}\n\n👇 Click below to watch!", reply_markup=btn)
                            await asyncio.sleep(0.05)
                        except: pass
                    await config_col.update_one({"_id": "settings"}, {"$set": {"autopost_idx": idx + 1}})
                last_autopost = time.time()
        except Exception as e: print(f"BG Task Error: {e}")

# ==========================================
# 3. USER START, MYID & JOIN CHECK
# ==========================================
@app.on_message(filters.command("myid"))
async def cmd_myid(client, message):
    await message.reply(f"✅ বট ঠিকভাবে কাজ করছে!\n🆔 আপনার আইডি: `{message.from_user.id}`")

@app.on_message(filters.command("start") & filters.private)
async def start_cmd(client, message):
    await get_db()
    user_id = message.from_user.id
    args = message.text.split()
    config = await get_config()
    
    user = await users_col.find_one({"_id": user_id})
    if not user:
        await users_col.insert_one({
            "_id": user_id, "name": message.from_user.first_name, 
            "balance": 0, "pending_file": None, "premium_until": None
        })
        if len(args) > 1 and args[1].isdigit() and int(args[1]) != user_id:
            ref_by = int(args[1])
            if config.get("ref_on", True):
                await users_col.update_one({"_id": ref_by}, {"$inc": {"balance": config.get("ref_coin", 10)}})
                try: await client.send_message(ref_by, f"🎉 আপনার রেফারে একজন জয়েন করেছে! +{config.get('ref_coin', 10)} Coins")
                except: pass
        user = await users_col.find_one({"_id": user_id})

    if len(args) > 1 and args[1].startswith("file_"):
        pending_file = args[1].replace("file_", "")
        await users_col.update_one({"_id": user_id}, {"$set": {"pending_file": pending_file}})
        user["pending_file"] = pending_file

    channels = await channels_col.find({"type": "must_join"}).to_list(100)
    not_joined = []
    for ch in channels:
        try: await client.get_chat_member(ch["chat_id"], user_id)
        except UserNotParticipant: not_joined.append(ch["link"])
        except: pass

    if not_joined:
        buttons = [[InlineKeyboardButton("📢 Join Channel", url=link)] for link in not_joined]
        buttons.append([InlineKeyboardButton("✅ Joined", callback_data="check_join")])
        return await message.reply("❌ আপনাকে আগে আমাদের চ্যানেলগুলোতে জয়েন করতে হবে:", reply_markup=InlineKeyboardMarkup(buttons))

    if user.get("pending_file"):
        file_id = user["pending_file"]
        await users_col.update_one({"_id": user_id}, {"$set": {"pending_file": None}})
        file_data = await files_col.find_one({"_id": file_id})
        
        if file_data:
            await files_col.update_one({"_id": file_id}, {"$inc": {"views": 1}})
            msg = await message.reply("⏳ আপনার ফাইল পাঠানো হচ্ছে...")
            try:
                sent_msg = await client.send_cached_media(
                    chat_id=user_id, file_id=file_data["file_id"], 
                    caption=f"🎬 **{file_data['title']}**", 
                    protect_content=config.get("frotect", False)
                )
                await msg.delete()
                
                del_time = config.get("auto_del_time", 0)
                if del_time > 0:
                    del_text = config.get("autodel_text", f"⏳ ফাইলটি {del_time} সেকেন্ড পর অটো ডিলিট হয়ে যাবে।")
                    await client.send_message(user_id, f"⚠️ {del_text}")
                    asyncio.create_task(delete_msg_later(client, user_id, sent_msg.id, del_time))
                    
            except Exception as e: await msg.edit_text(f"❌ ফাইল পাঠাতে সমস্যা হয়েছে! {e}")
        else: await message.reply("❌ ফাইলটি পাওয়া যায়নি!")
        return

    full_name = f"{message.from_user.first_name} {message.from_user.last_name or ''}".strip()
    first_name = message.from_user.first_name
    last_name = message.from_user.last_name or "N/A"
    username = f"@{message.from_user.username}" if message.from_user.username else "N/A"

    profile_text = f"👋 **স্বাগতম Glow Top-এ!**\n\n"
    profile_text += f"👤 **Full Name:** {full_name}\n🔹 **First Name:** {first_name}\n🔸 **Last Name:** {last_name}\n"
    profile_text += f"🆔 **User ID:** `{user_id}`\n🌐 **Username:** {username}\n💰 **Balance:** {user.get('balance', 0)} Coins\n"
    
    if config.get("start_text"): profile_text += f"\n📝 {config.get('start_text')}\n"
    profile_text += "\n👇 নিচের বাটনগুলো থেকে অ্যাপ ওপেন করুন বা চ্যানেলে যুক্ত হোন:"

    inline_channels = await channels_col.find({"type": "inline"}).to_list(100)
    buttons = [[InlineKeyboardButton(ch["name"], url=ch["link"])] for ch in inline_channels]
    buttons.insert(0, [InlineKeyboardButton("🔥 Open Glow Top", web_app=WebAppInfo(url=f"{WEB_URL}/"))])

    if config.get("start_logo"):
        try: await client.send_photo(user_id, photo=config.get("start_logo"), caption=profile_text, reply_markup=InlineKeyboardMarkup(buttons))
        except: await message.reply(profile_text, reply_markup=InlineKeyboardMarkup(buttons))
    else:
        await message.reply(profile_text, reply_markup=InlineKeyboardMarkup(buttons))

@app.on_callback_query(filters.regex("check_join"))
async def check_join_cb(client, query):
    await get_db()
    user_id = query.from_user.id
    channels = await channels_col.find({"type": "must_join"}).to_list(100)
    for ch in channels:
        try: await client.get_chat_member(ch["chat_id"], user_id)
        except: return await query.answer("❌ আপনি এখনো সব চ্যানেলে জয়েন করেননি!", show_alert=True)
    
    await query.message.delete()
    class FakeMsg:
        def __init__(self, from_user): self.from_user = from_user; self.text = "/start"
        async def reply(self, *args, **kwargs): return await client.send_message(user_id, *args, **kwargs)
    await start_cmd(client, FakeMsg(query.from_user))

# ==========================================
# 4. ADMIN: STATS, ADMIN, AD-LINKS
# ==========================================
@app.on_message(filters.command("stats") & filters.user(ADMIN_ID))
async def cmd_stats(client, message):
    await get_db()
    total_u = await users_col.count_documents({})
    total_f = await files_col.count_documents({})
    prem_u = await users_col.count_documents({"premium_until": {"$gt": datetime.now()}})
    reg_u = total_u - prem_u
    
    text = f"📊 **Bot Statistics:**\n\n"
    text += f"👥 Total Users: {total_u}\n"
    text += f"🎬 Total Files: {total_f}\n"
    text += f"💎 Premium Members: {prem_u}\n"
    text += f"👤 Regular Members: {reg_u}\n"
    await message.reply(text)

@app.on_message(filters.command("addadmin") & filters.user(ADMIN_ID))
async def cmd_addadmin(client, message):
    await get_db()
    try:
        username = message.text.split()[1].replace("@", "")
        await config_col.update_one({"_id": "settings"}, {"$set": {"payment_admin": username}})
        await message.reply(f"✅ Payment Admin Set to: `@{username}`")
    except: await message.reply("Format: `/addadmin @username`")

@app.on_message(filters.command("addlink") & filters.user(ADMIN_ID))
async def cmd_addlink(client, message):
    await get_db()
    try:
        link = message.text.split()[1]
        await links_col.insert_one({"link": link})
        await message.reply("✅ Ad Link Added Successfully!")
    except: await message.reply("Format: `/addlink https://ad-link.com`")

@app.on_message(filters.command("delink") & filters.user(ADMIN_ID))
async def cmd_dellink(client, message):
    await get_db()
    links = await links_col.find().to_list(100)
    btns = [[InlineKeyboardButton(f"❌ {c['link'][:20]}...", callback_data=f"dellink_{c['_id']}")] for c in links]
    await message.reply("ডিলিট করতে লিংকে ক্লিক করুন:", reply_markup=InlineKeyboardMarkup(btns) if btns else None)

@app.on_callback_query(filters.regex(r"^dellink_") & filters.user(ADMIN_ID))
async def dellink_cb(client, query):
    await get_db()
    await links_col.delete_one({"_id": ObjectId(query.data.split("_")[1])})
    await query.message.edit_text("✅ Ad Link Deleted!")

# ==========================================
# 5. ADMIN: CHANNELS, TEXT, LOGO & TASKS
# ==========================================
@app.on_message(filters.command("addcnl") & filters.user(ADMIN_ID))
async def cmd_addcnl(client, message):
    await get_db()
    try:
        parts = message.text.split(maxsplit=2)
        await channels_col.insert_one({"type": "inline", "name": parts[1], "link": parts[2]})
        await message.reply("✅ Channel button added!")
    except: await message.reply("Format: `/addcnl Name https://t.me/link`")

@app.on_message(filters.command("delcnl") & filters.user(ADMIN_ID))
async def cmd_delcnl(client, message):
    await get_db()
    chs = await channels_col.find({"type": "inline"}).to_list(100)
    btns = [[InlineKeyboardButton(f"❌ {c['name']}", callback_data=f"delch_{c['_id']}")] for c in chs]
    await message.reply("ডিলিট করতে ক্লিক করুন:", reply_markup=InlineKeyboardMarkup(btns) if btns else None)

@app.on_message(filters.command("vercnl") & filters.user(ADMIN_ID))
async def cmd_vercnl(client, message):
    await get_db()
    try:
        parts = message.text.split()
        await channels_col.insert_one({"type": "must_join", "chat_id": int(parts[1]), "link": parts[2]})
        await message.reply("✅ Must Join Channel Added!")
    except: await message.reply("Format: `/vercnl -100xxx https://t.me/xyz`")

@app.on_message(filters.command("delvrcnl") & filters.user(ADMIN_ID))
async def cmd_delvrcnl(client, message):
    await get_db()
    chs = await channels_col.find({"type": "must_join"}).to_list(100)
    btns = [[InlineKeyboardButton(f"❌ {c['chat_id']}", callback_data=f"delch_{c['_id']}")] for c in chs]
    await message.reply("Must Join চ্যানেল ডিলিট করতে ক্লিক করুন:", reply_markup=InlineKeyboardMarkup(btns) if btns else None)

@app.on_callback_query(filters.regex(r"^delch_") & filters.user(ADMIN_ID))
async def delch_cb(client, query):
    await get_db()
    await channels_col.delete_one({"_id": ObjectId(query.data.split("_")[1])})
    await query.message.edit_text("✅ চ্যানেল ডিলিট সম্পন্ন হয়েছে!")

@app.on_message(filters.command("addtex") & filters.user(ADMIN_ID))
async def cmd_addtex(client, message):
    await get_db()
    text = message.text.replace("/addtex", "").strip()
    if text:
        await config_col.update_one({"_id": "settings"}, {"$set": {"start_text": text}})
        await message.reply("✅ Start Text সেট করা হয়েছে!")
    else: await message.reply("Format: `/addtex Hello User...`")

@app.on_message(filters.command("deltex") & filters.user(ADMIN_ID))
async def cmd_deltex(client, message):
    await get_db()
    await config_col.update_one({"_id": "settings"}, {"$set": {"start_text": ""}})
    await message.reply("✅ Start Text ডিলিট করা হয়েছে!")

@app.on_message(filters.command("logo") & filters.user(ADMIN_ID))
async def cmd_logo(client, message):
    await get_db()
    if message.reply_to_message and message.reply_to_message.photo:
        file_id = message.reply_to_message.photo.file_id
        await config_col.update_one({"_id": "settings"}, {"$set": {"start_logo": file_id}})
        await message.reply("✅ Start Logo সেট করা হয়েছে!")
    else: await message.reply("❌ কোনো ছবি রিপ্লাই করে /logo দিন।")

@app.on_message(filters.command("autvid") & filters.user(ADMIN_ID))
async def cmd_autvid(client, message):
    await get_db()
    if message.reply_to_message:
        await config_col.update_one({"_id": "settings"}, {"$set": {"autovid_msg_id": message.reply_to_message.id}})
        await message.reply("✅ Auto Download Tutorial Message Set!")
    else: await message.reply("❌ রিপ্লাই করে কমান্ড দিন।")

@app.on_message(filters.command("autvidti") & filters.user(ADMIN_ID))
async def cmd_autvidti(client, message):
    await get_db()
    try:
        t = int(message.text.split()[1])
        await config_col.update_one({"_id": "settings"}, {"$set": {"autovid_time_min": t}})
        await message.reply(f"✅ Auto Vid Interval set to {t} minutes!")
    except: await message.reply("Format: `/autvidti 60`")

@app.on_message(filters.command("autpost") & filters.user(ADMIN_ID))
async def cmd_autpost(client, message):
    await get_db()
    try:
        h = int(message.text.split()[1])
        await config_col.update_one({"_id": "settings"}, {"$set": {"autopost_time_hr": h}})
        await message.reply(f"✅ Auto Post Interval set to {h} hours!")
    except: await message.reply("Format: `/autpost 2`")

# ==========================================
# 6. ADMIN: FILE UPLOAD & DELETE (UPDATED)
# ==========================================
def upload_to_telegraph(file_path):
    try:
        with open(file_path, 'rb') as f:
            res = requests.post('https://telegra.ph/upload', files={'file': ('file.jpg', f, 'image/jpeg')}).json()
        return "https://telegra.ph" + res[0]['src']
    except: return None

@app.on_message(filters.command("addfile") & filters.user(ADMIN_ID))
async def cmd_addfile(client, message):
    admin_steps[ADMIN_ID] = {"step": "name"}
    await message.reply("১. ফাইলের নাম/টাইটেল দিন:")

@app.on_message(filters.text & filters.user(ADMIN_ID) & filters.private & not_cmd_filter)
async def handle_admin_text(client, message):
    step = admin_steps.get(ADMIN_ID, {}).get("step")
    if step == "name":
        admin_steps[ADMIN_ID]["title"] = message.text
        admin_steps[ADMIN_ID]["step"] = "thumb"
        await message.reply("২. এবার ফাইলের ছবি বা লোগো দিন (Photo):")

@app.on_message(filters.photo & filters.user(ADMIN_ID) & filters.private)
async def handle_admin_photo(client, message):
    step = admin_steps.get(ADMIN_ID, {}).get("step")
    if step == "thumb":
        msg = await message.reply("⏳ ছবি প্রসেস হচ্ছে...")
        photo_path = await message.download()
        thumb_url = await asyncio.to_thread(upload_to_telegraph, photo_path)
        try: os.remove(photo_path)
        except: pass
        
        admin_steps[ADMIN_ID]["thumb_url"] = thumb_url or "https://placehold.co/600x400/1c1c24/ff007f?text=Media"
        
        btns = [
            [InlineKeyboardButton("💎 Premium Video", callback_data="filetype_prem")],
            [InlineKeyboardButton("👤 Regular Video", callback_data="filetype_reg")]
        ]
        await msg.edit_text("ভিডিওটি কি প্রিমিয়াম নাকি রেগুলার?", reply_markup=InlineKeyboardMarkup(btns))

@app.on_callback_query(filters.regex(r"^filetype_") & filters.user(ADMIN_ID))
async def filetype_cb(client, query):
    admin_steps[ADMIN_ID]["is_premium"] = (query.data == "filetype_prem")
    admin_steps[ADMIN_ID]["step"] = "file"
    await query.message.edit_text(f"✅ Type selected: {'Premium' if admin_steps[ADMIN_ID]['is_premium'] else 'Regular'}\n\n৩. এবার মূল ফাইল (Video/Document) দিন:")

@app.on_message((filters.video | filters.document | filters.audio) & filters.user(ADMIN_ID) & filters.private)
async def handle_admin_file(client, message):
    step = admin_steps.get(ADMIN_ID, {}).get("step")
    if step == "file":
        await get_db()
        msg = await message.reply("⏳ ফাইল সেভ করা হচ্ছে...")
        short_id = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
        file_id = message.video.file_id if message.video else (message.document.file_id if message.document else message.audio.file_id)
        
        await files_col.insert_one({
            "_id": short_id,
            "title": admin_steps[ADMIN_ID]["title"], 
            "category": "All", 
            "is_premium": admin_steps[ADMIN_ID].get("is_premium", False), 
            "file_id": file_id, 
            "thumb_url": admin_steps[ADMIN_ID].get("thumb_url", "https://placehold.co/600x400/1c1c24/ff007f?text=Media"),
            "views": 0
        })
        del admin_steps[ADMIN_ID]
        await msg.edit_text(f"✅ ফাইল সফলভাবে অ্যাড হয়েছে!\nID: `{short_id}`\nPremium: {admin_steps[ADMIN_ID].get('is_premium')}")

@app.on_message(filters.command("delfile") & filters.user(ADMIN_ID))
async def cmd_delfile(client, message):
    await get_db()
    try:
        f_id = message.text.split()[1]
        res = await files_col.delete_one({"_id": f_id})
        if res.deleted_count > 0: await message.reply("✅ ফাইল ডিলিট হয়েছে!")
        else: await message.reply("❌ ফাইল পাওয়া যায়নি!")
    except: await message.reply("Format: `/delfile FileID`")

@app.on_message(filters.command("delall") & filters.user(ADMIN_ID))
async def cmd_delall(client, message):
    await get_db()
    await files_col.delete_many({})
    await message.reply("✅ সকল ফাইল ডিলিট করা হয়েছে!")

# ==========================================
# 7. ADMIN: SETTINGS, COINS, PROTECT, PREMIUM
# ==========================================
@app.on_message(filters.command("refbonous") & filters.user(ADMIN_ID))
async def cmd_refbonous(client, message):
    await get_db()
    try:
        coin = int(message.text.split()[1])
        await config_col.update_one({"_id": "settings"}, {"$set": {"ref_coin": coin, "ref_on": True}})
        await message.reply(f"✅ পার রেফারে বোনাস সেট হয়েছে: {coin} Coins")
    except: await message.reply("Format: `/refbonous 10`")

@app.on_message(filters.command("refbonousoff") & filters.user(ADMIN_ID))
async def cmd_refbonousoff(client, message):
    await get_db()
    await config_col.update_one({"_id": "settings"}, {"$set": {"ref_on": False}})
    await message.reply("✅ রেফার বোনাস অফ করা হয়েছে! (রেফার হবে কিন্তু কয়েন পাবেনা)")

@app.on_message(filters.command("frotect") & filters.user(ADMIN_ID))
async def cmd_frotect(client, message):
    await get_db()
    state = message.text.split()[1].lower() if len(message.text.split()) > 1 else ""
    if state == "on": await config_col.update_one({"_id": "settings"}, {"$set": {"frotect": True}}); await message.reply("✅ Forward Protect ON")
    elif state == "off": await config_col.update_one({"_id": "settings"}, {"$set": {"frotect": False}}); await message.reply("✅ Forward Protect OFF")
    else: await message.reply("Format: `/frotect on/off`")

@app.on_message(filters.command("autodel") & filters.user(ADMIN_ID))
async def cmd_autodel(client, message):
    await get_db()
    try:
        t = int(message.text.split()[1])
        await config_col.update_one({"_id": "settings"}, {"$set": {"auto_del_time": t}})
        await message.reply(f"✅ অটো ডিলিট টাইম {t} সেকেন্ড সেট করা হয়েছে!")
    except: await message.reply("Format: `/autodel 60` (Seconds. 0 for OFF)")

@app.on_message(filters.command("autex") & filters.user(ADMIN_ID))
async def cmd_autex(client, message):
    await get_db()
    text = message.text.replace("/autex", "").strip()
    if text: await config_col.update_one({"_id": "settings"}, {"$set": {"autodel_text": text}}); await message.reply("✅ অটো ডিলিট টেক্সট সেট হয়েছে!")

@app.on_message(filters.command("usd") & filters.user(ADMIN_ID))
async def cmd_usd(client, message):
    await get_db()
    try:
        parts = message.text.split()
        details = f"{parts[1]} USD={parts[2]} Days"
        await pkgs_col.insert_one({"type": "usd", "details": details})
        await message.reply("✅ USD প্যাকেজ অ্যাড হয়েছে!")
    except: await message.reply("Format: `/usd 1 7`")

@app.on_message(filters.command("bdt") & filters.user(ADMIN_ID))
async def cmd_bdt(client, message):
    await get_db()
    try:
        parts = message.text.split()
        details = f"{parts[1]} BDT={parts[2]} Days"
        await pkgs_col.insert_one({"type": "bkash", "details": details})
        await message.reply("✅ BDT প্যাকেজ অ্যাড হয়েছে!")
    except: await message.reply("Format: `/bdt 100 7`")

@app.on_message(filters.command("addcred") & filters.user(ADMIN_ID))
async def cmd_addcred(client, message):
    await get_db()
    try:
        parts = message.text.split()
        details = f"{parts[1]} Coins={parts[3]} {parts[4]}"
        await pkgs_col.insert_one({"type": "coin", "coins": int(parts[1]), "amount": int(parts[3]), "unit": parts[4], "details": details})
        await message.reply("✅ Coin Package Added!")
    except: await message.reply("Format: `/addcred 10 coin 1 day`")

@app.on_message(filters.command("delcred") & filters.user(ADMIN_ID))
async def cmd_delcred(client, message):
    await get_db()
    pkgs = await pkgs_col.find({"type": "coin"}).to_list(100)
    btns = [[InlineKeyboardButton(f"❌ {c['details']}", callback_data=f"delpkg_{c['_id']}")] for c in pkgs]
    await message.reply("ডিলিট করতে ক্লিক করুন:", reply_markup=InlineKeyboardMarkup(btns) if btns else None)

@app.on_callback_query(filters.regex(r"^delpkg_") & filters.user(ADMIN_ID))
async def delpkg_cb(client, query):
    await get_db()
    await pkgs_col.delete_one({"_id": ObjectId(query.data.split("_")[1])})
    await query.message.edit_text("✅ Package Deleted!")

@app.on_message(filters.command("prparadd") & filters.user(ADMIN_ID))
async def cmd_prparadd(client, message):
    await get_db()
    try:
        wt = int(message.text.split()[1])
        await config_col.update_one({"_id": "settings"}, {"$set": {"prem_vid_wait": wt}})
        await message.reply(f"✅ Premium Video Ad Count/Wait Time set to {wt} for regular users.")
    except: await message.reply("Format: `/prparadd 10`")

@app.on_message(filters.command("addrdiem") & filters.user(ADMIN_ID))
async def cmd_addrdiem(client, message):
    await get_db()
    try:
        parts = message.text.split()
        u_id, amount, unit = int(parts[1]), int(parts[2]), parts[3].lower()
        secs = {"s": 1, "m": 60, "h": 3600, "d": 86400, "y": 31536000}.get(unit, 0)
        
        if secs > 0:
            expiry = datetime.now() + timedelta(seconds=amount * secs)
            await users_col.update_one({"_id": u_id}, {"$set": {"premium_until": expiry}})
            await message.reply(f"✅ User `{u_id}` কে {amount} {unit} এর জন্য প্রিমিয়াম করা হয়েছে!")
            try: await client.send_message(u_id, f"🎉 আপনার অ্যাকাউন্টে {amount} {unit} এর জন্য প্রিমিয়াম অ্যাক্সেস যুক্ত করা হয়েছে!")
            except: pass
    except: await message.reply("Format: `/addrdiem UserID 1 d`")

@app.on_message(filters.command("delpremium") & filters.user(ADMIN_ID))
async def cmd_delpremium(client, message):
    await get_db()
    try:
        u_id = int(message.text.split()[1])
        await users_col.update_one({"_id": u_id}, {"$set": {"premium_until": None}})
        await message.reply(f"✅ User `{u_id}` এর প্রিমিয়াম বাতিল করা হয়েছে!")
    except: await message.reply("Format: `/delpremium UserID`")

# ==========================================
# 8. ADMIN: BROADCAST & REDEEM COUPONS
# ==========================================
@app.on_message(filters.command("brodcast") & filters.user(ADMIN_ID))
async def cmd_brodcast(client, message):
    await get_db()
    if not message.reply_to_message: return await message.reply("❌ কোনো মেসেজ রিপ্লাই করে /brodcast লিখুন।")
    msg = await message.reply("⏳ ব্রডকাস্ট শুরু হয়েছে...")
    users = await users_col.find().to_list(None)
    success = 0
    for u in users:
        try: await message.reply_to_message.copy(u["_id"]); success += 1; await asyncio.sleep(0.05)
        except: pass
    await msg.edit_text(f"✅ ব্রডকাস্ট সম্পন্ন! {success} জনকে পাঠানো হয়েছে।")

@app.on_message(filters.command("cnlbdcst") & filters.user(ADMIN_ID))
async def cmd_cnlbdcst(client, message):
    if not message.reply_to_message: return await message.reply("❌ মেসেজ রিপ্লাই করুন।")
    try:
        chat_id = message.text.split()[1]
        await message.reply_to_message.copy(chat_id)
        await message.reply("✅ মেসেজ পাঠানো হয়েছে!")
    except: await message.reply("Format: `/cnlbdcst -100xxx`")

@app.on_message(filters.command("allred") & filters.user(ADMIN_ID))
async def cmd_allred(client, message):
    await get_db()
    try:
        parts = message.text.split()
        limit = int(parts[1])
        r_range = parts[2].split("-")
        min_c, max_c = int(r_range[0]), int(r_range[1])
        
        code = "RND" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        await coupons_col.insert_one({
            "code": code, "limit": limit, "used_by": [], 
            "is_random": True, "min": min_c, "max": max_c
        })
        await message.reply(f"✅ Random Coupon Created!\nCode: `{code}`\nLimit: {limit} users\nCoins: {min_c} to {max_c}")
    except: await message.reply("Format: `/allred 10 1-20`")

# ==========================================
# 9. WEB API (FLASK)
# ==========================================
@web.route('/api/get_ad/<int:user_id>/<file_id>')
def get_ad_api(user_id, file_id):
    config = sync_db["config"].find_one({"_id": "settings"}) or {}
    user = sync_db["users"].find_one({"_id": user_id})
    file_data = sync_db["files"].find_one({"_id": file_id})
    
    # Premium Users see NO ADS
    if user and user.get("premium_until") and user["premium_until"] > datetime.now():
        return jsonify({"show_ad": False})
        
    if config.get("ads_on", True):
        links = list(sync_db["ad_links"].find())
        if links:
            ad_link = random.choice(links)["link"]
            
            # If regular user watches premium video, apply different wait time
            if file_data and file_data.get("is_premium"): wait_time = config.get("prem_vid_wait", 10)
            else: wait_time = random.choice(config.get("direk_wait", [5]))
            
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
    
    coin_to_add = random.randint(coupon["min"], coupon["max"]) if coupon.get("is_random") else coupon.get("coins", 0)
    
    sync_db["coupons"].update_one({"code": code}, {"$push": {"used_by": uid}})
    sync_db["users"].update_one({"_id": uid}, {"$inc": {"balance": coin_to_add}})
    
    try: asyncio.run_coroutine_threadsafe(app.send_message(uid, f"🎉 কুপন রিডিম সফল! +{coin_to_add} Coins"), loop)
    except: pass
    
    return jsonify({"status": "success", "msg": f"✅ Successfully redeemed {coin_to_add} coins!"})

@web.route('/api/buy_with_coin', methods=['POST'])
def buy_with_coin():
    data = request.json
    uid, pkg_id = data['uid'], data['pkg_id']
    
    user = sync_db["users"].find_one({"_id": uid})
    pkg = sync_db["packages"].find_one({"_id": ObjectId(pkg_id)})
    
    if not user or not pkg: return jsonify({"status": "error", "msg": "Invalid Request"})
    if user.get("balance", 0) < pkg["coins"]: return jsonify({"status": "error", "msg": "❌ Insufficient Coins!"})
    
    secs = {"s": 1, "m": 60, "h": 3600, "d": 86400, "y": 31536000}.get(pkg.get("unit", "d").lower()[0], 86400)
    expiry = datetime.now() + timedelta(seconds=pkg["amount"] * secs)
    
    sync_db["users"].update_one({"_id": uid}, {"$inc": {"balance": -pkg["coins"]}, "$set": {"premium_until": expiry}})
    try: asyncio.run_coroutine_threadsafe(app.send_message(uid, f"🎉 আপনি {pkg['coins']} কয়েন দিয়ে প্রিমিয়াম কিনেছেন!"), loop)
    except: pass
    
    return jsonify({"status": "success", "msg": "✅ Premium Purchased Successfully!"})

@web.route('/api/user/<int:user_id>')
def get_user(user_id):
    user = sync_db["users"].find_one({"_id": user_id})
    is_prem = False
    if user and user.get("premium_until") and user["premium_until"] > datetime.now(): is_prem = True
    return jsonify({"balance": user.get("balance", 0) if user else 0, "is_premium": is_prem})

# ==========================================
# 10. HTML UI (EXACT GLOW TOP DESIGN)
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
        .prem-badge { background: #c72cff; padding: 2px 8px; border-radius: 10px; font-size: 10px; display:none; margin-left: 5px;}
        
        /* PAGE & NAV */
        .page { display: none; padding: 15px; }
        .page.active { display: block; animation: fadeIn 0.3s ease-in-out; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
        
        .bottom-nav { position: fixed; bottom: 0; width: 100%; background: rgba(14,20,30,0.95); display: flex; justify-content: space-around; padding: 10px 0; border-top: 1px solid rgba(255,255,255,0.05); backdrop-filter: blur(10px); z-index:100;}
        .nav-item { display: flex; flex-direction: column; align-items: center; font-size: 11px; color: #777; cursor: pointer; padding: 5px 15px; border-radius: 12px;}
        .nav-item.active { color: #fff; background: rgba(255,255,255,0.05); }
        .nav-item span { font-size: 22px; margin-bottom: 2px; filter: grayscale(100%); }
        .nav-item.active span { filter: grayscale(0%); }

        /* SEARCH & CATEGORIES */
        .search-box { width: 100%; padding: 14px 20px; border-radius: 12px; border: 1px solid rgba(255,255,255,0.1); background: rgba(0,0,0,0.4); color: white; outline: none; margin-bottom: 15px; font-size: 15px; font-family: 'Hind Siliguri', sans-serif;}
        
        /* VIDEO CARDS */
        .video-card { background: rgba(25,25,35,0.8); border-radius: 12px; margin-bottom: 20px; overflow: hidden; position: relative; border: 1px solid rgba(255,255,255,0.05);}
        .video-card img { width: 100%; height: 210px; object-fit: cover; }
        .tag-premium { position: absolute; top: 12px; left: 12px; background: #c72cff; padding: 4px 12px; border-radius: 15px; font-size: 11px; font-weight: bold; box-shadow: 0 2px 10px rgba(199,44,255,0.5);}
        .play-btn-overlay { position: absolute; top: 40%; left: 50%; transform: translate(-50%, -50%); width: 55px; height: 55px; background: rgba(0,123,255,0.8); border-radius: 50%; display: flex; justify-content: center; align-items: center; cursor: pointer; backdrop-filter: blur(5px); box-shadow: 0 0 15px rgba(0,123,255,0.4);}
        .play-btn-overlay::after { content: '▶'; color: white; font-size: 22px; margin-left: 4px;}
        .video-info { padding: 15px; }

        /* PAGINATION */
        .pagination { display: flex; justify-content: center; gap: 5px; flex-wrap: wrap; margin-top: 15px; }
        .page-btn { background: rgba(255,255,255,0.1); color: white; border: none; padding: 8px 12px; border-radius: 8px; cursor: pointer; font-weight:bold;}
        .page-btn.active { background: linear-gradient(90deg, #f02d73, #ff6b6b); }
        .page-btn:disabled { opacity: 0.5; cursor: not-allowed; }

        /* SETTINGS & PREMIUM */
        .cat-btn { background: rgba(255,255,255,0.05); padding: 8px 18px; border-radius: 25px; font-size: 13px; cursor: pointer; white-space: nowrap; border: 1px solid rgba(255,255,255,0.1);}
        .cat-btn.active { background: linear-gradient(90deg, #f02d73, #00d4ff); color: white; border:none; font-weight:bold;}
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
        <div class="logo">Glow Top <span id="prem-badge" class="prem-badge">VIP</span></div>
        <div class="coin-pill">🏛 <span id="hdr-balance">0</span></div>
    </div>

    <!-- AGE MODAL -->
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

    <!-- AD OVERLAY -->
    <div id="ad-overlay" class="modal-overlay">
        <div class="modal-box" style="background:transparent; border:none; box-shadow:none;">
            <h1 id="timer-count" style="font-size:90px; color:#f02d73; margin:0;">5</h1>
            <p style="font-size:16px; color:#aaa;">অ্যাড দেখার পর ফাইলটি ইনবক্সে পাবেন</p>
            <button id="get-file-btn" class="btn-main" style="background: linear-gradient(90deg, #00d4ff, #00ffcc); color:black; display:none;">Get File Now</button>
        </div>
    </div>

    <!-- HOME PAGE -->
    <div id="page-home" class="page active">
        <input type="text" id="search-bar" class="search-box" placeholder="🔍 Search videos..." onkeyup="handleSearch('home')">
        <div id="home-video-list"></div>
        <div class="pagination" id="home-pagination"></div>
    </div>

    <!-- PREMIUM VIDEOS PAGE -->
    <div id="page-premvids" class="page">
        <input type="text" id="search-bar-prem" class="search-box" placeholder="🔍 Search Premium Videos..." onkeyup="handleSearch('prem')">
        <div id="prem-video-list"></div>
        <div class="pagination" id="prem-pagination"></div>
    </div>

    <!-- VIP PLANS PAGE -->
    <div id="page-premium" class="page">
        <h2 style="margin-top:0;">VIP / Buy Coins</h2>
        <div style="display:flex; gap:10px; margin-bottom:20px;">
            <div class="cat-btn active" style="flex:1; text-align:center; border-radius:12px;" onclick="togglePkg('bks', this)">📱 BDT</div>
            <div class="cat-btn" style="flex:1; text-align:center; border-radius:12px;" onclick="togglePkg('usd', this)">⚡ USD</div>
            <div class="cat-btn" style="flex:1; text-align:center; border-radius:12px;" onclick="togglePkg('coin', this)">🪙 Coins</div>
        </div>
        
        <div id="pkg-bks">
            {% for pkg in pkgs if pkg.type == 'bkash' %}
            <div style="background: rgba(255,255,255,0.03); border: 1px solid #ffb703; padding: 20px; border-radius: 15px; margin-bottom: 15px; text-align: center; position: relative;">
                <div style="position: absolute; top: -12px; left: 50%; transform: translateX(-50%); background: #ffb703; color: black; font-size: 11px; font-weight: bold; padding: 4px 15px; border-radius: 12px;">⭐ BDT Premium</div>
                <div style="font-size:35px; margin-bottom:10px;">🏛</div>
                <h2 style="margin:0 0 5px 0; font-size:24px;">{{ pkg.details.split('=')[0] if '=' in pkg.details else pkg.details }}</h2>
                <p style="color:#aaa; font-size:14px; margin:0 0 15px 0;">{{ pkg.details.split('=')[1] if '=' in pkg.details else pkg.details }}</p>
                <button class="btn-main" style="margin:0; padding:12px;" onclick="reqBuy()">Buy Now</button>
            </div>
            {% endfor %}
        </div>
        
        <div id="pkg-usd" style="display:none;">
            {% for pkg in pkgs if pkg.type == 'usd' %}
            <div style="background: rgba(255,255,255,0.03); border: 1px solid #00d4ff; padding: 20px; border-radius: 15px; margin-bottom: 15px; text-align: center; position: relative;">
                <div style="position: absolute; top: -12px; left: 50%; transform: translateX(-50%); background: #00d4ff; color: black; font-size: 11px; font-weight: bold; padding: 4px 15px; border-radius: 12px;">⚡ USD Premium</div>
                <div style="font-size:35px; margin-bottom:10px;">💲</div>
                <h2 style="margin:0 0 5px 0; font-size:24px;">{{ pkg.details.split('=')[0] if '=' in pkg.details else pkg.details }}</h2>
                <p style="color:#aaa; font-size:14px; margin:0 0 15px 0;">{{ pkg.details.split('=')[1] if '=' in pkg.details else pkg.details }}</p>
                <button class="btn-main" style="margin:0; padding:12px; background:linear-gradient(90deg, #00d4ff, #00ffcc); color:black;" onclick="reqBuy()">Buy Now</button>
            </div>
            {% endfor %}
        </div>

        <div id="pkg-coin" style="display:none;">
            {% for pkg in pkgs if pkg.type == 'coin' %}
            <div style="background: rgba(255,255,255,0.03); border: 1px solid #c72cff; padding: 20px; border-radius: 15px; margin-bottom: 15px; text-align: center; position: relative;">
                <div style="position: absolute; top: -12px; left: 50%; transform: translateX(-50%); background: #c72cff; color: white; font-size: 11px; font-weight: bold; padding: 4px 15px; border-radius: 12px;">🪙 Buy with Coin</div>
                <div style="font-size:35px; margin-bottom:10px;">💎</div>
                <h2 style="margin:0 0 5px 0; font-size:24px;">{{ pkg.details.split('=')[0] if '=' in pkg.details else pkg.details }}</h2>
                <p style="color:#aaa; font-size:14px; margin:0 0 15px 0;">{{ pkg.details.split('=')[1] if '=' in pkg.details else pkg.details }} VIP (No Ads)</p>
                <button class="btn-main" style="margin:0; padding:12px; background:#c72cff;" onclick="buyWithCoin('{{ pkg._id }}', {{ pkg.coins }})">Exchange Coin</button>
            </div>
            {% endfor %}
        </div>
    </div>

    <!-- SETTINGS PAGE -->
    <div id="page-settings" class="page">
        <div class="balance-card">
            <p style="margin:0; color:#aaa; font-size:12px; letter-spacing:1px;">আপনার ব্যালেন্স (YOUR BALANCE)</p>
            <h1 style="color:#ffb703; margin:15px 0 10px 0; font-size:48px;">🏛 <span id="set-balance">0</span></h1>
            <p style="margin:0; color:#666; font-size:12px;">ID: <span id="set-id"></span></p>
        </div>
        <div class="set-item" onclick="switchNav('coupon')">
            <div class="set-icon" style="background: linear-gradient(135deg, #a18cd1, #fbc2eb);">🎟</div>
            <div><b style="display:block; font-size:16px;">কুপন কোড (Coupon)</b><span style="color:#aaa; font-size:12px;">কোড রিডিম করে ফ্রি কয়েন নিন</span></div>
        </div>
        <div class="set-item" onclick="switchNav('share')">
            <div class="set-icon" style="background: linear-gradient(135deg, #ffecd2, #fcb69f);">🎁</div>
            <div><b style="display:block; font-size:16px;">বন্ধুকে শেয়ার করুন (Share)</b><span style="color:#aaa; font-size:12px;">ইনভাইট করে ফ্রি কয়েন জিতুন</span></div>
        </div>
    </div>

    <!-- SUB PAGES -->
    <div id="page-coupon" class="page">
        <h2 style="margin-top:0;">🎟 কুপন কোড (Coupon Code)</h2>
        <div style="display:flex; gap:10px; margin-bottom:20px;">
            <input type="text" id="coupon-input" class="search-box" style="margin:0; border-radius:12px;" placeholder="Enter coupon">
            <button class="btn-main" style="width:auto; margin:0; padding:0 25px;" onclick="redeemCoupon()">Redeem</button>
        </div>
    </div>
    <div id="page-share" class="page">
        <h2 style="margin-top:0;">🎁 বন্ধুকে শেয়ার করুন (Share)</h2>
        <div class="share-banner">🥳 বন্ধু আপনার লিংক দিয়ে স্টার্ট করলেই <b style="color:#ffb703;">বোনাস</b> পাবেন!</div>
        <div class="ref-box">
            <input type="text" id="ref-link" readonly>
            <button onclick="copyRef()">📋 Copy</button>
        </div>
    </div>

    <!-- BOTTOM NAV -->
    <div class="bottom-nav">
        <div class="nav-item active" onclick="switchNav('home', this)"><span>🏠</span> Home</div>
        <div class="nav-item" onclick="switchNav('premvids', this)"><span>💎</span> VIP Vids</div>
        <div class="nav-item" onclick="switchNav('premium', this)"><span>🛒</span> Buy VIP</div>
        <div class="nav-item" onclick="switchNav('settings', this)"><span>⚙️</span> Setting</div>
    </div>

    <script>
        let tg = window.Telegram.WebApp;
        tg.expand();
        let botUsername = "{{ bot_username }}";
        let adminUsername = "{{ config.payment_admin }}";
        let userId = tg.initDataUnsafe.user ? tg.initDataUnsafe.user.id : 123456789; 
        
        document.getElementById('set-id').innerText = userId;
        document.getElementById('ref-link').value = `https://t.me/${botUsername}?start=${userId}`;
        
        let userBalance = 0;
        async function loadUser() {
            let res = await fetch('/api/user/' + userId);
            let data = await res.json();
            userBalance = data.balance;
            document.getElementById('hdr-balance').innerText = userBalance;
            document.getElementById('set-balance').innerText = userBalance;
            if(data.is_premium) document.getElementById('prem-badge').style.display = 'inline-block';
        }
        loadUser();

        if(!localStorage.getItem('ageVerified')) { document.getElementById('age-modal').style.display = 'flex'; }
        function confirmAge() { localStorage.setItem('ageVerified', 'true'); document.getElementById('age-modal').style.display = 'none'; }

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
            document.getElementById('pkg-coin').style.display = type === 'coin' ? 'block' : 'none';
        }

        // --- PAGINATION LOGIC ---
        let allFiles = {{ files_json | safe }};
        
        let state = { home: { p: 1, lim: 20, q: "" }, prem: { p: 1, lim: 20, q: "" } };

        function renderPagination(tab, total) {
            let s = state[tab];
            let maxP = Math.ceil(total / s.lim) || 1;
            if(s.p > maxP) s.p = maxP;
            
            let html = `<button class="page-btn" onclick="chgP('${tab}', -1)" ${s.p===1?'disabled':''}>Prev</button>`;
            let start = Math.max(1, s.p - 1);
            let end = Math.min(maxP, s.p + 1);
            
            for(let i=start; i<=end; i++){
                html += `<button class="page-btn ${s.p===i?'active':''}" onclick="setP('${tab}', ${i})">${i}</button>`;
            }
            html += `<button class="page-btn" onclick="chgP('${tab}', 1)" ${s.p>=maxP?'disabled':''}>Next</button>`;
            html += `<button class="page-btn" style="background:#444;" onclick="setLim('${tab}', 100)">See All</button>`;
            
            document.getElementById(`${tab}-pagination`).innerHTML = html;
        }

        function renderList(tab) {
            let s = state[tab];
            let filtered = allFiles.filter(f => {
                if(tab === 'prem' && !f.is_premium) return false;
                if(tab === 'home' && f.is_premium) return false;
                return f.title.toLowerCase().includes(s.q);
            });
            
            let start = (s.p - 1) * s.lim;
            let pageFiles = filtered.slice(start, start + s.lim);
            
            let html = "";
            if(pageFiles.length === 0) html = "<p style='text-align:center; color:#666;'>No videos found!</p>";
            pageFiles.forEach(f => {
                html += `<div class="video-card">
                    <img src="${f.thumb_url || 'https://placehold.co/600x400/1c1c24/ff007f?text=Media'}">
                    ${f.is_premium ? '<div class="tag-premium">💎 VIP</div>' : ''}
                    <div class="play-btn-overlay" onclick="playVideo('${f._id}')"></div>
                    <div class="video-info">
                        <b style="font-size:15px; display:block; margin-bottom:5px;">${f.title} <small style="color:#00d4ff;">[ID: ${f._id}]</small></b>
                        <small style="color:#aaa;">👁 ${f.views} views</small>
                    </div>
                </div>`;
            });
            document.getElementById(`${tab}-video-list`).innerHTML = html;
            renderPagination(tab, filtered.length);
        }

        function handleSearch(tab) { state[tab].q = document.getElementById(`search-bar${tab==='prem'?'-prem':''}`).value.toLowerCase(); state[tab].p = 1; renderList(tab); }
        function chgP(tab, dir) { state[tab].p += dir; renderList(tab); }
        function setP(tab, num) { state[tab].p = num; renderList(tab); }
        function setLim(tab, lim) { state[tab].lim = lim; state[tab].p = 1; renderList(tab); }

        renderList('home'); renderList('prem');

        // --- ADS & PLAY ---
        let currentDeepLink = "";
        async function playVideo(fileId) {
            currentDeepLink = `https://t.me/${botUsername}?start=file_${fileId}`;
            let res = await fetch(`/api/get_ad/${userId}/${fileId}`);
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
            if(!code) return tg.showAlert("কোড লিখুন!");
            let res = await fetch('/api/redeem', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ uid: userId, code: code }) });
            let data = await res.json();
            tg.showAlert(data.msg);
            if(data.status === 'success') { loadUser(); document.getElementById('coupon-input').value = ""; }
        }
        
        async function buyWithCoin(pkgId, cost) {
            if(userBalance < cost) return tg.showAlert("❌ আপনার পর্যাপ্ত কয়েন নেই!");
            if(confirm(`আপনি কি ${cost} কয়েন দিয়ে প্রিমিয়াম নিতে চান?`)) {
                let res = await fetch('/api/buy_with_coin', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ uid: userId, pkg_id: pkgId }) });
                let data = await res.json();
                tg.showAlert(data.msg);
                loadUser();
            }
        }

        function copyRef() {
            let copyText = document.getElementById("ref-link");
            copyText.select(); navigator.clipboard.writeText(copyText.value);
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
    config = sync_db["config"].find_one({"_id": "settings"}) or {}
    return render_template_string(HTML_TEMPLATE, files_json=json.dumps(files), cats=cats, pkgs=pkgs, bot_username=BOT_USERNAME, config=config)

# ==========================================
# 11. RUN SERVERS
# ==========================================
def run_flask(): 
    port = int(os.environ.get("PORT", 8080))
    web.run(host="0.0.0.0", port=port, debug=False)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    while True:
        try:
            print("🚀 Starting Bot, Tasks & UI (Safe Mode)...")
            loop.create_task(background_tasks())
            app.run()
            break  
        except FloodWait as e:
            print(f"⚠️ Rate Limit: Waiting {e.value} seconds...")
            time.sleep(e.value) 
        except Exception as e:
            print(f"❌ Core Error: {e}")
            break
