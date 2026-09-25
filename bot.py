import os
import asyncio
import threading
import time

# ==========================================
# 🔴 RENDER ERROR FIX (Event Loop Fix)
# সার্ভার যেন ক্র্যাশ না করে তাই এই কোডটি শুরুতে দিতে হবে
# ==========================================
try:
    loop = asyncio.get_event_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

# এবার লাইব্রেরিগুলো ইমপোর্ট করা হলো
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from flask import Flask, render_template_string
from motor.motor_asyncio import AsyncIOMotorClient

# ==========================================
# 1. CONFIGURATION (আপনার দেওয়া ইনফো)
# ==========================================
API_ID = int(os.environ.get("API_ID", 29904834))
API_HASH = os.environ.get("API_HASH", "8b4fd9ef578af114502feeafa2d31938")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8206083172:AAHP9raleY3l2R2HBTGSVCdpcLQvgn960Mw")
MONGO_URI = os.environ.get("MONGO_URI", "mongodb+srv://akash:akash@cluster0.etisrpx.mongodb.net/?appName=Cluster0")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 7120801813))
WEB_URL = os.environ.get("WEB_URL", "https://amiking.onrender.com") # আপনার রেন্ডার লিংক

# ==========================================
# 2. DATABASE SETUP
# ==========================================
db_client = AsyncIOMotorClient(MONGO_URI)
db = db_client["ShilaCallApp"]
users_col = db["users"]
files_col = db["files"]
settings_col = db["settings"]
links_col = db["ad_links"]
cats_col = db["categories"]

# ==========================================
# 3. BOT & WEB SERVER INIT
# ==========================================
app = Client("shilacall_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
web = Flask(__name__)
admin_steps = {}

# ==========================================
# 4. BOT COMMANDS (USER & ALL ADMIN COMMANDS)
# ==========================================

@app.on_message(filters.command("start") & filters.private)
async def start_cmd(client, message):
    user_id = message.from_user.id
    
    # Save User to Database
    user = await users_col.find_one({"_id": user_id})
    if not user:
        await users_col.insert_one({
            "_id": user_id,
            "name": message.from_user.first_name,
            "username": message.from_user.username,
            "balance": 0,
            "is_premium": False
        })

    btn = InlineKeyboardMarkup([[InlineKeyboardButton("🔥 Open Shila Call App", web_app=WebAppInfo(url=f"{WEB_URL}/?uid={user_id}"))]])
    await message.reply(f"হ্যালো {message.from_user.first_name}! আমাদের মিনি অ্যাপে স্বাগতম।", reply_markup=btn)

# --- 1. /new (ফাইল এড করা) ---
@app.on_message(filters.command("new") & filters.user(ADMIN_ID))
async def cmd_new(client, message):
    admin_steps[ADMIN_ID] = {"step": "name"}
    await message.reply("ফাইলের নাম দিন:")

@app.on_message(filters.text & filters.user(ADMIN_ID))
async def handle_admin_text(client, message):
    step_info = admin_steps.get(ADMIN_ID)
    if not step_info:
        return

    if step_info["step"] == "name":
        admin_steps[ADMIN_ID]["name"] = message.text
        admin_steps[ADMIN_ID]["step"] = "file"
        await message.reply("এবার ভিডিও ফাইলটি দিন (বট অটো এড করে নিবে):")

@app.on_message(filters.video & filters.user(ADMIN_ID))
async def handle_admin_video(client, message):
    step_info = admin_steps.get(ADMIN_ID)
    if step_info and step_info["step"] == "file":
        msg = await message.reply("ফাইল প্রসেস হচ্ছে...")
        file_id = message.video.file_id
        file_name = step_info["name"]
        
        await files_col.insert_one({"name": file_name, "file_id": file_id, "views": 0})
        del admin_steps[ADMIN_ID]
        await msg.edit("✅ ফাইল মিনি অ্যাপের হোমপেজে এড হয়ে গেছে!")

# --- 2. /adson & /adsoff ---
@app.on_message(filters.command("adson") & filters.user(ADMIN_ID))
async def cmd_adson(client, message):
    await settings_col.update_one({"_id": "config"}, {"$set": {"ads": True}}, upsert=True)
    await message.reply("✅ এডস চালু করা হয়েছে।")

@app.on_message(filters.command("adsoff") & filters.user(ADMIN_ID))
async def cmd_adsoff(client, message):
    await settings_col.update_one({"_id": "config"}, {"$set": {"ads": False}}, upsert=True)
    await message.reply("❌ এডস বন্ধ করা হয়েছে।")

# --- 3. /adpremiun & /delpremiun ---
@app.on_message(filters.command("adpremiun") & filters.user(ADMIN_ID))
async def cmd_adpremium(client, message):
    try:
        args = message.text.split()
        uid = int(args[1])
        duration = args[2] if len(args) > 2 else "Lifetime"
        await users_col.update_one({"_id": uid}, {"$set": {"is_premium": True, "plan": duration}})
        await message.reply(f"✅ User {uid} কে {duration} এর জন্য প্রিমিয়াম দেওয়া হলো।")
    except:
        await message.reply("Format: /adpremiun user_id 1month")

@app.on_message(filters.command("delpremiun") & filters.user(ADMIN_ID))
async def cmd_delpremium(client, message):
    try:
        uid = int(message.text.split()[1])
        await users_col.update_one({"_id": uid}, {"$set": {"is_premium": False}})
        await message.reply(f"❌ User {uid} আন-প্রিমিয়াম করা হলো।")
    except:
        await message.reply("Format: /delpremiun user_id")

# --- 4. /addlink & /delelink ---
@app.on_message(filters.command("addlink") & filters.user(ADMIN_ID))
async def cmd_addlink(client, message):
    try:
        link = message.text.split(maxsplit=1)[1]
        await links_col.insert_one({"link": link})
        await message.reply("✅ এড লিংক এড করা হয়েছে।")
    except:
        await message.reply("Format: /addlink https://example.com")

@app.on_message(filters.command("delelink") & filters.user(ADMIN_ID))
async def cmd_delelink(client, message):
    links = await links_col.find().to_list(100)
    if not links:
        return await message.reply("কোনো লিংক নেই।")
    buttons = [[InlineKeyboardButton(f"❌ {l['link'][:15]}...", callback_data=f"dellink_{l['_id']}")] for l in links]
    await message.reply("যে লিংক ডিলেট করবেন ক্লিক করুন:", reply_markup=InlineKeyboardMarkup(buttons))

# --- 5. /addcata & /delcata ---
@app.on_message(filters.command("addcata") & filters.user(ADMIN_ID))
async def cmd_addcata(client, message):
    try:
        cata = message.text.split(maxsplit=1)[1]
        await cats_col.insert_one({"name": cata})
        await message.reply("✅ ক্যাটাগরি এড করা হয়েছে।")
    except:
        await message.reply("Format: /addcata CategoryName")

@app.on_message(filters.command("delcata") & filters.user(ADMIN_ID))
async def cmd_delcata(client, message):
    cats = await cats_col.find().to_list(100)
    if not cats:
        return await message.reply("কোনো ক্যাটাগরি নেই।")
    buttons = [[InlineKeyboardButton(f"❌ {c['name']}", callback_data=f"delcat_{c['_id']}")] for c in cats]
    await message.reply("ক্যাটাগরি ডিলেট করুন:", reply_markup=InlineKeyboardMarkup(buttons))

# --- 6. Handle File Request from WebApp ---
@app.on_message(filters.service)
async def web_app_data_handler(client, message):
    if message.web_app_data:
        file_id = message.web_app_data.data
        uid = message.from_user.id
        
        # Check Premium & Ads logic
        user = await users_col.find_one({"_id": uid})
        config = await settings_col.find_one({"_id": "config"})
        ads_on = config.get("ads", False) if config else False

        if ads_on and not (user and user.get("is_premium", False)):
            await message.reply("বিজ্ঞাপন... (Premium কিনলে এড আসবে না)")
            await asyncio.sleep(2) # Fake ad delay
            
        await client.send_cached_media(chat_id=uid, file_id=file_id)

# ==========================================
# 5. MASSIVE WEB APP FRONTEND (HTML + CSS)
# ==========================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Shila Call</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        body { background-color: #0f1015; color: white; font-family: sans-serif; margin: 0; padding-bottom: 70px; }
        
        /* Header */
        .header { display: flex; justify-content: space-between; padding: 15px; background: #1c1c1c; align-items: center; border-bottom: 1px solid #333;}
        .coin-box { background: #ffcc00; color: black; padding: 5px 15px; border-radius: 20px; font-weight: bold; }
        
        /* Navigation System */
        .page { display: none; padding: 15px; }
        .page.active { display: block; }
        
        /* Home Page Cards */
        .card { background: #1c1c24; border-radius: 12px; margin-bottom: 20px; overflow: hidden; position: relative; }
        .card img { width: 100%; height: 200px; object-fit: cover; }
        .premium-tag { position: absolute; top: 10px; left: 10px; background: #b026ff; padding: 4px 10px; border-radius: 6px; font-size: 11px; font-weight: bold; }
        .card-title { padding: 12px; font-size: 14px; font-weight: bold; }
        .card-views { color: gray; font-size: 12px; margin-top: 5px; }
        .play-btn { position: absolute; bottom: 15px; right: 15px; background: #ff2a5f; width: 40px; height: 40px; border-radius: 50%; display: flex; justify-content: center; align-items: center; }

        /* Settings Page */
        .balance-card { background: linear-gradient(45deg, #ff007f, #7a00ff); border-radius: 15px; padding: 20px; text-align: center; margin-bottom: 20px; box-shadow: 0 4px 15px rgba(0,0,0,0.3); }
        .balance-card h2 { margin: 0; font-size: 30px; }
        .balance-card p { margin: 5px 0 0 0; font-size: 12px; opacity: 0.8; }
        .menu-item { background: linear-gradient(90deg, #3a2a50, #1f1b2e); margin-bottom: 15px; padding: 15px; border-radius: 10px; display: flex; align-items: center; border: 1px solid #4a3b69;}
        .menu-item span { margin-left: 15px; font-size: 14px; font-weight: bold;}
        .menu-item small { display: block; font-size: 10px; color: gray; font-weight: normal; margin-top:3px;}

        /* Buy Coins Page */
        .payment-methods { display: flex; gap: 10px; margin-bottom: 20px; }
        .pay-btn { flex: 1; text-align: center; padding: 12px; background: #2a1b38; border-radius: 8px; font-weight: bold; border: 1px solid #ff007f; color: #ff007f;}
        .pay-btn.active { background: #ff007f; color: white; }
        .package { background: #1c1c24; border: 1px solid #444; border-radius: 12px; padding: 15px; margin-bottom: 15px; text-align: center; position: relative;}
        .most-popular { position: absolute; top: -10px; left: 50%; transform: translateX(-50%); background: #ffcc00; color: black; font-size: 10px; padding: 2px 10px; border-radius: 10px; font-weight:bold;}
        .pkg-price { font-size: 24px; font-weight: bold; margin: 10px 0; }
        .pkg-buy-btn { background: linear-gradient(90deg, #ff007f, #00d4ff); padding: 12px; border-radius: 25px; font-weight: bold; cursor: pointer; }

        /* Bottom Nav */
        .bottom-nav { position: fixed; bottom: 0; left:0; width: 100%; background: rgba(28, 28, 28, 0.95); backdrop-filter: blur(10px); display: flex; justify-content: space-around; padding: 12px 0; border-top: 1px solid #333; z-index: 1000;}
        .nav-item { text-align: center; font-size: 11px; color: gray; cursor: pointer; }
        .nav-item.active { color: #ff2a5f; }
        .nav-icon { font-size: 20px; margin-bottom: 3px; display: block;}
    </style>
</head>
<body>

    <div class="header">
        <b>Viral <span style="background: #ff2a5f; padding: 2px 5px; border-radius: 5px;">Video</span></b>
        <div class="coin-box">🪙 0</div>
    </div>

    <!-- HOME PAGE (আপনার স্ক্রিনশট ১ ও ২) -->
    <div id="page-home" class="page active">
        <div class="card" onclick="getFile('আপনার_ফাইল_আইডি_এখানে_বসবে')">
            <div class="premium-tag">💎 PREMIUM</div>
            <img src="https://images.unsplash.com/photo-1516259762381-22954d7d3ad2?w=500" alt="Thumb">
            <div class="card-title">নিউ ভাইরাল ভিডিও সেরা সেরা ভিডিও <div class="card-views">👁 137 views</div></div>
            <div class="play-btn">🔍</div>
        </div>
        <div class="card" onclick="getFile('আপনার_ফাইল_আইডি_এখানে_বসবে')">
            <div class="premium-tag" style="background:#00d4ff; color:black;">FREE</div>
            <img src="https://images.unsplash.com/photo-1529626455594-4ff0802cfb7e?w=500" alt="Thumb">
            <div class="card-title">ওয়াত স্বামী স্ত্রীর নিউ ভাইরাল ভিডিও... <div class="card-views">👁 231 views</div></div>
            <div class="play-btn">🔍</div>
        </div>
    </div>

    <!-- BUY COINS PAGE (আপনার স্ক্রিনশট ৪ ও ৫) -->
    <div id="page-premium" class="page">
        <h3 style="text-align: center; color: #ff007f;">কয়েন কিনুন (Buy Coins)</h3>
        <div class="payment-methods">
            <div class="pay-btn active">bKash/Nagad</div>
            <div class="pay-btn">Instant (USD)</div>
        </div>

        <div class="package">
            <div class="most-popular">Most Popular</div>
            <div class="pkg-price">৳120</div>
            <div style="color: gray; font-size: 12px; margin-bottom: 15px;">🪙 1000 Coins + 10 Bonus</div>
            <div class="pkg-buy-btn">কিনুন (Buy)</div>
        </div>
        
        <div class="package">
            <div class="most-popular">Most Popular</div>
            <div class="pkg-price">৳240</div>
            <div style="color: gray; font-size: 12px; margin-bottom: 15px;">🪙 2000 Coins + 30 Bonus</div>
            <div class="pkg-buy-btn">কিনুন (Buy)</div>
        </div>
    </div>

    <!-- SETTINGS PAGE (আপনার স্ক্রিনশট ৩, ৬ ও ৭) -->
    <div id="page-settings" class="page">
        <div class="balance-card">
            <p>আপনার ব্যালেন্স (YOUR BALANCE)</p>
            <h2>🪙 0</h2>
            <p>ID: 7120801813</p>
        </div>

        <div class="menu-item" onclick="switchPage('premium')">
            🪙 <span>কয়েন কিনুন (Buy Coins)<small>প্যাকেজ বেছে নিয়ে পেমেন্ট করুন</small></span>
        </div>
        <div class="menu-item">
            🎟 <span>কুপন কোড (Coupon Code)<small>কোড রিডিম করে ফ্রি কয়েন নিন</small></span>
        </div>
        <div class="menu-item">
            🎁 <span>বন্ধুকে শেয়ার করুন (Share Friend)<small>ইনভাইট করে ফ্রি কয়েন জিতুন</small></span>
        </div>
    </div>

    <!-- NAVIGATION (নিচের মেনুবার) -->
    <div class="bottom-nav">
        <div class="nav-item active" onclick="switchPage('home')"><span class="nav-icon">🏠</span>Home</div>
        <div class="nav-item" onclick="switchPage('premium')"><span class="nav-icon">💎</span>Premium</div>
        <div class="nav-item" onclick="switchPage('settings')"><span class="nav-icon">⚙️</span>Settings</div>
    </div>

    <script>
        let tg = window.Telegram.WebApp;
        tg.expand(); // Full screen

        // Page Switch Logic
        function switchPage(pageId) {
            document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
            document.getElementById('page-' + pageId).classList.add('active');
            
            document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
            event.currentTarget.classList.add('active');
        }

        // Send File Request to Bot
        function getFile(fileId) {
            tg.sendData(fileId);
        }
    </script>
</body>
</html>
"""

@web.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

# ==========================================
# 6. RUN BOTH BOT & FLASK TOGETHER
# ==========================================
def run_flask():
    web.run(host="0.0.0.0", port=8080)

if __name__ == "__main__":
    print("Starting Web Server...")
    threading.Thread(target=run_flask, daemon=True).start()
    
    print("Starting Telegram Bot...")
    app.run()
