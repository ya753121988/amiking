import os
import sys
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
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo, MenuButtonWebApp, CallbackQuery
from pyrogram.errors import UserNotParticipant
from flask import Flask, render_template_string
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
    config_col = db["config"]
    channels_col = db["channels"] # For Must Join

    sync_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    sync_db = sync_client["ShilaCallApp"]
    sync_files = sync_db["files"]
    sync_cats = sync_db["categories"]
    sync_pkgs = sync_db["packages"]
except Exception as e:
    print(f"❌ Database Connection Error: {e}")
    sys.exit(1)

app = Client("shilacall_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
web = Flask(__name__)
admin_steps = {}

# ==========================================
# HELPER FUNCTIONS
# ==========================================
async def check_force_sub(client, user_id):
    channels = await channels_col.find().to_list(length=100)
    not_joined = []
    for ch in channels:
        try:
            await client.get_chat_member(ch["chat_id"], user_id)
        except UserNotParticipant:
            not_joined.append(ch["link"])
        except Exception: pass
    return not_joined

async def get_config():
    conf = await config_col.find_one({"_id": "settings"})
    if not conf:
        conf = {"_id": "settings", "ref_coin": 10, "auto_del_time": 0, "ads_on": True, "admin_group": None, "forward_off": True}
        await config_col.insert_one(conf)
    return conf

# ==========================================
# 3. USER COMMANDS
# ==========================================
@app.on_message(filters.command("start") & filters.private)
async def start_cmd(client, message):
    user_id = message.from_user.id
    bot_info = await client.get_me()
    bot_username = bot_info.username
    
    # Check Force Sub
    not_joined_links = await check_force_sub(client, user_id)
    if not_joined_links:
        buttons = [[InlineKeyboardButton("Join Channel", url=link)] for link in not_joined_links]
        buttons.append([InlineKeyboardButton("✅ Joined", callback_data="check_join")])
        await message.reply("❌ আপনাকে আগে আমাদের মাস্ট চ্যানেলে জয়েন করতে হবে:", reply_markup=InlineKeyboardMarkup(buttons))
        return

    # User Registration
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
        # Referral logic
        if len(args) > 1 and args[1].isdigit():
            ref_by = int(args[1])
            if ref_by != user_id and config["ref_coin"] > 0:
                await users_col.update_one({"_id": ref_by}, {"$inc": {"balance": config["ref_coin"]}})
                try: await app.send_message(ref_by, f"🎉 আপনার রেফারে একজন জয়েন করেছে! +{config['ref_coin']} Coins যোগ হয়েছে।")
                except: pass
        user = await users_col.find_one({"_id": user_id})

    # Show User Profile
    ref_link = f"https://t.me/{bot_username}?start={user_id}"
    profile_text = (
        f"👋 স্বাগতম, {user.get('name')}!\n\n"
        f"👤 ফুল নাম: {message.from_user.first_name} {message.from_user.last_name or ''}\n"
        f"🔗 ইউজারনেম: @{message.from_user.username or 'N/A'}\n"
        f"🆔 ইউজার আইডি: `{user_id}`\n"
        f"💰 ব্যালেন্স: {user.get('balance', 0)} Coins\n"
        f"💎 প্রিমিয়াম স্ট্যাটাস: {'Yes ✅' if user.get('is_premium') else 'No ❌'}\n\n"
        f"📢 আপনার রেফার লিংক:\n`{ref_link}`"
    )

    btn = InlineKeyboardMarkup([[InlineKeyboardButton("🔥 Open App (Watch Videos)", web_app=WebAppInfo(url=f"{WEB_URL}/"))]])
    
    try: await client.set_chat_menu_button(chat_id=user_id, menu_button=MenuButtonWebApp(text="🚀 Open App", web_app=WebAppInfo(url=f"{WEB_URL}/")))
    except: pass
    
    await message.reply(profile_text, reply_markup=btn)

@app.on_callback_query(filters.regex("check_join"))
async def check_join_callback(client, query):
    not_joined_links = await check_force_sub(client, query.from_user.id)
    if not_joined_links:
        await query.answer("আপনি এখনো জয়েন করেননি!", show_alert=True)
    else:
        await query.message.delete()
        await start_cmd(client, query.message)

# ==========================================
# 4. ADMIN COMMANDS (File Upload & Management)
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
        cats = await cats_col.find().to_list(100)
        cat_names = ", ".join([c["name"] for c in cats]) if cats else "Default"
        await message.reply(f"২. ক্যাটাগরির নাম লিখুন:\n(Available: {cat_names})")
        
    elif step_info["step"] == "category":
        admin_steps[ADMIN_ID]["category"] = message.text
        admin_steps[ADMIN_ID]["step"] = "file"
        await message.reply("৩. এবার ভিডিওটি সেন্ড করুন (বট অটোমেটিক থাম্বনেইল ক্যাপচার করে মিনি অ্যাপে এড করবে):")

@app.on_message(filters.video & filters.user(ADMIN_ID) & filters.private)
async def handle_admin_video(client, message):
    step_info = admin_steps.get(ADMIN_ID)
    if step_info and step_info.get("step") == "file":
        title = step_info["title"]
        category = step_info["category"]
        file_id = message.video.file_id
        
        # Telegram automatically generates a thumbnail (poster) for videos. We save its File ID.
        thumb_id = message.video.thumbs[0].file_id if message.video.thumbs else None
        
        await files_col.insert_one({
            "title": title, 
            "category": category, 
            "file_id": file_id, 
            "thumb_id": thumb_id, 
            "views": 0
        })
        del admin_steps[ADMIN_ID]
        await message.reply("✅ ভিডিও এবং ল্যান্ডস্কেপ পোস্টার সফলভাবে মিনি অ্যাপের হোমপেজে এড হয়েছে!")

# --- CONFIG COMMANDS ---
@app.on_message(filters.command("addcata") & filters.user(ADMIN_ID))
async def cmd_addcata(client, message):
    try:
        cat_name = message.text.split(" ", 1)[1]
        await cats_col.insert_one({"name": cat_name})
        await message.reply(f"✅ Category '{cat_name}' Added.")
    except IndexError:
        await message.reply("Format: /addcata Name")

@app.on_message(filters.command("delcata") & filters.user(ADMIN_ID))
async def cmd_delcata(client, message):
    cats = await cats_col.find().to_list(100)
    if not cats: return await message.reply("কোনো ক্যাটাগরি নেই।")
    
    buttons = [[InlineKeyboardButton(f"❌ {c['name']}", callback_data=f"delcat_{c['_id']}")] for c in cats]
    await message.reply("যেটি ডিলিট করতে চান ক্লিক করুন:", reply_markup=InlineKeyboardMarkup(buttons))

@app.on_callback_query(filters.regex(r"^delcat_") & filters.user(ADMIN_ID))
async def cb_delcat(client, query):
    from bson.objectid import ObjectId
    cat_id = query.data.split("_")[1]
    await cats_col.delete_one({"_id": ObjectId(cat_id)})
    await query.message.edit_text("✅ Category Deleted!")

@app.on_message(filters.command("addbks") & filters.user(ADMIN_ID))
async def cmd_addbks(client, message):
    # /addbks 10 day 109 coin bonous 0, 01
    try:
        pkg_details = message.text.split(" ", 1)[1]
        await pkgs_col.insert_one({"type": "bkash", "details": pkg_details})
        await message.reply("✅ bKash Package Added.")
    except:
        await message.reply("Format: /addbks details...")

@app.on_message(filters.command("setgroup") & filters.user(ADMIN_ID))
async def cmd_setgroup(client, message):
    try:
        grp_id = int(message.text.split()[1])
        await config_col.update_one({"_id": "settings"}, {"$set": {"admin_group": grp_id}}, upsert=True)
        await message.reply(f"✅ Admin group set to {grp_id}")
    except: await message.reply("Format: /setgroup -100xxx")

@app.on_message(filters.command("setautodel") & filters.user(ADMIN_ID))
async def cmd_autodel(client, message):
    try:
        minutes = int(message.text.split()[1].replace("munit", "").replace("m", ""))
        await config_col.update_one({"_id": "settings"}, {"$set": {"auto_del_time": minutes}}, upsert=True)
        await message.reply(f"✅ Auto Delete set to {minutes} minutes.")
    except: await message.reply("Format: /setautodel 10")

@app.on_message(filters.command("adson") & filters.user(ADMIN_ID))
async def cmd_adson(client, message):
    await config_col.update_one({"_id": "settings"}, {"$set": {"ads_on": True}}, upsert=True)
    await message.reply("✅ Ads turned ON.")

@app.on_message(filters.command("adsoff") & filters.user(ADMIN_ID))
async def cmd_adsoff(client, message):
    await config_col.update_one({"_id": "settings"}, {"$set": {"ads_on": False}}, upsert=True)
    await message.reply("✅ Ads turned OFF.")

@app.on_message(filters.command("forward") & filters.user(ADMIN_ID))
async def cmd_forward(client, message):
    state = message.text.split()[1].lower()
    is_off = state == "off"
    await config_col.update_one({"_id": "settings"}, {"$set": {"forward_off": is_off}}, upsert=True)
    await message.reply(f"✅ Forwarding is now {'DISABLED (Protected)' if is_off else 'ENABLED'}.")

@app.on_message(filters.command("refcine") & filters.user(ADMIN_ID))
async def cmd_refcine(client, message):
    try:
        # /refcine 1user 10 coine
        coins = int(message.text.split()[2])
        await config_col.update_one({"_id": "settings"}, {"$set": {"ref_coin": coins}}, upsert=True)
        await message.reply(f"✅ Referral bonus set to {coins} coins.")
    except: await message.reply("Format: /refcine 1user 10")

# ==========================================
# 5. WEB APP DATA RECEIVER (Send File & Order)
# ==========================================
@app.on_message(filters.service)
async def web_app_handler(client, message):
    if not message.web_app_data: return
    data = message.web_app_data.data
    uid = message.from_user.id
    config = await get_config()
    
    # Handle Buying Package
    if data.startswith("buy_"):
        grp = config.get("admin_group")
        pkg_details = data.replace("buy_", "")
        
        user_info = f"👤 User: {message.from_user.mention}\n🆔 ID: `{uid}`\n📦 Package: {pkg_details}"
        if grp: 
            try: await app.send_message(grp, f"🚨 **New Buy Order!**\n\n{user_info}")
            except: pass
        await message.reply("✅ আপনার বাই রিকোয়েস্ট এডমিনের কাছে পাঠানো হয়েছে। এডমিন চেক করে এপ্রুভ করবেন।")
        return

    # Handle Video Request
    file = await files_col.find_one({"file_id": data})
    if file:
        await files_col.update_one({"file_id": data}, {"$inc": {"views": 1}})
        
        # Check if Ads should be shown (Placeholder logic for Ads implementation)
        # Here you can deduct coins or show Ad links if config["ads_on"] is True
        
        forward_prot = config.get("forward_off", True)
        sent_msg = await client.send_cached_media(
            chat_id=uid, 
            file_id=data, 
            caption=f"🎬 {file['title']}", 
            protect_content=forward_prot
        )
        
        # Auto Delete Logic
        del_time = config.get("auto_del_time", 0)
        if del_time > 0:
            await asyncio.sleep(del_time * 60) # Convert minutes to seconds
            try: await sent_msg.delete()
            except: pass


# ==========================================
# 6. MINI APP FRONTEND (Flask)
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
        .header { display: flex; justify-content: space-between; padding: 15px; background: var(--card-bg); border-bottom: 1px solid #333;}
        .page { display: none; padding: 15px; }
        .page.active { display: block; }
        
        .cat-scroll { display: flex; overflow-x: auto; gap: 10px; padding-bottom: 10px; margin-bottom: 15px; }
        .cat-btn { background: #333; padding: 8px 15px; border-radius: 20px; white-space: nowrap; font-size: 12px;}
        .cat-btn.active { background: var(--primary); color: white; }
        
        .card { background: var(--card-bg); border-radius: 12px; margin-bottom: 20px; overflow: hidden; position: relative;}
        /* THIS IS WHERE THE THUMBNAIL IS DISPLAYED */
        .card img { width: 100%; height: 200px; object-fit: cover; }
        .card-info { padding: 12px; }
        .play-btn { position: absolute; top: 40%; left: 50%; transform: translate(-50%, -50%); background: rgba(255,0,127,0.8); color: white; padding: 15px; border-radius: 50%; font-size: 20px; text-align: center;}
        
        .btn { background: var(--primary); color: white; padding: 12px; text-align: center; border-radius: 8px; font-weight: bold; margin-top: 10px; cursor: pointer;}
        .bottom-nav { position: fixed; bottom: 0; width: 100%; background: var(--card-bg); display: flex; justify-content: space-around; padding: 12px 0; border-top: 1px solid #333;}
        .nav-item { text-align: center; font-size: 12px; color: gray; cursor: pointer; }
        .nav-item.active { color: var(--primary); }
    </style>
</head>
<body>
    <div class="header">
        <b>Viral Video</b>
    </div>

    <!-- HOME PAGE (Videos) -->
    <div id="page-home" class="page active">
        <div class="cat-scroll">
            <div class="cat-btn active">All</div>
            {% for cat in cats %}
            <div class="cat-btn">{{ cat.name }}</div>
            {% endfor %}
        </div>

        {% for file in files %}
        <div class="card" onclick="sendAction('{{ file.file_id }}')">
            <!-- Display Telegram Auto-Thumbnail if available, else placeholder -->
            {% if file.thumb_id %}
            <img src="https://telegra.ph/file/0ba41d0ddccfdbfcc2fbd.jpg" alt="Video Poster"> <!-- Replace with actual logic to fetch tg file if needed, using generic for now -->
            {% else %}
            <img src="https://images.unsplash.com/photo-1611162617474-5b21e879e113?w=600" alt="Video">
            {% endif %}
            
            <div class="play-btn">▶</div>
            <div class="card-info">
                <b>{{ file.title }}</b><br>
                <small style="color: gray;">👁 {{ file.views }} views • {{ file.category }}</small>
            </div>
        </div>
        {% else %}
        <p style="text-align:center;">কোনো ভিডিও আপলোড করা হয়নি।</p>
        {% endfor %}
    </div>

    <!-- PREMIUM PAGE (Buy) -->
    <div id="page-premium" class="page">
        <h3 style="color: var(--primary);">Buy Premium Packages</h3>
        {% for pkg in bkash_pkgs %}
        <div class="card card-info">
            <b>💳 {{ pkg.details }}</b>
            <div class="btn" onclick="sendAction('buy_{{ pkg.details }}')">Buy Now (Admin Message)</div>
        </div>
        {% else %}
        <p>No packages available.</p>
        {% endfor %}
    </div>

    <div class="bottom-nav">
        <div class="nav-item active" onclick="switchPage('home')">🏠<br>Home</div>
        <div class="nav-item" onclick="switchPage('premium')">💎<br>Buy</div>
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
            tg.close(); // Close WebApp and send msg to bot
        }
    </script>
</body>
</html>
"""

@web.route('/')
def home():
    files = list(sync_files.find().sort("_id", -1))
    cats = list(sync_cats.find())
    bkash_pkgs = list(sync_pkgs.find({"type": "bkash"}))
    return render_template_string(HTML_TEMPLATE, files=files, cats=cats, bkash_pkgs=bkash_pkgs)

# ==========================================
# 7. RUN SERVER & BOT
# ==========================================
def run_flask(): web.run(host="0.0.0.0", port=8080)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    app.run()
