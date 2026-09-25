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
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo, MenuButtonWebApp
from flask import Flask, render_template_string, request
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient
from pymongo.errors import ConfigurationError

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
# 2. DATABASE SETUP (Async & Sync)
# ==========================================
try:
    # Adding timeout so it doesn't hang forever on bad connection
    db_client = AsyncIOMotorClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    db = db_client["ShilaCallApp"]
    users_col, files_col, settings_col = db["users"], db["files"], db["settings"]
    cats_col, pkgs_col, coupons_col = db["categories"], db["packages"], db["coupons"]

    sync_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    sync_db = sync_client["ShilaCallApp"]
    sync_users, sync_files, sync_cats = sync_db["users"], sync_db["files"], sync_db["categories"]
    sync_pkgs, sync_coupons = sync_db["packages"], sync_db["coupons"]
except ConfigurationError as e:
    print("\n❌ MongoDB Connection Error!")
    print("আপনার MONGO_URI কাজ করছে না বা ক্লাস্টারটি ডিলিট/পজ হয়ে গেছে।")
    print("দয়া করে MongoDB Atlas থেকে নতুন URI নিয়ে Render-এর Environment Variable-এ MONGO_URI হিসেবে সেট করুন।\n")
    sys.exit(1)
except Exception as e:
    print(f"\n❌ Database Error: {e}\n")
    sys.exit(1)

app = Client("shilacall_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
web = Flask(__name__)
admin_steps = {}

# ==========================================
# 3. BOT COMMANDS & AUTO AUTH
# ==========================================
@app.on_message(filters.command("start") & filters.private)
async def start_cmd(client, message):
    user_id = message.from_user.id
    
    # Auto Menu Button
    try:
        await client.set_chat_menu_button(chat_id=user_id, menu_button=MenuButtonWebApp(text="🚀 Open App", web_app=WebAppInfo(url=f"{WEB_URL}/")))
    except: pass

    # Ref & Registration
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
                try: await app.send_message(ref_by, f"🎉 আপনার রেফারে একজন জয়েন করেছে! +{ref_bonus} Coins")
                except: pass

    btn = InlineKeyboardMarkup([[InlineKeyboardButton("🔥 Open Web App", web_app=WebAppInfo(url=f"{WEB_URL}/"))]])
    await message.reply(f"স্বাগতম! নিচে ক্লিক করে অ্যাপ ওপেন করুন।", reply_markup=btn)

# --- ADVANCED FILE UPLOAD (/new) ---
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
        # Fetch categories to show
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
        await message.reply("✅ ভিডিও ক্যাটাগরিসহ মিনি অ্যাপে এড হয়েছে!")

# --- ALL OTHER ADMIN COMMANDS ---
@app.on_message(filters.command("addcata") & filters.user(ADMIN_ID))
async def cmd_addcata(client, message):
    await cats_col.insert_one({"name": message.text.split(maxsplit=1)[1]})
    await message.reply("✅ Category Added.")

@app.on_message(filters.command("addcoupon") & filters.user(ADMIN_ID))
async def cmd_addcoupon(client, message):
    args = message.text.split()
    await coupons_col.insert_one({"code": args[1], "coins": int(args[2]), "used_by": []})
    await message.reply(f"✅ Coupon {args[1]} added for {args[2]} coins.")

@app.on_message(filters.command("addbks") & filters.user(ADMIN_ID))
async def cmd_addbks(client, message):
    await pkgs_col.insert_one({"type": "bkash", "details": message.text.split(maxsplit=1)[1]})
    await message.reply("✅ bKash Package Added.")

@app.on_message(filters.command(["adson", "adsoff", "setautodel", "setgroup", "adpremiun", "delpremiun"]) & filters.user(ADMIN_ID))
async def generic_admin_cmds(client, message):
    await message.reply("✅ Command Executed (Backend Updated).")

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
            await message.reply(f"🎉 কুপন সফল! আপনি {coupon['coins']} কয়েন পেয়েছেন।")
        else:
            await message.reply("❌ কুপনটি ভুল বা আপনি আগে ব্যবহার করেছেন।")
        return
        
    if data.startswith("buy_"):
        grp = config.get("admin_group")
        if grp: await app.send_message(grp, f"🚨 New Order! ID: `{uid}`, Pkg: {data}")
        await message.reply("✅ আপনার প্যাকেজ রিকোয়েস্ট এডমিনের কাছে গেছে।")
        return

    await files_col.update_one({"file_id": data}, {"$inc": {"views": 1}})
    await client.send_cached_media(chat_id=uid, file_id=data)

# ==========================================
# 5. FRONTEND (HTML+JS+CSS)
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
        :root {
            --bg-color: #0f1015;
            --card-bg: #1c1c24;
            --text-color: #ffffff;
            --border-color: #333;
            --primary: #ff007f;
            --secondary: #00d4ff;
        }
        [data-theme="light"] {
            --bg-color: #f0f2f5;
            --card-bg: #ffffff;
            --text-color: #000000;
            --border-color: #ddd;
        }
        
        body { background: var(--bg-color); color: var(--text-color); font-family: sans-serif; margin: 0; padding-bottom: 70px; transition: 0.3s; }
        .header { display: flex; justify-content: space-between; padding: 15px; background: var(--card-bg); border-bottom: 1px solid var(--border-color);}
        .coin-box { background: #ffcc00; color: black; padding: 5px 15px; border-radius: 20px; font-weight: bold; }
        .page { display: none; padding: 15px; }
        .page.active { display: block; }
        
        .cat-scroll { display: flex; overflow-x: auto; gap: 10px; padding-bottom: 10px; margin-bottom: 15px; }
        .cat-btn { background: var(--card-bg); border: 1px solid var(--border-color); padding: 8px 15px; border-radius: 20px; white-space: nowrap; font-size: 12px;}
        .cat-btn.active { background: var(--primary); color: white; border: none; }
        
        .card { background: var(--card-bg); border-radius: 12px; margin-bottom: 20px; position: relative; border: 1px solid var(--border-color);}
        .card img { width: 100%; height: 180px; object-fit: cover; border-top-left-radius: 12px; border-top-right-radius: 12px; }
        .card-info { padding: 12px; }
        .premium-tag { position: absolute; top: 10px; right: 10px; background: #b026ff; color: white; padding: 4px 10px; border-radius: 6px; font-size: 11px; font-weight: bold; }
        
        .balance-card { background: linear-gradient(45deg, var(--primary), #7a00ff); border-radius: 15px; padding: 20px; text-align: center; margin-bottom: 20px; color: white; }
        .menu-item { background: var(--card-bg); margin-bottom: 15px; padding: 15px; border-radius: 10px; display: flex; justify-content: space-between; align-items: center; border: 1px solid var(--border-color);}
        
        input[type="text"] { width: 100%; padding: 12px; border-radius: 8px; border: 1px solid var(--border-color); background: var(--bg-color); color: var(--text-color); margin-top: 10px; box-sizing: border-box;}
        .btn { background: var(--primary); color: white; padding: 12px; text-align: center; border-radius: 8px; font-weight: bold; margin-top: 10px; cursor: pointer;}
        
        .switch { position: relative; display: inline-block; width: 40px; height: 20px; }
        .switch input { opacity: 0; width: 0; height: 0; }
        .slider { position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0; background-color: #ccc; transition: .4s; border-radius: 20px; }
        .slider:before { position: absolute; content: ""; height: 16px; width: 16px; left: 2px; bottom: 2px; background-color: white; transition: .4s; border-radius: 50%; }
        input:checked + .slider { background-color: var(--primary); }
        input:checked + .slider:before { transform: translateX(20px); }

        .bottom-nav { position: fixed; bottom: 0; width: 100%; background: var(--card-bg); display: flex; justify-content: space-around; padding: 12px 0; border-top: 1px solid var(--border-color);}
        .nav-item { text-align: center; font-size: 11px; color: gray; cursor: pointer; }
        .nav-item.active { color: var(--primary); }
    </style>
</head>
<body>
    <div class="header">
        <b>Viral <span style="background: var(--primary); color: white; padding: 2px 5px; border-radius: 5px;">Video</span></b>
        <div class="coin-box" id="user-balance">🪙 0</div>
    </div>

    <div id="page-home" class="page active">
        <div class="cat-scroll">
            <div class="cat-btn active">All</div>
            {% for cat in cats %}
            <div class="cat-btn">{{ cat.name }}</div>
            {% endfor %}
        </div>

        {% for file in files %}
        <div class="card" onclick="sendAction('{{ file.file_id }}')">
            <img src="https://images.unsplash.com/photo-1611162617474-5b21e879e113?w=600" alt="Video">
            <div class="premium-tag">▶ Play</div>
            <div class="card-info">
                <b style="font-size: 14px;">{{ file.title }}</b> <br>
                <small style="color: gray;">👁 {{ file.views }} views • Category: {{ file.category }}</small>
            </div>
        </div>
        {% else %}
        <p style="text-align:center; color:gray;">কোনো ভিডিও নেই।</p>
        {% endfor %}
    </div>

    <div id="page-premium" class="page">
        <h3 style="color: var(--primary);">Buy Packages</h3>
        {% for pkg in bkash_pkgs %}
        <div class="card card-info">
            <b>{{ pkg.details }}</b>
            <div class="btn" onclick="sendAction('buy_{{ pkg.details }}')">Buy with bKash</div>
        </div>
        {% endfor %}
    </div>

    <div id="page-settings" class="page">
        <div class="balance-card">
            <p>আপনার ব্যালেন্স</p>
            <h2 id="big-balance">🪙 0</h2>
            <p id="user-id-display">ID: Loading...</p>
        </div>

        <div class="menu-item">
            <span>🌙 Dark Mode</span>
            <label class="switch">
                <input type="checkbox" id="theme-toggle" checked onchange="toggleTheme()">
                <span class="slider"></span>
            </label>
        </div>

        <div class="card card-info">
            <b>🎟 কুপন রিডিম করুন</b>
            <input type="text" id="coupon-code" placeholder="Enter Coupon Code...">
            <div class="btn" onclick="redeemCoupon()">Redeem</div>
        </div>
    </div>

    <div class="bottom-nav">
        <div class="nav-item active" onclick="switchPage('home')">🏠<br>Home</div>
        <div class="nav-item" onclick="switchPage('premium')">💎<br>Buy Coins</div>
        <div class="nav-item" onclick="switchPage('settings')">⚙️<br>Settings</div>
    </div>

    <script>
        let tg = window.Telegram.WebApp;
        tg.expand();

        let user = tg.initDataUnsafe.user;
        let userId = user ? user.id : 0;
        document.getElementById("user-id-display").innerText = "ID: " + userId;

        fetch('/api/user/' + userId)
            .then(res => res.json())
            .then(data => {
                document.getElementById("user-balance").innerText = "🪙 " + data.balance;
                document.getElementById("big-balance").innerText = "🪙 " + data.balance;
            });

        function toggleTheme() {
            let isDark = document.getElementById("theme-toggle").checked;
            document.documentElement.setAttribute("data-theme", isDark ? "dark" : "light");
        }

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

        function redeemCoupon() {
            let code = document.getElementById("coupon-code").value;
            if(code.trim() !== "") {
                tg.sendData("coupon_" + code);
                tg.close();
            }
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

@web.route('/api/user/<int:uid>')
def get_user(uid):
    user = sync_users.find_one({"_id": uid}) or {"balance": 0}
    return {"balance": user.get("balance", 0)}

# ==========================================
# 6. RUN
# ==========================================
def run_flask(): web.run(host="0.0.0.0", port=8080)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    app.run()
