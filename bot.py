import os, sys, asyncio, threading, random, string, time, requests, json 
from datetime import datetime, timedelta

# ==========================================
# 🛑 PYROGRAM PYTHON 3.14 FIX 🛑
# Pyrogram ইমপোর্ট করার আগে Event Loop সেট করতে হবে
# ==========================================
loop = asyncio.new_event_loop() 
asyncio.set_event_loop(loop)

from pyrogram import Client, filters, idle 
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

try:
    requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook?drop_pending_updates=True")
except: pass

# ==========================================
# 2. DATABASE & SYSTEM INIT
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
        conf = { "_id": "settings", "ref_coin": 10, "ref_on": True, "auto_del_time": 0, "autodel_text": "⏳ ফাইলটি নির্দিষ্ট সময় পর অটো ডিলিট হয়ে যাবে। / File will be auto-deleted after some time.", "frotect": False, "ads_on": True, "direk_wait": [5], "prem_vid_wait": 10, "prstep": 1, "regstep": 1, "start_logo": None, "start_text": "", "payment_admin": DEFAULT_ADMIN_USERNAME, "autovid_msg_id": None, "autovid_time_min": 0, "autopost_time_hr": 0, "autopost_idx": 0, "site_name": "Glow Top" } 
        await config_col.insert_one(conf) 
    return conf

async def delete_msg_later(client, chat_id, msg_id, delay): 
    await asyncio.sleep(delay) 
    try: await client.delete_messages(chat_id, msg_id) 
    except: pass

# --- TIME FORMATTER (বছর, মাস, দিন...) ---
def get_expiry_str(expiry_date): 
    if not expiry_date: return None 
    now = datetime.now() 
    if expiry_date <= now: return None 
    sec = int((expiry_date - now).total_seconds())

    y, sec = divmod(sec, 31536000)
    mo, sec = divmod(sec, 2592000)
    w, sec = divmod(sec, 604800)
    d, sec = divmod(sec, 86400)
    h, sec = divmod(sec, 3600)
    m, sec = divmod(sec, 60)

    res = []
    if y: res.append(f"{y} বছর/Years")
    if mo: res.append(f"{mo} মাস/Months")
    if w: res.append(f"{w} সপ্তাহ/Weeks")
    if d: res.append(f"{d} দিন/Days")
    if h: res.append(f"{h} ঘণ্টা/Hours")
    if m: res.append(f"{m} মিনিট/Mins")
    if sec or not res: res.append(f"{sec} সেকেন্ড/Secs")
    return " ".join(res)

# --- Keep Alive ---
def keep_alive(): 
    while True: 
        try: 
            time.sleep(300) 
            requests.get(WEB_URL) 
        except: pass 
threading.Thread(target=keep_alive, daemon=True).start()

# ==========================================
# 3. BACKGROUND TASKS
# ==========================================
async def background_tasks(): 
    last_autovid, last_autopost = time.time(), time.time() 
    while True: 
        await asyncio.sleep(60) 
        now = time.time() 
        try: 
            config = await get_config() 
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

            ap_hr = config.get("autopost_time_hr", 0)
            if ap_hr > 0 and (now - last_autopost) >= (ap_hr * 3600):
                idx = config.get("autopost_idx", 0)
                files = await files_col.find().sort("_id", 1).to_list(None)
                if files:
                    if idx >= len(files): idx = 0
                    f = files[idx]
                    users = await users_col.find().to_list(None)
                    btn = InlineKeyboardMarkup([[InlineKeyboardButton("🎬 Watch Now / দেখুন", web_app=WebAppInfo(url=f"{WEB_URL}/"))]])
                    for u in users:
                        try:
                            await app.send_photo(u["_id"], photo=f.get("thumb_url"), caption=f"🔥 **New Video / নতুন ভিডিও!**\n\nTitle: {f['title']}\n\n👇 Click below to watch / নিচে ক্লিক করে দেখুন!", reply_markup=btn)
                            await asyncio.sleep(0.05)
                        except: pass
                    await config_col.update_one({"_id": "settings"}, {"$set": {"autopost_idx": idx + 1}})
                last_autopost = time.time()
        except Exception as e: print("BG Task Error:", e)

# ==========================================
# 4. BOT COMMANDS
# ==========================================
@app.on_message(filters.command("myid")) 
async def cmd_myid(c, m): 
    await m.reply(f"✅ বট একদম ঠিকভাবে কাজ করছে! / Bot is working perfectly!\n🆔 আপনার আইডি / Your ID: {m.from_user.id}")

@app.on_message(filters.command("stats") & filters.user(ADMIN_ID)) 
async def cmd_stats(c, m): 
    await get_db() 
    t_u = await users_col.count_documents({}) 
    t_f = await files_col.count_documents({}) 
    p_u = await users_col.count_documents({"premium_until": {"$gt": datetime.now()}}) 
    await m.reply(f"📊 Statistics:\n\n👥 Users: {t_u}\n🎬 Files: {t_f}\n💎 Premium: {p_u}\n👤 Regular: {t_u - p_u}")

@app.on_message(filters.command("name") & filters.user(ADMIN_ID))
async def cmd_name(c, m):
    new_name = m.text.replace("/name", "").strip()
    if not new_name: return await m.reply("❌ সাইটের নাম দিন / Please provide a site name. Example: /name MySite")
    await get_db()
    await config_col.update_one({"_id": "settings"}, {"$set": {"site_name": new_name}})
    await m.reply(f"✅ সাইটের নাম পরিবর্তন করা হয়েছে / Site name changed to: {new_name}")

@app.on_message(filters.command("start") & filters.private) 
async def start_cmd(client, message): 
    await get_db() 
    uid = message.from_user.id 
    args = message.text.split() 
    config = await get_config()

    user = await users_col.find_one({"_id": uid})
    if not user:
        await users_col.insert_one({"_id": uid, "name": message.from_user.first_name, "balance": 0, "pending_file": None, "premium_until": None})
        if len(args) > 1 and args[1].isdigit() and int(args[1]) != uid:
            ref_by = int(args[1])
            if config.get("ref_on", True):
                await users_col.update_one({"_id": ref_by}, {"$inc": {"balance": config.get("ref_coin", 10)}})
                try: await client.send_message(ref_by, f"🎉 আপনার রেফারে একজন জয়েন করেছে! / Someone joined using your refer link! +{config.get('ref_coin', 10)} Coins")
                except: pass
        user = await users_col.find_one({"_id": uid})

    if len(args) > 1 and args[1].startswith("file_"):
        pf = args[1].replace("file_", "")
        await users_col.update_one({"_id": uid}, {"$set": {"pending_file": pf}})
        user["pending_file"] = pf

    channels = await channels_col.find({"type": "must_join"}).to_list(100)
    not_joined = []
    for ch in channels:
        try: await client.get_chat_member(ch["chat_id"], uid)
        except UserNotParticipant: not_joined.append(ch["link"])
        except: pass

    if not_joined:
        btns = [[InlineKeyboardButton("📢 Join Channel / চ্যানেল জয়েন করুন", url=link)] for link in not_joined]
        btns.append([InlineKeyboardButton("✅ Joined / জয়েন করেছি", callback_data="check_join")])
        return await message.reply("❌ আপনাকে আগে আমাদের চ্যানেলগুলোতে জয়েন করতে হবে / You must join our channels first:", reply_markup=InlineKeyboardMarkup(btns))

    if user.get("pending_file"):
        f_id = user["pending_file"]
        await users_col.update_one({"_id": uid}, {"$set": {"pending_file": None}})
        file_data = await files_col.find_one({"_id": f_id})
        
        if file_data:
            await files_col.update_one({"_id": f_id}, {"$inc": {"views": 1}})
            msg = await message.reply("⏳ আপনার ফাইল পাঠানো হচ্ছে... / Sending your file...")
            try:
                sent_msg = await client.send_cached_media(chat_id=uid, file_id=file_data["file_id"], caption=f"🎬 **{file_data['title']}**", protect_content=config.get("frotect", False))
                await msg.delete()
                
                del_time = config.get("auto_del_time", 0)
                if del_time > 0:
                    warn = await client.send_message(uid, f"⚠️ {config.get('autodel_text')}")
                    asyncio.create_task(delete_msg_later(client, uid, sent_msg.id, del_time))
                    asyncio.create_task(delete_msg_later(client, uid, warn.id, del_time))
            except Exception as e: await msg.edit_text(f"❌ ফাইল পাঠাতে সমস্যা হয়েছে! / Failed to send file! {e}")
        else: await message.reply("❌ ফাইলটি পাওয়া যায়নি! / File not found!")
        return

    full = f"{message.from_user.first_name} {message.from_user.last_name or ''}".strip()
    uname = f"@{message.from_user.username}" if message.from_user.username else "N/A"

    expiry_str = get_expiry_str(user.get("premium_until"))
    mem_status = f"💎 **Premium** (মেয়াদ / Expiry: {expiry_str})" if expiry_str else "👤 **Regular Member**"

    txt = f"👋 **স্বাগতম / Welcome to {config.get('site_name', 'Glow Top')}!**\n\n👤 **Name:** {full}\n🆔 **User ID:** `{uid}`\n🌐 **Username:** {uname}\n💰 **Balance:** {user.get('balance', 0)} Coins\n🔰 **Membership:** {mem_status}\n"
    if config.get("start_text"): txt += f"\n📝 {config.get('start_text')}\n"
    txt += "\n👇 নিচের বাটন থেকে অ্যাপ ওপেন করুন / Click below to open app:"

    btns = [[InlineKeyboardButton(ch["name"], url=ch["link"])] for ch in await channels_col.find({"type": "inline"}).to_list(100)]
    btns.insert(0, [InlineKeyboardButton(f"🔥 Open / ওপেন {config.get('site_name', 'Glow Top')}", web_app=WebAppInfo(url=f"{WEB_URL}/"))])

    if config.get("start_logo"):
        try: await client.send_photo(uid, photo=config.get("start_logo"), caption=txt, reply_markup=InlineKeyboardMarkup(btns))
        except: await message.reply(txt, reply_markup=InlineKeyboardMarkup(btns))
    else: await message.reply(txt, reply_markup=InlineKeyboardMarkup(btns))

@app.on_callback_query(filters.regex("check_join")) 
async def check_join_cb(c, q): 
    await get_db() 
    for ch in await channels_col.find({"type": "must_join"}).to_list(100): 
        try: await c.get_chat_member(ch["chat_id"], q.from_user.id) 
        except: return await q.answer("❌ আপনি এখনো সব চ্যানেলে জয়েন করেননি! / You haven't joined all channels yet!", show_alert=True) 
    await q.message.delete() 
    class FakeMsg: 
        def __init__(self, u): self.from_user = u; self.text = "/start" 
        async def reply(self, *a, **k): return await c.send_message(q.from_user.id, *a, **k) 
    await start_cmd(c, FakeMsg(q.from_user))

# ==========================================
# 5. ADMIN FILE UPLOAD (FIXED IMAGE UPLOAD)
# ==========================================
def upload_to_telegraph(file_path): 
    try: 
        # Force .jpg extension so Telegraph accepts any format (png/webp/heic) sent from Telegram
        new_path = file_path + ".jpg"
        os.rename(file_path, new_path)
        with open(new_path, 'rb') as f: 
            res = requests.post('https://telegra.ph/upload', files={'file': ('f.jpg', f, 'image/jpeg')}).json() 
        return "https://telegra.ph" + res[0]['src'] 
    except Exception as e: 
        print(e); return None

@app.on_message(filters.command("addfile") & filters.user(ADMIN_ID)) 
async def cmd_addfile(c, m): 
    admin_steps[m.from_user.id] = {"step": "name"} 
    await m.reply("১. ফাইলের নাম/টাইটেল দিন: \n(1. Enter File Name/Title:)")

def is_in_step(step): 
    return filters.create(lambda _, __, m: admin_steps.get(m.from_user.id, {}).get("step") == step)

@app.on_message(filters.text & filters.user(ADMIN_ID) & filters.private & is_in_step("name") & ~filters.command(["start", "myid"])) 
async def handle_admin_name(c, m): 
    admin_steps[m.from_user.id]["title"] = m.text 
    admin_steps[m.from_user.id]["step"] = "thumb" 
    await m.reply("২. এবার ফাইলের ছবি বা লোগো দিন (Photo বা Document আকারে সেন্ড করুন):\n(2. Now send File Thumbnail/Photo/Document:)")

@app.on_message((filters.photo | filters.document) & filters.user(ADMIN_ID) & filters.private & is_in_step("thumb")) 
async def handle_admin_photo(c, m): 
    msg = await m.reply("⏳ ছবি প্রসেস হচ্ছে... / Processing image...") 
    path = await m.download() 
    url = await asyncio.to_thread(upload_to_telegraph, path) 
    try: os.remove(path) 
    except: pass

    admin_steps[m.from_user.id]["thumb_url"] = url or "https://placehold.co/600x400/1c1c24/ff007f?text=Media"

    btns = [[InlineKeyboardButton("💎 Premium Video", callback_data="ftype_prem")], [InlineKeyboardButton("👤 Regular Video", callback_data="ftype_reg")]]
    await msg.edit_text("ভিডিওটি কি প্রিমিয়াম নাকি রেগুলার? / Is it Premium or Regular?", reply_markup=InlineKeyboardMarkup(btns))

@app.on_callback_query(filters.regex(r"^ftype_") & filters.user(ADMIN_ID)) 
async def filetype_cb(c, q): 
    admin_steps[q.from_user.id]["is_premium"] = (q.data == "ftype_prem") 
    admin_steps[q.from_user.id]["step"] = "file" 
    await q.message.edit_text("✅ ৩. এবার মূল ফাইল (Video/Document) দিন:\n(3. Now send the main Video/File:)")

@app.on_message((filters.video | filters.document | filters.audio) & filters.user(ADMIN_ID) & filters.private & is_in_step("file")) 
async def handle_admin_file(c, m): 
    await get_db() 
    msg = await m.reply("⏳ ফাইল সেভ করা হচ্ছে... / Saving file...") 
    short_id = ''.join(random.choices(string.ascii_letters + string.digits, k=8)) 
    f_id = m.video.file_id if m.video else (m.document.file_id if m.document else m.audio.file_id) 
    await files_col.insert_one({ "_id": short_id, "title": admin_steps[m.from_user.id]["title"], "category": "All", "is_premium": admin_steps[m.from_user.id].get("is_premium", False), "file_id": f_id, "thumb_url": admin_steps[m.from_user.id].get("thumb_url"), "views": 0 }) 
    del admin_steps[m.from_user.id] 
    await msg.edit_text(f"✅ ফাইল সফলভাবে অ্যাড হয়েছে! / File Added Successfully!\nID: {short_id}")

@app.on_message(filters.command("delfile") & filters.user(ADMIN_ID)) 
async def cmd_delfile(c, m): 
    await get_db(); res = await files_col.delete_one({"_id": m.text.split()[1]}) 
    if res.deleted_count > 0: await m.reply("✅ ফাইল ডিলিট হয়েছে! / File Deleted!") 
    else: await m.reply("❌ ফাইল পাওয়া যায়নি! / File Not Found!")

@app.on_message(filters.command("delall") & filters.user(ADMIN_ID)) 
async def cmd_delall(c, m): 
    await get_db(); await files_col.delete_many({}); await m.reply("✅ সকল ফাইল ডিলিট করা হয়েছে! / All files deleted!")

# ==========================================
# 6. OTHER ADMIN COMMANDS
# ==========================================
@app.on_message(filters.command("prstep") & filters.user(ADMIN_ID)) 
async def cmd_prstep(c, m): 
    await get_db(); await config_col.update_one({"_id": "settings"}, {"$set": {"prstep": int(m.text.split()[1])}}); await m.reply("✅ Premium Ad Steps Set!")

@app.on_message(filters.command("regstep") & filters.user(ADMIN_ID)) 
async def cmd_regstep(c, m): 
    await get_db(); await config_col.update_one({"_id": "settings"}, {"$set": {"regstep": int(m.text.split()[1])}}); await m.reply("✅ Regular Ad Steps Set!")

@app.on_message(filters.command("addadmin") & filters.user(ADMIN_ID)) 
async def cmd_addadmin(c, m): 
    await get_db(); await config_col.update_one({"_id": "settings"}, {"$set": {"payment_admin": m.text.split()[1].replace("@", "")}}); await m.reply("✅ Payment Admin Set!")

@app.on_message(filters.command("addlink") & filters.user(ADMIN_ID)) 
async def cmd_addlink(c, m): 
    await get_db(); await links_col.insert_one({"link": m.text.split()[1]}); await m.reply("✅ Ad Link Added!")

@app.on_message(filters.command("delink") & filters.user(ADMIN_ID)) 
async def cmd_dellink(c, m): 
    await get_db() 
    btns = [[InlineKeyboardButton(f"❌ {l['link'][:20]}...", callback_data=f"dellink_{l['_id']}")] for l in await links_col.find().to_list(100)] 
    await m.reply("ডিলিট করতে ক্লিক করুন / Click to delete:", reply_markup=InlineKeyboardMarkup(btns) if btns else None)

@app.on_callback_query(filters.regex(r"^dellink_") & filters.user(ADMIN_ID))
async def dellink_cb(c, q): 
    await get_db(); await links_col.delete_one({"_id": ObjectId(q.data.split("_")[1])}); await q.message.edit_text("✅ Ad Link Deleted!")

@app.on_message(filters.command("addcnl") & filters.user(ADMIN_ID)) 
async def cmd_addcnl(c, m): 
    await get_db(); p = m.text.split(maxsplit=2); await channels_col.insert_one({"type": "inline", "name": p[1], "link": p[2]}); await m.reply("✅ Inline Channel added!")

@app.on_message(filters.command("delcnl") & filters.user(ADMIN_ID)) 
async def cmd_delcnl(c, m): 
    await get_db() 
    btns = [[InlineKeyboardButton(f"❌ {ch['name']}", callback_data=f"delch_{ch['_id']}")] for ch in await channels_col.find({"type": "inline"}).to_list(100)] 
    await m.reply("ডিলিট করতে ক্লিক করুন / Click to delete:", reply_markup=InlineKeyboardMarkup(btns) if btns else None)

@app.on_message(filters.command("vercnl") & filters.user(ADMIN_ID)) 
async def cmd_vercnl(c, m): 
    await get_db(); p = m.text.split(); await channels_col.insert_one({"type": "must_join", "chat_id": int(p[1]), "link": p[2]}); await m.reply("✅ Must Join Channel Added!")

@app.on_message(filters.command("delvrcnl") & filters.user(ADMIN_ID)) 
async def cmd_delvrcnl(c, m): 
    await get_db() 
    btns = [[InlineKeyboardButton(f"❌ {ch['chat_id']}", callback_data=f"delch_{ch['_id']}")] for ch in await channels_col.find({"type": "must_join"}).to_list(100)] 
    await m.reply("ডিলিট করতে ক্লিক করুন / Click to delete:", reply_markup=InlineKeyboardMarkup(btns) if btns else None)

@app.on_callback_query(filters.regex(r"^delch_") & filters.user(ADMIN_ID)) 
async def delch_cb(c, q): 
    await get_db(); await channels_col.delete_one({"_id": ObjectId(q.data.split("_")[1])}); await q.message.edit_text("✅ Channel Deleted!")

@app.on_message(filters.command("addtex") & filters.user(ADMIN_ID)) 
async def cmd_addtex(c, m): 
    await get_db(); await config_col.update_one({"_id": "settings"}, {"$set": {"start_text": m.text.replace("/addtex", "").strip()}}); await m.reply("✅ Start Text Set!")

@app.on_message(filters.command("deltex") & filters.user(ADMIN_ID)) 
async def cmd_deltex(c, m): 
    await get_db(); await config_col.update_one({"_id": "settings"}, {"$set": {"start_text": ""}}); await m.reply("✅ Start Text Deleted!")

@app.on_message(filters.command("logo") & filters.user(ADMIN_ID)) 
async def cmd_logo(c, m): 
    await get_db() 
    if m.reply_to_message and m.reply_to_message.photo: 
        await config_col.update_one({"_id": "settings"}, {"$set": {"start_logo": m.reply_to_message.photo.file_id}}); await m.reply("✅ Start Logo Set!")

@app.on_message(filters.command("autvid") & filters.user(ADMIN_ID)) 
async def cmd_autvid(c, m): 
    await get_db(); 
    if m.reply_to_message: 
        await config_col.update_one({"_id": "settings"}, {"$set": {"autovid_msg_id": m.reply_to_message.id}}); await m.reply("✅ Auto Vid Msg Set!")

@app.on_message(filters.command("autvidti") & filters.user(ADMIN_ID)) 
async def cmd_autvidti(c, m): 
    await get_db(); await config_col.update_one({"_id": "settings"}, {"$set": {"autovid_time_min": int(m.text.split()[1])}}); await m.reply("✅ Auto Vid Interval Set!")

@app.on_message(filters.command("autpost") & filters.user(ADMIN_ID)) 
async def cmd_autpost(c, m): 
    await get_db(); await config_col.update_one({"_id": "settings"}, {"$set": {"autopost_time_hr": int(m.text.split()[1])}}); await m.reply("✅ Auto Post Interval Set!")

@app.on_message(filters.command("refbonous") & filters.user(ADMIN_ID)) 
async def cmd_refbonous(c, m): 
    await get_db(); await config_col.update_one({"_id": "settings"}, {"$set": {"ref_coin": int(m.text.split()[1]), "ref_on": True}}); await m.reply("✅ Ref Bonus Set!")

@app.on_message(filters.command("refbonousoff") & filters.user(ADMIN_ID)) 
async def cmd_refbonousoff(c, m): 
    await get_db(); await config_col.update_one({"_id": "settings"}, {"$set": {"ref_on": False}}); await m.reply("✅ Ref Bonus OFF!")

@app.on_message(filters.command("frotect") & filters.user(ADMIN_ID)) 
async def cmd_frotect(c, m): 
    await get_db(); await config_col.update_one({"_id": "settings"}, {"$set": {"frotect": m.text.split()[1].lower() == "on"}}); await m.reply("✅ Protect Config Set!")

@app.on_message(filters.command("autodel") & filters.user(ADMIN_ID)) 
async def cmd_autodel(c, m): 
    await get_db(); await config_col.update_one({"_id": "settings"}, {"$set": {"auto_del_time": int(m.text.split()[1])}}); await m.reply("✅ Auto Delete Set!")

@app.on_message(filters.command("autex") & filters.user(ADMIN_ID)) 
async def cmd_autex(c, m): 
    await get_db(); await config_col.update_one({"_id": "settings"}, {"$set": {"autodel_text": m.text.replace("/autex", "").strip()}}); await m.reply("✅ Auto Delete Text Set!")

@app.on_message(filters.command("usd") & filters.user(ADMIN_ID)) 
async def cmd_usd(c, m): 
    await get_db(); p=m.text.split(); await pkgs_col.insert_one({"type": "usd", "details": f"{p[1]} USD={p[2]} Days"}); await m.reply("✅ USD Package Added!")

@app.on_message(filters.command("bdt") & filters.user(ADMIN_ID)) 
async def cmd_bdt(c, m): 
    await get_db(); p=m.text.split(); await pkgs_col.insert_one({"type": "bkash", "details": f"{p[1]} BDT={p[2]} Days"}); await m.reply("✅ BDT Package Added!")

@app.on_message(filters.command("addcred") & filters.user(ADMIN_ID)) 
async def cmd_addcred(c, m): 
    await get_db(); p=m.text.split(); await pkgs_col.insert_one({"type": "coin", "coins": int(p[1]), "amount": int(p[3]), "unit": p[4], "details": f"{p[1]} Coins={p[3]} {p[4]}"}); await m.reply("✅ Coin Package Added!")

@app.on_message(filters.command("delcred") & filters.user(ADMIN_ID)) 
async def cmd_delcred(c, m): 
    await get_db() 
    btns = [[InlineKeyboardButton(f"❌ {p['details']}", callback_data=f"delpkg_{p['_id']}")] for p in await pkgs_col.find({"type": "coin"}).to_list(100)] 
    await m.reply("ডিলিট করতে ক্লিক করুন / Click to delete:", reply_markup=InlineKeyboardMarkup(btns) if btns else None)

@app.on_callback_query(filters.regex(r"^delpkg_") & filters.user(ADMIN_ID))
async def delpkg_cb(c, q): 
    await get_db(); await pkgs_col.delete_one({"_id": ObjectId(q.data.split("_")[1])}); await q.message.edit_text("✅ Package Deleted!")

@app.on_message(filters.command("prparadd") & filters.user(ADMIN_ID)) 
async def cmd_prparadd(c, m): 
    await get_db(); await config_col.update_one({"_id": "settings"}, {"$set": {"prem_vid_wait": int(m.text.split()[1])}}); await m.reply("✅ Premium Vid Wait Time Set!")

@app.on_message(filters.command("addrdiem") & filters.user(ADMIN_ID)) 
async def cmd_addrdiem(c, m): 
    await get_db() 
    p = m.text.split(); u_id, amt, unit = int(p[1]), int(p[2]), p[3].lower() 
    secs = {"s": 1, "m": 60, "h": 3600, "d": 86400, "y": 31536000}.get(unit, 0) 
    await users_col.update_one({"_id": u_id}, {"$set": {"premium_until": datetime.now() + timedelta(seconds=amt * secs)}}) 
    await m.reply(f"✅ User {u_id} made Premium!"); await c.send_message(u_id, f"🎉 You received {amt} {unit} Premium!")

@app.on_message(filters.command("delpremium") & filters.user(ADMIN_ID)) 
async def cmd_delpremium(c, m): 
    await get_db(); await users_col.update_one({"_id": int(m.text.split()[1])}, {"$set": {"premium_until": None}}); await m.reply("✅ Premium Removed!")

@app.on_message(filters.command("brodcast") & filters.user(ADMIN_ID)) 
async def cmd_brodcast(c, m): 
    await get_db() 
    if not m.reply_to_message: return await m.reply("❌ Reply to a message.") 
    msg = await m.reply("⏳ Broadcasting..."); success = 0 
    for u in await users_col.find().to_list(None): 
        try: await m.reply_to_message.copy(u["_id"]); success += 1; await asyncio.sleep(0.05) 
        except: pass 
    await msg.edit_text(f"✅ Sent to {success} users.")

@app.on_message(filters.command("cnlbdcst") & filters.user(ADMIN_ID)) 
async def cmd_cnlbdcst(c, m): 
    if not m.reply_to_message: return await m.reply("❌ Reply to a message.") 
    await m.reply_to_message.copy(m.text.split()[1]); await m.reply("✅ Message Sent to Channel/Group!")

@app.on_message(filters.command("allred") & filters.user(ADMIN_ID)) 
async def cmd_allred(c, m): 
    await get_db() 
    p = m.text.split(); lim, rng = int(p[1]), p[2].split("-") 
    code = "RND" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=6)) 
    await coupons_col.insert_one({"code": code, "limit": lim, "used_by": [], "is_random": True, "min": int(rng[0]), "max": int(rng[1])}) 
    await m.reply(f"✅ Code: {code}\nLimit: {lim}\nCoins: {rng[0]}-{rng[1]}")

# ==========================================
# 7. FLASK WEB API
# ==========================================
@web.route('/api/get_ad/<int:user_id>/<file_id>') 
def get_ad_api(user_id, file_id): 
    config = sync_db["config"].find_one({"_id": "settings"}) or {} 
    user = sync_db["users"].find_one({"_id": user_id}) 
    file_data = sync_db["files"].find_one({"_id": file_id})

    if user and user.get("premium_until") and user["premium_until"] > datetime.now(): return jsonify({"show_ad": False})
        
    if config.get("ads_on", True):
        links = list(sync_db["ad_links"].find())
        if links:
            ad_link = random.choice(links)["link"]
            is_prem_vid = file_data and file_data.get("is_premium")
            wait_time = config.get("prem_vid_wait", 10) if is_prem_vid else random.choice(config.get("direk_wait", [5]))
            steps = config.get("prstep", 1) if is_prem_vid else config.get("regstep", 1)
            return jsonify({"show_ad": True, "ad_link": ad_link, "wait_time": wait_time, "steps": steps})
    return jsonify({"show_ad": False})

@web.route('/api/redeem', methods=['POST']) 
def redeem_coupon(): 
    data = request.json 
    uid, code = data['uid'], data['code'] 
    coupon = sync_db["coupons"].find_one({"code": code})

    if not coupon: return jsonify({"status": "error", "msg": "❌ Invalid Coupon Code! / কোডটি সঠিক নয়!"})
    if uid in coupon.get("used_by", []): return jsonify({"status": "error", "msg": "❌ You already used this! / আপনি এটি ব্যবহার করেছেন!"})
    if len(coupon.get("used_by", [])) >= coupon.get("limit", 0): return jsonify({"status": "error", "msg": "❌ Coupon limit reached! / কুপনের মেয়াদ শেষ!"})

    coin_to_add = random.randint(coupon["min"], coupon["max"]) if coupon.get("is_random") else coupon.get("coins", 0)
    sync_db["coupons"].update_one({"code": code}, {"$push": {"used_by": uid}})
    sync_db["users"].update_one({"_id": uid}, {"$inc": {"balance": coin_to_add}})

    try: asyncio.run_coroutine_threadsafe(app.send_message(uid, f"🎉 কুপন রিডিম সফল! / Redeemed Successfully! +{coin_to_add} Coins"), loop)
    except: pass
    return jsonify({"status": "success", "msg": f"✅ Successfully redeemed {coin_to_add} coins!"})

@web.route('/api/buy_with_coin', methods=['POST']) 
def buy_with_coin(): 
    data = request.json 
    uid, pkg_id = data['uid'], data['pkg_id'] 
    user = sync_db["users"].find_one({"_id": uid}) 
    pkg = sync_db["packages"].find_one({"_id": ObjectId(pkg_id)})

    if not user or not pkg: return jsonify({"status": "error", "msg": "Invalid Request"})
    if user.get("balance", 0) < pkg["coins"]: return jsonify({"status": "error", "msg": "❌ Insufficient Coins! / পর্যাপ্ত কয়েন নেই!"})

    secs = {"s": 1, "m": 60, "h": 3600, "d": 86400, "y": 31536000}.get(pkg.get("unit", "d").lower()[0], 86400)
    sync_db["users"].update_one({"_id": uid}, {"$inc": {"balance": -pkg["coins"]}, "$set": {"premium_until": datetime.now() + timedelta(seconds=pkg["amount"] * secs)}})
    try: asyncio.run_coroutine_threadsafe(app.send_message(uid, f"🎉 আপনি {pkg['coins']} কয়েন দিয়ে প্রিমিয়াম কিনেছেন! / You bought Premium!"), loop)
    except: pass
    return jsonify({"status": "success", "msg": "✅ Premium Purchased Successfully!"})

@web.route('/api/user/<int:user_id>') 
def get_user(user_id): 
    user = sync_db["users"].find_one({"_id": user_id}) 
    is_prem = False; expiry_str = None 
    if user and user.get("premium_until"): 
        now = datetime.now() 
        if user["premium_until"] > now: 
            is_prem = True 
            sec = int((user["premium_until"] - now).total_seconds()) 
            y, sec = divmod(sec, 31536000); mo, sec = divmod(sec, 2592000) 
            w, sec = divmod(sec, 604800); d, sec = divmod(sec, 86400) 
            h, sec = divmod(sec, 3600); m, sec = divmod(sec, 60)
            res = []
            if y: res.append(f"{y} বছর/y")
            if mo: res.append(f"{mo} মাস/mo")
            if w: res.append(f"{w} সপ্তাহ/w")
            if d: res.append(f"{d} দিন/d")
            if h: res.append(f"{h} ঘণ্টা/h")
            if m: res.append(f"{m} মিনিট/m")
            if sec or not res: res.append(f"{sec} সেকেন্ড/s")
            expiry_str = " ".join(res)

    return jsonify({"balance": user.get("balance", 0) if user else 0, "is_premium": is_prem, "expiry": expiry_str})

# ==========================================
# 8. EXPANDED HTML UI (GLOW TOP DESIGN & LOGIC)
# ==========================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        body { 
            background: linear-gradient(180deg, #18091c 0%, #081016 100%); 
            color: #fff; 
            font-family: 'Hind Siliguri', sans-serif; 
            margin: 0; 
            padding-bottom: 90px; 
            min-height: 100vh; 
        }
        
        * { box-sizing: border-box; }
        
        /* HEADER */
        .header { 
            display: flex; 
            justify-content: space-between; 
            padding: 15px 20px; 
            align-items: center; 
        }
        
        .logo { 
            font-size: 20px; 
            font-weight: bold; 
        }
        
        .coin-pill { 
            background: #ffb703; 
            color: #000; 
            padding: 5px 12px; 
            border-radius: 20px; 
            font-weight: bold; 
            font-size: 14px;
        }

        .lang-btn {
            background: rgba(255,255,255,0.1);
            color: white;
            border: 1px solid #fff;
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 12px;
            cursor: pointer;
            margin-right: 10px;
        }
        
        .prem-badge { 
            background: #c72cff; 
            padding: 2px 8px; 
            border-radius: 10px; 
            font-size: 10px; 
            display:none; 
            margin-left: 5px;
        }
        
        /* PAGE & NAV */
        .page { 
            display: none; 
            padding: 15px; 
        }
        
        .page.active { 
            display: block; 
            animation: fadeIn 0.3s ease-in-out; 
        }
        
        @keyframes fadeIn { 
            from { opacity: 0; transform: translateY(10px); } 
            to { opacity: 1; transform: translateY(0); } 
        }
        
        .bottom-nav { 
            position: fixed; 
            bottom: 0; 
            width: 100%; 
            background: rgba(14,20,30,0.95); 
            display: flex; 
            justify-content: space-around; 
            padding: 10px 0; 
            border-top: 1px solid rgba(255,255,255,0.05); 
            backdrop-filter: blur(10px); 
            z-index: 100;
        }
        
        .nav-item { 
            display: flex; 
            flex-direction: column; 
            align-items: center; 
            font-size: 11px; 
            color: #777; 
            cursor: pointer; 
            padding: 5px 15px; 
            border-radius: 12px;
        }
        
        .nav-item.active { 
            color: #fff; 
            background: rgba(255,255,255,0.05); 
        }
        
        .nav-item span { 
            font-size: 22px; 
            margin-bottom: 2px; 
            filter: grayscale(100%); 
        }
        
        .nav-item.active span { 
            filter: grayscale(0%); 
        }

        /* SEARCH & CATEGORIES */
        .search-box { 
            width: 100%; 
            padding: 14px 20px; 
            border-radius: 12px; 
            border: 1px solid rgba(255,255,255,0.1); 
            background: rgba(0,0,0,0.4); 
            color: white; 
            outline: none; 
            margin-bottom: 15px; 
            font-size: 15px; 
            font-family: 'Hind Siliguri', sans-serif;
        }
        
        /* VIDEO CARDS */
        .video-card { 
            background: rgba(25,25,35,0.8); 
            border-radius: 12px; 
            margin-bottom: 20px; 
            overflow: hidden; 
            position: relative; 
            border: 1px solid rgba(255,255,255,0.05);
        }
        
        .video-card img { 
            width: 100%; 
            height: 210px; 
            object-fit: cover; 
        }
        
        .tag-premium { 
            position: absolute; 
            top: 12px; 
            left: 12px; 
            background: #c72cff; 
            padding: 4px 12px; 
            border-radius: 15px; 
            font-size: 11px; 
            font-weight: bold; 
            box-shadow: 0 2px 10px rgba(199,44,255,0.5);
        }

        .tag-regular { 
            position: absolute; 
            top: 12px; 
            left: 12px; 
            background: #00d4ff; 
            color: black;
            padding: 4px 12px; 
            border-radius: 15px; 
            font-size: 11px; 
            font-weight: bold; 
            box-shadow: 0 2px 10px rgba(0,212,255,0.5);
        }
        
        .play-btn-overlay { 
            position: absolute; 
            top: 40%; 
            left: 50%; 
            transform: translate(-50%, -50%); 
            width: 55px; 
            height: 55px; 
            background: rgba(0,123,255,0.8); 
            border-radius: 50%; 
            display: flex; 
            justify-content: center; 
            align-items: center; 
            cursor: pointer; 
            backdrop-filter: blur(5px); 
            box-shadow: 0 0 15px rgba(0,123,255,0.4);
        }
        
        .play-btn-overlay::after { 
            content: '▶'; 
            color: white; 
            font-size: 22px; 
            margin-left: 4px;
        }
        
        .video-info { 
            padding: 15px; 
        }

        /* PAGINATION */
        .pagination { 
            display: flex; 
            justify-content: center; 
            gap: 5px; 
            flex-wrap: wrap; 
            margin-top: 15px; 
        }
        
        .page-btn { 
            background: rgba(255,255,255,0.1); 
            color: white; 
            border: none; 
            padding: 8px 12px; 
            border-radius: 8px; 
            cursor: pointer; 
            font-weight: bold;
        }
        
        .page-btn.active { 
            background: linear-gradient(90deg, #f02d73, #ff6b6b); 
        }
        
        .page-btn:disabled { 
            opacity: 0.5; 
            cursor: not-allowed; 
        }

        /* SETTINGS & PREMIUM */
        .cat-btn { 
            background: rgba(255,255,255,0.05); 
            padding: 8px 18px; 
            border-radius: 25px; 
            font-size: 13px; 
            cursor: pointer; 
            white-space: nowrap; 
            border: 1px solid rgba(255,255,255,0.1);
        }
        
        .cat-btn.active { 
            background: linear-gradient(90deg, #f02d73, #00d4ff); 
            color: white; 
            border: none; 
            font-weight: bold;
        }
        
        .balance-card { 
            background: linear-gradient(135deg, #4b2354, #1b1c29); 
            border-radius: 15px; 
            padding: 25px; 
            text-align: center; 
            margin-bottom: 20px; 
            border: 1px solid rgba(255,255,255,0.05);
        }
        
        .set-item { 
            display: flex; 
            align-items: center; 
            background: rgba(255,255,255,0.03); 
            padding: 15px; 
            border-radius: 12px; 
            border: 1px solid rgba(255,255,255,0.05); 
            margin-bottom: 12px; 
            cursor: pointer;
        }
        
        .set-icon { 
            width: 45px; 
            height: 45px; 
            border-radius: 12px; 
            display: flex; 
            justify-content: center; 
            align-items: center; 
            font-size: 20px; 
            margin-right: 15px;
        }
        
        .share-banner { 
            background: rgba(0,255,100,0.05); 
            border: 1px solid rgba(0,255,100,0.2); 
            padding: 20px; 
            border-radius: 12px; 
            font-size: 14px; 
            line-height: 1.6; 
            margin-bottom: 25px;
        }
        
        .ref-box { 
            display: flex; 
            background: rgba(255,255,255,0.05); 
            border-radius: 10px; 
            border: 1px solid rgba(255,255,255,0.1); 
            margin-bottom: 25px; 
            overflow: hidden;
        }
        
        .ref-box input { 
            flex: 1; 
            background: transparent; 
            border: none; 
            color: white; 
            padding: 15px; 
            font-size: 14px; 
            outline: none;
        }
        
        .ref-box button { 
            background: rgba(255,255,255,0.1); 
            color: #00d4ff; 
            border: none; 
            padding: 0 20px; 
            font-weight: bold; 
            cursor: pointer;
        }

        /* BUTTONS & MODALS */
        .btn-main { 
            width: 100%; 
            background: linear-gradient(90deg, #f02d73, #ff6b6b); 
            padding: 16px; 
            border-radius: 12px; 
            font-weight: bold; 
            border: none; 
            color: white; 
            font-size: 16px; 
            cursor: pointer; 
            font-family: 'Hind Siliguri', sans-serif;
        }
        
        .modal-overlay { 
            display: none; 
            position: fixed; 
            top: 0; 
            left: 0; 
            width: 100%; 
            height: 100%; 
            background: rgba(8,16,22,0.98); 
            z-index: 9999; 
            justify-content: center; 
            align-items: center; 
            backdrop-filter: blur(5px);
        }
        
        .modal-box { 
            background: rgba(30, 30, 45, 0.95); 
            padding: 30px 25px; 
            border-radius: 20px; 
            text-align: center; 
            width: 90%; 
            max-width: 400px; 
            border: 1px solid rgba(255,255,255,0.05);
        }
        
        .alert-box { 
            background: rgba(255,0,0,0.1); 
            border: 1px solid #ff4d4d; 
            color: #ffb3b3; 
            padding: 15px; 
            border-radius: 12px; 
            font-size: 13px; 
            margin: 15px 0;
        }

        .lang-en { display: none; }
    </style>
</head>
<body>

<!-- HEADER -->
<div class="header">
    <div class="logo">
        {{ site_name }}
        <span class="prem-badge" id="prem-badge">VIP</span>
    </div>
    <div style="display:flex; align-items:center;">
        <button class="lang-btn" onclick="toggleLanguage()" id="lang-btn">English</button>
        <div class="coin-pill">🏛 <span id="hdr-balance">0</span></div>
    </div>
</div>

<!-- STRICT 18+ AGE MODAL (EVERY TIME) -->
<div id="age-modal" class="modal-overlay">
    <div class="modal-box">
        <div style="font-size: 55px; margin-bottom:10px;">🔞</div>
        <h2 style="margin-top:0;">
            <span class="lang-bn">বয়স নিশ্চিতকরণ</span>
            <span class="lang-en">Age Verification</span>
        </h2>
        <p style="font-size:14px; color:#aaa;">
            <span class="lang-bn">এই ওয়েবসাইটের কনটেন্ট শুধুমাত্র <b style="color:#00d4ff;">১৮ বছর বা তার বেশি বয়সী</b> ব্যবহারকারীদের জন্য প্রযোজ্য।</span>
            <span class="lang-en">This website content is strictly for users who are <b style="color:#00d4ff;">18 years of age or older</b>.</span>
        </p>
        <div class="alert-box">
            <span class="lang-bn">⚠️ আপনার বয়স ১৮+ না হলে সাইটটি ব্যবহার করবেন না।</span>
            <span class="lang-en">⚠️ Do not enter if you are under 18.</span>
        </div>
        <button class="btn-main" style="background: linear-gradient(90deg, #00d4ff, #00ffcc); color:black; margin-bottom:10px;" onclick="confirmAge()">
            <span class="lang-bn">✅ হ্যাঁ, আমার বয়স ১৮+ বছর</span>
            <span class="lang-en">✅ Yes, I am 18+</span>
        </button>
        <button class="btn-main" style="background: transparent; border: 1px solid #555; color: #888;" onclick="tg.close()">
            <span class="lang-bn">❌ না, বের হয়ে যান</span>
            <span class="lang-en">❌ No, Exit</span>
        </button>
    </div>
</div>

<!-- AD OVERLAY -->
<div id="ad-overlay" class="modal-overlay">
    <div class="modal-box" style="background:transparent; border:none; box-shadow:none;">
        <div style="background: rgba(255,255,255,0.1); padding: 5px 15px; border-radius: 20px; display:inline-block; margin-bottom: 15px; font-weight:bold;" id="step-info">Step 1 of 1</div>
        <h1 id="timer-count" style="font-size:90px; color:#f02d73; margin:0;">5</h1>
        <p style="font-size:16px; color:#aaa;">
            <span class="lang-bn">অ্যাড দেখার পর ফাইলটি পাবেন (ব্যাক দিলে টাইম রিফ্রেশ হবে না)</span>
            <span class="lang-en">You will get the file after ad (Timer saves on exit)</span>
        </p>
        <button id="get-file-btn" class="btn-main" style="background: linear-gradient(90deg, #00d4ff, #00ffcc); color:black; display:none;">Next Step</button>
    </div>
</div>

<!-- ALL VIDEOS PAGE (HOME) -->
<div id="page-home" class="page active">
    <input type="text" id="search-bar" class="search-box bn-pl" placeholder="🔍 Search all videos..." onkeyup="handleSearch('home')">
    <div id="home-video-list"></div>
    <div class="pagination" id="home-pagination"></div>
</div>

<!-- REGULAR VIDEOS PAGE -->
<div id="page-regvids" class="page">
    <input type="text" id="search-bar-reg" class="search-box bn-pl" placeholder="🔍 Search Regular Videos..." onkeyup="handleSearch('reg')">
    <div id="reg-video-list"></div>
    <div class="pagination" id="reg-pagination"></div>
</div>

<!-- PREMIUM VIDEOS PAGE -->
<div id="page-premvids" class="page">
    <input type="text" id="search-bar-prem" class="search-box bn-pl" placeholder="🔍 Search Premium Videos..." onkeyup="handleSearch('prem')">
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
            <button class="btn-main" style="margin:0; padding:12px;" onclick="reqBuy()">
                <span class="lang-bn">কিনুন</span><span class="lang-en">Buy Now</span>
            </button>
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
            <button class="btn-main" style="margin:0; padding:12px; background:linear-gradient(90deg, #00d4ff, #00ffcc); color:black;" onclick="reqBuy()">
                <span class="lang-bn">কিনুন</span><span class="lang-en">Buy Now</span>
            </button>
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
            <button class="btn-main" style="margin:0; padding:12px; background:#c72cff;" onclick="buyWithCoin('{{ pkg._id }}', {{ pkg.coins }})">
                <span class="lang-bn">কয়েন দিয়ে নিন</span><span class="lang-en">Exchange Coin</span>
            </button>
        </div>
        {% endfor %}
    </div>
</div>

<!-- SETTINGS PAGE (USER PROFILE & MEMBERSHIP) -->
<div id="page-settings" class="page">
    <div class="balance-card">
        <p style="margin:0; color:#aaa; font-size:12px; letter-spacing:1px;">
            <span class="lang-bn">আপনার ব্যালেন্স</span><span class="lang-en">YOUR BALANCE</span>
        </p>
        <h1 style="color:#ffb703; margin:15px 0 10px 0; font-size:48px;">🏛 <span id="set-balance">0</span></h1>
        <p style="margin:0; color:#666; font-size:12px; margin-bottom:5px;">ID: <span id="set-id"></span></p>
        
        <div id="mem-status" style="display:inline-block; padding:5px 15px; border-radius:15px; font-size:12px; font-weight:bold; background:rgba(255,255,255,0.1); margin-top:5px;">👤 Regular Member</div>
        <div id="mem-expiry" style="color:#ffb703; font-size:11px; margin-top:5px; display:none;"></div>
    </div>
    
    <div class="set-item" onclick="switchNav('coupon')">
        <div class="set-icon" style="background: linear-gradient(135deg, #a18cd1, #fbc2eb);">🎟</div>
        <div>
            <b style="display:block; font-size:16px;"><span class="lang-bn">কুপন কোড</span><span class="lang-en">Coupon Code</span></b>
            <span style="color:#aaa; font-size:12px;"><span class="lang-bn">কোড রিডিম করে ফ্রি কয়েন নিন</span><span class="lang-en">Redeem to get free coins</span></span>
        </div>
    </div>
    
    <div class="set-item" onclick="switchNav('share')">
        <div class="set-icon" style="background: linear-gradient(135deg, #ffecd2, #fcb69f);">🎁</div>
        <div>
            <b style="display:block; font-size:16px;"><span class="lang-bn">বন্ধুকে শেয়ার করুন</span><span class="lang-en">Share with Friends</span></b>
            <span style="color:#aaa; font-size:12px;"><span class="lang-bn">ইনভাইট করে ফ্রি কয়েন জিতুন</span><span class="lang-en">Invite and win free coins</span></span>
        </div>
    </div>
</div>

<!-- SUB PAGES -->
<div id="page-coupon" class="page">
    <h2 style="margin-top:0;">🎟 <span class="lang-bn">কুপন কোড</span><span class="lang-en">Coupon Code</span></h2>
    <div style="display:flex; gap:10px; margin-bottom:20px;">
        <input type="text" id="coupon-input" class="search-box" style="margin:0; border-radius:12px;" placeholder="Enter coupon">
        <button class="btn-main" style="width:auto; margin:0; padding:0 25px;" onclick="redeemCoupon()">Redeem</button>
    </div>
</div>

<div id="page-share" class="page">
    <h2 style="margin-top:0;">🎁 <span class="lang-bn">শেয়ার করুন</span><span class="lang-en">Share</span></h2>
    <div class="share-banner">
        <span class="lang-bn">🥳 বন্ধু আপনার লিংক দিয়ে স্টার্ট করলেই <b style="color:#ffb703;">বোনাস</b> পাবেন!</span>
        <span class="lang-en">🥳 Get <b style="color:#ffb703;">Bonus</b> when a friend starts using your link!</span>
    </div>
    <div class="ref-box">
        <input type="text" id="ref-link" readonly>
        <button onclick="copyRef()">📋 Copy</button>
    </div>
</div>

<!-- BOTTOM NAV -->
<div class="bottom-nav">
    <div class="nav-item active" onclick="switchNav('home', this)"><span>🏠</span> All Vids</div>
    <div class="nav-item" onclick="switchNav('regvids', this)"><span>👤</span> Regular</div>
    <div class="nav-item" onclick="switchNav('premvids', this)"><span>💎</span> VIP Vids</div>
    <div class="nav-item" onclick="switchNav('premium', this)"><span>🛒</span> Buy VIP</div>
    <div class="nav-item" onclick="switchNav('settings', this)"><span>⚙️</span> Setting</div>
</div>

<!-- JAVASCRIPT LOGIC -->
<script>
    let tg = window.Telegram.WebApp;
    tg.expand();
    let botUsername = "{{ bot_username }}";
    let adminUsername = "{{ config.payment_admin }}";
    let userId = tg.initDataUnsafe.user ? tg.initDataUnsafe.user.id : 123456789; 
    
    document.getElementById('set-id').innerText = userId;
    document.getElementById('ref-link').value = `https://t.me/${botUsername}?start=${userId}`;
    
    let userBalance = 0;
    
    // LANGUAGE LOGIC
    let currentLang = localStorage.getItem('appLang') || 'bn';
    
    function applyLanguage() {
        let isBn = currentLang === 'bn';
        document.querySelectorAll('.lang-bn').forEach(el => el.style.display = isBn ? 'inline-block' : 'none');
        document.querySelectorAll('.lang-en').forEach(el => el.style.display = isBn ? 'none' : 'inline-block');
        document.getElementById('lang-btn').innerText = isBn ? 'English' : 'বাংলা';
        localStorage.setItem('appLang', currentLang);
    }
    
    function toggleLanguage() {
        currentLang = currentLang === 'bn' ? 'en' : 'bn';
        applyLanguage();
    }
    applyLanguage();

    async function loadUser() {
        let res = await fetch('/api/user/' + userId);
        let data = await res.json();
        userBalance = data.balance;
        
        document.getElementById('hdr-balance').innerText = userBalance;
        document.getElementById('set-balance').innerText = userBalance;
        
        if(data.is_premium) {
            document.getElementById('prem-badge').style.display = 'inline-block';
            let memBox = document.getElementById('mem-status');
            memBox.innerHTML = '💎 Premium Member';
            memBox.style.background = 'linear-gradient(90deg, #c72cff, #ff007f)';
            memBox.style.color = '#fff';
            let expBox = document.getElementById('mem-expiry');
            expBox.style.display = 'block';
            expBox.innerText = (currentLang==='bn'?"মেয়াদ: ":"Expiry: ") + data.expiry;
        } else {
            document.getElementById('prem-badge').style.display = 'none';
            let memBox = document.getElementById('mem-status');
            memBox.innerHTML = '👤 Regular Member';
            memBox.style.background = 'rgba(255,255,255,0.1)';
            memBox.style.color = '#fff';
            document.getElementById('mem-expiry').style.display = 'none';
        }
    }
    loadUser();

    // STRICT 18+ NOTICE - EVERY SINGLE TIME IT OPENS
    document.getElementById('age-modal').style.display = 'flex';
    function confirmAge() { 
        document.getElementById('age-modal').style.display = 'none'; 
    }

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

    // --- PAGINATION LOGIC (1 2 3 See All) ---
    let allFiles = {{ files_json | safe }};
    let state = { home: { p: 1, lim: 20, q: "" }, reg: { p: 1, lim: 20, q: "" }, prem: { p: 1, lim: 20, q: "" } };

    function renderPagination(tab, total) {
        let s = state[tab];
        let maxP = Math.ceil(total / s.lim) || 1;
        if(s.p > maxP) s.p = maxP;
        
        let html = `<button class="page-btn" onclick="chgP('${tab}', -1)" ${s.p===1?'disabled':''}>Prev</button>`;
        
        let start = Math.max(1, s.p - 1);
        let end = Math.min(maxP, start + 2);
        if(end - start < 2) start = Math.max(1, end - 2);
        
        for(let i=start; i<=end; i++){
            html += `<button class="page-btn ${s.p===i?'active':''}" onclick="setP('${tab}', ${i})">${i}</button>`;
        }
        html += `<button class="page-btn" onclick="chgP('${tab}', 1)" ${s.p>=maxP?'disabled':''}>Next</button>`;
        html += `<button class="page-btn" style="background:#444;" onclick="setLim('${tab}', 100)">All</button>`;
        
        document.getElementById(`${tab}-pagination`).innerHTML = html;
    }

    function renderList(tab) {
        let s = state[tab];
        let filtered = allFiles.filter(f => {
            if(tab === 'prem' && !f.is_premium) return false;
            if(tab === 'reg' && f.is_premium) return false;
            return f.title.toLowerCase().includes(s.q);
        });
        
        let start = (s.p - 1) * s.lim;
        let pageFiles = filtered.slice(start, start + s.lim);
        
        let html = "";
        if(pageFiles.length === 0) html = "<p style='text-align:center; color:#666;'>No videos found!</p>";
        
        pageFiles.forEach(f => {
            let tag = f.is_premium ? '<div class="tag-premium">💎 VIP</div>' : '<div class="tag-regular">👤 Regular</div>';
            html += `<div class="video-card">
                <img src="${f.thumb_url || 'https://placehold.co/600x400/1c1c24/ff007f?text=Media'}">
                ${tag}
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

    function handleSearch(tab) { 
        let id = tab==='home'? 'search-bar' : 'search-bar-'+tab;
        state[tab].q = document.getElementById(id).value.toLowerCase(); 
        state[tab].p = 1; 
        renderList(tab); 
    }
    function chgP(tab, dir) { state[tab].p += dir; renderList(tab); }
    function setP(tab, num) { state[tab].p = num; renderList(tab); }
    function setLim(tab, lim) { state[tab].lim = lim; state[tab].p = 1; renderList(tab); }

    renderList('home'); 
    renderList('reg');
    renderList('prem');

    // --- ADS ANTI-CHEAT TIMER ---
    let currentDeepLink = "";
    let adDataGlobal = null;
    let timerInterval = null;
    let cFileId = null;

    async function playVideo(fileId) {
        cFileId = fileId;
        currentDeepLink = `https://t.me/${botUsername}?start=file_${fileId}`;
        let res = await fetch(`/api/get_ad/${userId}/${fileId}`);
        adDataGlobal = await res.json();

        if (adDataGlobal.show_ad) {
            startAdProcess();
        } else {
            tg.openTelegramLink(currentDeepLink);
            setTimeout(() => tg.close(), 500);
        }
    }

    function startAdProcess() {
        document.getElementById('ad-overlay').style.display = 'flex';
        document.getElementById('get-file-btn').style.display = 'none';
        document.getElementById('timer-count').style.display = 'block';

        let adState = JSON.parse(localStorage.getItem('ad_state_' + cFileId)) || {
            step: 1, timeLeft: adDataGlobal.wait_time
        };
        
        document.getElementById('step-info').innerText = `Step ${adState.step} of ${adDataGlobal.steps}`;
        document.getElementById('timer-count').innerText = adState.timeLeft;
        
        window.open(adDataGlobal.ad_link, '_blank');

        clearInterval(timerInterval);
        timerInterval = setInterval(() => {
            adState.timeLeft--;
            if (adState.timeLeft <= 0) {
                clearInterval(timerInterval);
                document.getElementById('timer-count').style.display = 'none';
                
                if (adState.step < adDataGlobal.steps) {
                    let btn = document.getElementById('get-file-btn');
                    btn.innerText = "Next Step";
                    btn.style.display = 'block';
                    btn.onclick = () => {
                        adState.step++;
                        adState.timeLeft = adDataGlobal.wait_time;
                        localStorage.setItem('ad_state_' + cFileId, JSON.stringify(adState));
                        startAdProcess();
                    };
                } else {
                    let btn = document.getElementById('get-file-btn');
                    btn.innerText = currentLang === 'bn' ? "ফাইল নিন" : "Get File Now";
                    btn.style.display = 'block';
                    btn.onclick = () => {
                        localStorage.removeItem('ad_state_' + cFileId);
                        tg.openTelegramLink(currentDeepLink);
                        setTimeout(()=>tg.close(), 500);
                    };
                }
            } else {
                document.getElementById('timer-count').innerText = adState.timeLeft;
                localStorage.setItem('ad_state_' + cFileId, JSON.stringify(adState));
            }
        }, 1000);
    }

    async function redeemCoupon() {
        let code = document.getElementById('coupon-input').value;
        if(!code) return tg.showAlert(currentLang==='bn'?"কোড লিখুন!":"Enter Code!");
        let res = await fetch('/api/redeem', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ uid: userId, code: code }) });
        let data = await res.json();
        tg.showAlert(data.msg);
        if(data.status === 'success') { 
            loadUser(); 
            document.getElementById('coupon-input').value = ""; 
        }
    }
    
    async function buyWithCoin(pkgId, cost) {
        if(userBalance < cost) return tg.showAlert(currentLang==='bn'?"❌ আপনার পর্যাপ্ত কয়েন নেই!":"❌ Insufficient Coins!");
        let confirmText = currentLang === 'bn' ? `আপনি কি ${cost} কয়েন দিয়ে প্রিমিয়াম নিতে চান?` : `Buy VIP with ${cost} coins?`;
        if(confirm(confirmText)) {
            let res = await fetch('/api/buy_with_coin', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ uid: userId, pkg_id: pkgId }) });
            let data = await res.json();
            tg.showAlert(data.msg);
            loadUser();
        }
    }

    function copyRef() { 
        let c = document.getElementById("ref-link"); 
        c.select(); 
        navigator.clipboard.writeText(c.value); 
        tg.showAlert(currentLang==='bn'?"✅ রেফার লিংক কপি হয়েছে!":"✅ Link Copied!"); 
    }
    
    function reqBuy() { 
        tg.openTelegramLink(`https://t.me/${adminUsername}`); 
        tg.showAlert(currentLang==='bn'?"✅ পেমেন্ট করতে অ্যাডমিনকে ইনবক্সে মেসেজ দিন।":"✅ Inbox Admin to pay."); 
    }
</script>
</body>
</html>
"""

@web.route('/') 
def home(): 
    files = list(sync_db["files"].find().sort("_id", -1)) 
    for f in files: f["_id"] = str(f["_id"]) 
    config = sync_db["config"].find_one({"_id": "settings"}) or {}
    return render_template_string(HTML_TEMPLATE, files_json=json.dumps(files), pkgs=list(sync_db["packages"].find()), bot_username=BOT_USERNAME, config=config, site_name=config.get("site_name", "Glow Top"))

# ==========================================
# 9. RUN LOGIC (SAFE & ROBUST)
# ==========================================
def run_flask(): 
    web.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)), debug=False)

async def main_bot(): 
    await get_db() 
    await get_config() 
    await app.start() 
    print("✅ Bot Started Successfully!") 
    asyncio.create_task(background_tasks()) 
    await idle() 
    await app.stop()

if __name__ == "__main__": 
    threading.Thread(target=run_flask, daemon=True).start() 
    while True: 
        try: 
            loop.run_until_complete(main_bot()) 
        except FloodWait as e: 
            print(f"⚠️ Rate Limit: Waiting {e.value}s...") 
            time.sleep(e.value) 
        except Exception as e: 
            print(f"❌ Error: {e}") 
            time.sleep(5)
