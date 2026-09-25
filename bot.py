মোবাইল বা ছোট স্ক্রিনে কোড ব্লকটি পুরো টেক্সট হিসেবে দেখা যেতে পারে, কারণ এটি অনেক বড় একটি কোড ফাইল। কোডটি যাতে সহজেই কপি বক্সে সিলেক্ট করে কপি করা যায়, তাই নিচে এটিকে স্ট্যান্ডার্ড **Markdown Code Block** হিসেবে দেওয়া হলো:

```python
import os
import asyncio
import threading
import time

# --- RENDER ASYNC LOOP FIX ---
try:
    loop = asyncio.get_event_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo, MenuButtonWebApp
from flask import Flask, render_template_string, request
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient

# ==========================================
# 1. CONFIGURATION
# ==========================================
API_ID = int(os.environ.get("API_ID", 29904834))
API_HASH = os.environ.get("API_HASH", "8b4fd9ef578af114502feeafa2d31938")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8206083172:AAHP9raleY3l2R2HBTGSVCdpcLQvgn960Mw")
MONGO_URI = os.environ.get("MONGO_URI", "YOUR_CORRECT_MONGODB_URI_HERE")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 7120801813))
WEB_URL = os.environ.get("WEB_URL", "https://amiking.onrender.com")
PORT = int(os.environ.get("PORT", 8080))

# ==========================================
# 2. DATABASE SETUP (Async & Sync)
# ==========================================
db_client = AsyncIOMotorClient(MONGO_URI)
db = db_client["ShilaCallApp"]
users_col, files_col, settings_col = db["users"], db["files"], db["settings"]
cats_col, pkgs_col, coupons_col = db["categories"], db["packages"], db["coupons"]

sync_client = MongoClient(MONGO_URI)
sync_db = sync_client["ShilaCallApp"]
sync_users, sync_files, sync_cats = sync_db["users"], sync_db["files"], sync_db["categories"]
sync_pkgs, sync_coupons = sync_db["packages"], sync_db["coupons"]

app = Client("shilacall_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
web = Flask(__name__)
admin_steps = {}

# ==========================================
# 3. BOT COMMANDS & AUTO AUTH
# ==========================================
@app.on_message(filters.command("start") & filters.private)
async def start_cmd(client, message):
    user_id = message.from_user.id
    
    try:
        await client.set_chat_menu_button(chat_id=user_id, menu_button=MenuButtonWebApp(text="🚀 Open App", web_app=WebAppInfo(url=f"{WEB_URL}/")))
    except: pass

    args = message.text.split()
    user = await users_col.find_one({"_id": user_id})
    config = await settings_col.find_one({"_id": "config"}) or {}
    ref_bonus = config.get("ref_coin", 10) 
    
    if not user:
        await users_col.insert_one({"_id": user_id, "name": message.from_user.first_name, "balance": 0, "is_premium": False})
        if len(args) > 1 and args[1].isdigit():
            ref_by = int(args[1])
            if ref_by != user_id and ref_bonus > 0:
                await users_col.update_one({"_id": ref_by}, {"$inc": {"balance": ref_bonus}})
                try: await app.send_message(ref_by, f"🎉 আপনার রেফারে একজন জয়েন করেছে! +{ref_bonus} Coins")
                except: pass

    btn = InlineKeyboardMarkup([[InlineKeyboardButton("🔥 Open Web App", web_app=WebAppInfo(url=f"{WEB_URL}/"))]])
    await message.reply(f"স্বাগতম! নিচে ক্লিক করে অ্যাপ ওপেন করুন।", reply_markup=btn)

@app.on_message(filters.command("new") & filters.user(ADMIN_ID))
async def cmd_new(client, message):
    admin_steps[ADMIN_ID] = {"step": "title"}
    await message.reply("১. ভিডিওর টাইটেল/নাম দিন:")

@app.on_message(filters.text & filters.user(ADMIN_ID))
async def handle_admin_text(client, message):
    step_info = admin_steps.get(ADMIN_ID)
    if not step_info: return
    
    if step_info["step"] == "title":
        admin_steps[ADMIN_ID]["title"] = message.text
        admin_steps[ADMIN_ID]["step"] = "category"
        cats = await cats_col.find().to_list(100)
        cat_names = ", ".join([c["name"] for c in cats]) if cats else "No category (Type default)"
        await message.reply(f"২. ক্যাটাগরির নাম লিখুন:\n(Available: {cat_names})")
        
    elif step_info["step"] == "category":
        admin_steps[ADMIN_ID]["category"] = message.text
        admin_steps[ADMIN_ID]["step"] = "file"
        await message.reply("৩. এবার ভিডিওটি দিন (বট সেভ করবে):")

@app.on_message(filters.video & filters.user(ADMIN_ID))
async def handle_admin_video(client, message):
    step_info = admin_steps.get(ADMIN_ID)
    if step_info and step_info["step"] == "file":
        title = step_info["title"]
        category = step_info["category"]
        file_id = message.video.file_id
        
        await files_col.insert_one({"title": title, "category": category, "file_id": file_id, "views": 0})
        del admin_steps[ADMIN_ID]
        await message.reply("✅ ভিডিও ক্যাটাগরিসহ মিনি অ্যাপে এড হয়েছে!")

@app.on_message(filters.command("addcata") & filters.user(ADMIN_ID))
async def cmd_addcata(client, message):
    try:
        cat_name = message.text.split(maxsplit=1)[1]
        await cats_col.insert_one({"name": cat_name})
        await message.reply("✅ Category Added.")
    except IndexError:
        await message.reply("❌ ফরম্যাট ভুল! লিখুন: `/addcata CategoryName`")

@app.on_message(filters.command("addcoupon") & filters.user(ADMIN_ID))
async def cmd_addcoupon(client, message):
    try:
        args = message.text.split()
        await coupons_col.insert_one({"code": args[1], "coins": int(args[2]), "used_by": []})
        await message.reply(f"✅ Coupon {args[1]} added for {args[2]} coins.")
    except Exception:
        await message.reply("❌ ফরম্যাট ভুল! লিখুন: `/addcoupon CODE 100`")

@app.on_message(filters.command("addbks") & filters.user(ADMIN_ID))
async def cmd_addbks(client, message):
    try:
        await pkgs_col.insert_one({"type": "bkash", "details": message.text.split(maxsplit=1)[1]})
        await message.reply("✅ bKash Package Added.")
    except IndexError:
        await message.reply("❌ ফরম্যাট ভুল!")

# ==========================================
# 4. HANDLE WEB APP DATA
# ==========================================
@app.on_message(filters.service)
async def web_app_handler(client, message):
    if not message.web_app_data: return
    data = message.web_app_data.data
    uid = message.from_user.id
    config = await settings_col.find_one({"_id": "config"}) or {}
    
    if data.startswith("coupon_"):
        code = data.replace("coupon_", "")
        coupon = await coupons_col.find_one({"code": code})
        if coupon and uid not in coupon.get("used_by", []):
            await users_col.update_one({"_id": uid}, {"$inc": {"balance": coupon["coins"]}})
            await coupons_col.update_one({"code": code}, {"$push": {"used_by": uid}})
            await message.reply(f"🎉 কুপন সফল! আপনি {coupon['coins']} কয়েন পেয়েছেন।")
        else:
            await message.reply("❌ কুপনটি ভুল বা আপনি আগে ব্যবহার করেছেন।")
        return
        
    if data.startswith("buy_"):
        grp = config.get("admin_group")
        if grp: await app.send_message(grp, f"🚨 New Order! ID: `{uid}`, Pkg: {data}")
        await message.reply("✅ আপনার প্যাকেজ রিকোয়েস্ট এডমিনের কাছে গেছে।")
        return

    await files_col.update_one({"file_id": data}, {"$inc": {"views": 1}})
    await client.send_cached_media(chat_id=uid, file_id=data)

# ==========================================
# 5. FRONTEND TEMPLATE
# ==========================================
HTML_TEMPLATE = """



    
    
    Viral Video App
    
    


```

**Viral Video**

🪙 0

All

{% for cat in cats %}

{{ cat.name }}

{% endfor %}

{% for file in files %}

▶ Play

**{{ file.title }}**



👁 {{ file.views }} views • Category: {{ file.category }}

{% else %}

কোনো ভিডিও নেই।

{% endfor %}

### Buy Packages

{% for pkg in bkash_pkgs %}

**{{ pkg.details }}**

Buy with bKash

{% endfor %}

আপনার ব্যালেন্স

## 🪙 0

ID: Loading...

🌙 Dark Mode (ডার্ক থিম)

**🎟 কুপন রিডিম করুন**

Redeem

🏠



Home

💎



Buy Coins

⚙️



Settings

"""

# Web Routes

@web.route('/')
def home():
files = list(sync_files.find().sort("_id", -1))
cats = list(sync_cats.find())
bkash_pkgs = list(sync_pkgs.find({"type": "bkash"}))
return render_template_string(HTML_TEMPLATE, files=files, cats=cats, bkash_pkgs=bkash_pkgs)

@web.route('/api/user/')
def get_user(uid):
user = sync_users.find_one({"_id": uid}) or {"balance": 0}
return {"balance": user.get("balance", 0)}

# ==========================================

# 6. RUN

# ==========================================

def run_flask():
web.run(host="0.0.0.0", port=PORT)

if **name** == "**main**":
threading.Thread(target=run_flask, daemon=True).start()
app.run()

```

```
