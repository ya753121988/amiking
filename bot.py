import asyncio

# ================= Python 3.10+ Pyrogram Crash Fix =================
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
# ===================================================================

import os
import random
from datetime import datetime
from dateutil.relativedelta import relativedelta
from aiohttp import web
from pyrogram import Client, filters, idle
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, WebAppInfo
from pyrogram.errors import UserNotParticipant
from motor.motor_asyncio import AsyncIOMotorClient

# ================= কনফিগারেশন =================
API_ID = int(os.environ.get("API_ID", 29904834))
API_HASH = os.environ.get("API_HASH", "8b4fd9ef578af114502feeafa2d31938")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8206083172:AAHP9raleY3l2R2HBTGSVCdpcLQvgn960Mw")
MONGO_URI = os.environ.get("MONGO_URI", "mongodb+srv://akash:akash@cluster0.etisrpx.mongodb.net/?appName=Cluster0")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 7120801813))
PORT = int(os.environ.get("PORT", 8080))

# ⚠️ রেন্ডারে ডিপ্লয় করার পর আপনার সাইটের লিংক এখানে বসাবেন (যেমন: https://your-app.onrender.com)
WEB_URL = os.environ.get("WEB_URL", "https://amiking.onrender.com")

# ================= ডাটাবেস সেটআপ =================
mongo_client = AsyncIOMotorClient(MONGO_URI)
db = mongo_client["AdvancedBotDB"]
users_db = db["users"]
files_db = db["files"]
settings_db = db["settings"]
redeem_db = db["redeems"]
packages_db = db["packages"]

app = Client("AdvancedFileStoreBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
upload_state = {}

# ================= হেল্পার ফাংশন =================
async def init_db():
    config = await settings_db.find_one({"_id": "bot_config"})
    if not config:
        await settings_db.insert_one({
            "_id": "bot_config",
            "fsub_channels": [],
            "notice": "স্বাগতম আমাদের ফ্যামিলিতে!",
            "forward_protect": True,
            "refer_coin": 10,
            "spin_values": [1, 2, 5, 0, 10],
            "admin_contact": f"tg://user?id={ADMIN_ID}"
        })

async def check_fsub(client, user_id):
    config = await settings_db.find_one({"_id": "bot_config"})
    channels = config.get("fsub_channels", [])
    not_joined = []
    
    for ch in channels:
        try:
            await client.get_chat_member(ch, user_id)
        except UserNotParticipant:
            not_joined.append(ch)
        except Exception:
            pass # যদি বট চ্যানেলে অ্যাডমিন না থাকে
            
    return not_joined

async def check_prem(user_data):
    if user_data and user_data.get("is_premium") and user_data.get("premium_expiry"):
        if datetime.now() > user_data["premium_expiry"]:
            await users_db.update_one({"user_id": user_data["user_id"]}, {"$set": {"is_premium": False, "premium_expiry": None}})
            return False
        return True
    return False

# ================= ইউজার কমান্ডস =================

@app.on_message(filters.command("start") & filters.private)
async def start_cmd(client, message: Message):
    user_id = message.from_user.id
    user_name = message.from_user.first_name
    cmd_args = message.command

    # ইউজার ডাটাবেস চেক ও সেভ
    user_data = await users_db.find_one({"user_id": user_id})
    if not user_data:
        config = await settings_db.find_one({"_id": "bot_config"})
        ref_coin = config.get("refer_coin", 10)
        
        # রেফারেল সিস্টেম
        if len(cmd_args) > 1 and cmd_args[1].isdigit():
            referrer_id = int(cmd_args[1])
            if referrer_id != user_id:
                await users_db.update_one({"user_id": referrer_id}, {"$inc": {"coins": ref_coin}})
                try:
                    await client.send_message(referrer_id, f"🎉 নতুন রেফার! আপনি {ref_coin} Coins পেয়েছেন।")
                except: pass

        await users_db.insert_one({"user_id": user_id, "name": user_name, "coins": 0, "is_premium": False, "premium_expiry": None, "is_blocked": False, "last_spin": None})
        user_data = await users_db.find_one({"user_id": user_id})

    if user_data.get("is_blocked"):
        return await message.reply_text("🚫 আপনি এই বট থেকে ব্লকড!")

    # Force Sub Check
    not_joined = await check_fsub(client, user_id)
    if not_joined:
        buttons = []
        for ch in not_joined:
            try:
                chat = await client.get_chat(ch)
                buttons.append([InlineKeyboardButton(f"📢 জয়েন {chat.title}", url=chat.invite_link or f"https://t.me/{chat.username}")])
            except: pass
        buttons.append([InlineKeyboardButton("✅ জয়েন করেছি", callback_data="check_sub")])
        return await message.reply_text("⚠️ বটটি ব্যবহার করতে প্রথমে আমাদের চ্যানেলগুলোতে জয়েন করুন!", reply_markup=InlineKeyboardMarkup(buttons))

    # ওয়েবসাইট থেকে ফাইল কেনার প্রসেস (Deep Linking)
    if len(cmd_args) > 1 and cmd_args[1].startswith("get_"):
        file_name = cmd_args[1].replace("get_", "").replace("_", " ")
        file_data = await files_db.find_one({"file_name": file_name})
        
        if file_data:
            if user_data["coins"] >= file_data["price"]:
                await users_db.update_one({"user_id": user_id}, {"$inc": {"coins": -file_data["price"]}})
                config = await settings_db.find_one({"_id": "bot_config"})
                protect = config.get("forward_protect", True)
                
                await message.reply_text("✅ পেমেন্ট সফল! আপনার ফাইল নিচে দেওয়া হলো:")
                await client.send_cached_media(
                    chat_id=user_id, 
                    file_id=file_data["file_id"], 
                    protect_content=protect
                )
                return
            else:
                return await message.reply_text("❌ আপনার পর্যাপ্ত কয়েন নেই!")

    # নরমাল স্টার্ট মেনু
    is_prem = await check_prem(user_data)
    status_text = "👑 Premium" if is_prem else "👤 Regular"
    coins = user_data.get('coins', 0)
    config = await settings_db.find_one({"_id": "bot_config"})
    admin_contact = config.get("admin_contact", f"tg://user?id={ADMIN_ID}")

    text = f"👋 স্বাগতম **{user_name}**!\n\n"
    text += f"🔖 **ইউজার আইডি:** `{user_id}`\n"
    text += f"🔰 **স্ট্যাটাস:** {status_text}\n"
    text += f"💰 **ব্যালেন্স:** {coins} Coins\n\n"
    text += f"🔗 **রেফার লিংক:** `https://t.me/{client.me.username}?start={user_id}`\n"

    btn = InlineKeyboardMarkup([
        [InlineKeyboardButton("🌐 মিনি অ্যাপ ওপেন করুন", web_app=WebAppInfo(url=f"{WEB_URL}/app?uid={user_id}"))],
        [InlineKeyboardButton("📞 অ্যাডমিন সাপোর্ট", url=admin_contact)]
    ])
    await message.reply_text(text, reply_markup=btn)

@app.on_callback_query(filters.regex("check_sub"))
async def check_sub_callback(client, callback_query: CallbackQuery):
    await callback_query.message.delete()
    await start_cmd(client, callback_query.message)

# ================= অ্যাডমিন কমান্ডস =================

@app.on_message(filters.command("new") & filters.user(ADMIN_ID))
async def new_file_cmd(client, message: Message):
    try:
        name = message.text.split(" ", 2)[1]
        price = int(message.text.split(" ", 2)[2])
        upload_state[ADMIN_ID] = {"step": "wait_file", "name": name, "price": price}
        await message.reply_text(f"📂 **{name}** এর জন্য ভিডিও/ফাইল সেন্ড করুন:")
    except:
        await message.reply_text("⚠️ ফরম্যাট ভুল! ব্যবহার করুন: `/new FileName 20`")

@app.on_message(filters.private & filters.user(ADMIN_ID) & filters.media & ~filters.command(["new"]))
async def receive_file(client, message: Message):
    if upload_state.get(ADMIN_ID, {}).get("step") == "wait_file":
        data = upload_state[ADMIN_ID]
        file_id = message.video.file_id if message.video else message.document.file_id
        
        await files_db.insert_one({"file_name": data["name"], "file_id": file_id, "price": data["price"]})
        del upload_state[ADMIN_ID]
        await message.reply_text(f"✅ ফাইল সাইটে আপলোড হয়েছে!\nনাম: {data['name']} | প্রাইস: {data['price']}")

@app.on_message(filters.command("delfile") & filters.user(ADMIN_ID))
async def del_file(client, message: Message):
    name = message.text.split(None, 1)[1]
    res = await files_db.delete_one({"file_name": name})
    await message.reply_text("✅ ফাইল ডিলিট হয়েছে!" if res.deleted_count > 0 else "❌ পাওয়া যায়নি!")

@app.on_message(filters.command("delall") & filters.user(ADMIN_ID))
async def del_all(client, message: Message):
    await files_db.delete_many({})
    await message.reply_text("🗑️ সাইট থেকে সব ফাইল ডিলিট করা হয়েছে!")

@app.on_message(filters.command("channel") & filters.user(ADMIN_ID))
async def add_channel(client, message: Message):
    ch_id = message.command[1]
    await settings_db.update_one({"_id": "bot_config"}, {"$addToSet": {"fsub_channels": ch_id}})
    await message.reply_text(f"✅ চ্যানেল {ch_id} Force Sub এ যুক্ত হয়েছে!")

@app.on_message(filters.command("notice") & filters.user(ADMIN_ID))
async def set_notice(client, message: Message):
    notice = message.text.split(None, 1)[1]
    await settings_db.update_one({"_id": "bot_config"}, {"$set": {"notice": notice}})
    await message.reply_text("✅ সাইটের নোটিশ আপডেট হয়েছে!")

@app.on_message(filters.command("forward") & filters.user(ADMIN_ID))
async def set_forward(client, message: Message):
    status = message.command[1].lower() == "off"
    await settings_db.update_one({"_id": "bot_config"}, {"$set": {"forward_protect": status}})
    await message.reply_text(f"⚙️ Forward Protection: {'ON (Cannot Forward)' if status else 'OFF'}")

@app.on_message(filters.command("admin") & filters.user(ADMIN_ID))
async def set_admin_contact(client, message: Message):
    link = message.command[1]
    await settings_db.update_one({"_id": "bot_config"}, {"$set": {"admin_contact": link}})
    await message.reply_text("✅ অ্যাডমিন কন্টাক্ট বাটন আপডেট হয়েছে!")

@app.on_message(filters.command("addrediem") & filters.user(ADMIN_ID))
async def add_redeem(client, message: Message):
    _, code, d, m, y = message.text.split()
    await redeem_db.insert_one({"code": code, "days": int(d), "months": int(m), "years": int(y), "used": False})
    await message.reply_text(f"🎟️ কোড জেনারেট হয়েছে: `{code}`")

@app.on_message(filters.command("rediem") & filters.private)
async def use_redeem(client, message: Message):
    code = message.command[1]
    user_id = message.from_user.id
    data = await redeem_db.find_one({"code": code, "used": False})
    if data:
        expiry = datetime.now() + relativedelta(days=data['days'], months=data['months'], years=data['years'])
        await users_db.update_one({"user_id": user_id}, {"$set": {"is_premium": True, "premium_expiry": expiry}})
        await redeem_db.update_one({"code": code}, {"$set": {"used": True}})
        await message.reply_text("✅ আপনার প্রিমিয়াম এক্টিভেট হয়েছে!")
    else:
        await message.reply_text("❌ কোডটি ভুল বা ব্যবহৃত!")

@app.on_message(filters.command("premium") & filters.user(ADMIN_ID))
async def set_premium(client, message: Message):
    _, uid, d, m, y = message.text.split()
    expiry = datetime.now() + relativedelta(days=int(d), months=int(m), years=int(y))
    await users_db.update_one({"user_id": int(uid)}, {"$set": {"is_premium": True, "premium_expiry": expiry}})
    await message.reply_text(f"✅ ইউজার {uid} প্রিমিয়াম হয়েছে!")

@app.on_message(filters.command("delpremium") & filters.user(ADMIN_ID))
async def del_premium(client, message: Message):
    uid = int(message.command[1])
    await users_db.update_one({"user_id": uid}, {"$set": {"is_premium": False, "premium_expiry": None}})
    await message.reply_text("🚫 ইউজারের প্রিমিয়াম রিমুভ হয়েছে!")

@app.on_message(filters.command("stats") & filters.user(ADMIN_ID))
async def show_stats(client, message: Message):
    total = await users_db.count_documents({})
    prem = await users_db.count_documents({"is_premium": True})
    blocked = await users_db.count_documents({"is_blocked": True})
    files = await files_db.count_documents({})
    await message.reply_text(f"📊 স্ট্যাটাস:\nমোট ইউজার: {total}\nপ্রিমিয়াম: {prem}\nরেগুলার: {total-prem}\nব্লকড: {blocked}\nমোট ফাইল: {files}")

@app.on_message(filters.command("block") & filters.user(ADMIN_ID))
async def block_user(client, message: Message):
    uid = int(message.command[1])
    await users_db.update_one({"user_id": uid}, {"$set": {"is_blocked": True}})
    await message.reply_text("🚫 ব্লক করা হয়েছে!")

@app.on_message(filters.command("unblock") & filters.user(ADMIN_ID))
async def unblock_user(client, message: Message):
    uid = int(message.command[1])
    await users_db.update_one({"user_id": uid}, {"$set": {"is_blocked": False}})
    await message.reply_text("✅ আনব্লক করা হয়েছে!")

@app.on_message(filters.command("refer") & filters.user(ADMIN_ID))
async def set_refer(client, message: Message):
    coin = int(message.command[1])
    await settings_db.update_one({"_id": "bot_config"}, {"$set": {"refer_coin": coin}})
    await message.reply_text(f"✅ রেফার কয়েন {coin} সেট হয়েছে!")

@app.on_message(filters.command("addlist") & filters.user(ADMIN_ID))
async def add_list(client, message: Message):
    d, p = int(message.command[1]), int(message.command[2])
    await packages_db.insert_one({"days": d, "price": p})
    await message.reply_text(f"✅ প্যাকেজ এড: {d} দিন, {p} টাকা")

@app.on_message(filters.command("dellist") & filters.user(ADMIN_ID))
async def del_list(client, message: Message):
    d = int(message.command[1])
    await packages_db.delete_one({"days": d})
    await message.reply_text("✅ প্যাকেজ ডিলিট!")

@app.on_message(filters.command("luckspin") & filters.user(ADMIN_ID))
async def set_spin(client, message: Message):
    vals = [int(x) for x in message.command[1].split(",")]
    await settings_db.update_one({"_id": "bot_config"}, {"$set": {"spin_values": vals}})
    await message.reply_text("✅ স্পিন ভ্যালু আপডেট হয়েছে!")

# ================= ওয়েবসাইট ও মিনি অ্যাপ জেনারেটর (aiohttp) =================

async def web_app_handler(request):
    uid = request.query.get("uid")
    user = await users_db.find_one({"user_id": int(uid)}) if uid else None
    config = await settings_db.find_one({"_id": "bot_config"})
    files = await files_db.find().to_list(length=100)
    
    notice = config.get("notice", "স্বাগতম!")
    u_name = user['name'] if user else "Guest"
    u_coins = user['coins'] if user else 0
    u_stat = "Premium" if (user and await check_prem(user)) else "Regular"

    # ডাইনামিক ফাইল লিস্ট তৈরি
    files_html = ""
    for f in files:
        safe_name = f['file_name'].replace(' ', '_')
        files_html += f"""
        <div class="file-card">
            <div class="f-info">
                <h4>{f['file_name']}</h4>
                <span><i class="fa-solid fa-coins" style="color:gold;"></i> {f['price']} Coins</span>
            </div>
            <div class="f-actions">
                <button class="btn buy" onclick="buyFile('{safe_name}', {f['price']})">Buy</button>
                <button class="btn ad" onclick="alert('Ads system not integrated yet!')">Watch Ad</button>
            </div>
        </div>
        """

    html = f"""
    <!DOCTYPE html>
    <html lang="bn">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Mini App</title>
        <script src="https://telegram.org/js/telegram-web-app.js"></script>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
        <style>
            body {{ font-family: Arial; background: #121212; color: white; margin: 0; padding: 0; }}
            .marquee {{ background: #ffcc00; color: #000; padding: 5px; font-weight: bold; font-size:14px; text-align:center; }}
            .profile {{ background: #1e1e24; padding: 20px; text-align: center; border-bottom: 2px solid #ffcc00; }}
            .profile img {{ width: 70px; border-radius: 50%; border: 2px solid #ffcc00; }}
            .stats {{ display: flex; justify-content: space-around; margin: 15px 0; }}
            .box {{ background: #2b2b36; padding: 10px; border-radius: 8px; width: 40%; text-align: center; }}
            .box h3 {{ margin: 5px 0; color: #ffcc00; }}
            .file-card {{ background: #2b2b36; margin: 10px; padding: 15px; border-radius: 8px; display: flex; justify-content: space-between; align-items: center; }}
            .f-info h4 {{ margin: 0 0 5px 0; }}
            .btn {{ padding: 8px 12px; border: none; border-radius: 5px; cursor: pointer; font-weight: bold; }}
            .buy {{ background: #ffcc00; color: #000; }}
            .ad {{ background: #00cc66; color: #fff; }}
        </style>
    </head>
    <body>
        <div class="marquee"><marquee>{notice}</marquee></div>
        
        <div class="profile">
            <img id="uPic" src="https://via.placeholder.com/70" alt="Profile">
            <h3 style="margin: 10px 0 0 0;">{u_name}</h3>
            <p style="margin: 0; color: #aaa; font-size: 12px;">UID: {uid}</p>
        </div>

        <div class="stats">
            <div class="box">
                <p style="margin:0;">Balance</p>
                <h3>{u_coins}</h3>
            </div>
            <div class="box">
                <p style="margin:0;">Status</p>
                <h3>{u_stat}</h3>
            </div>
        </div>

        <h3 style="padding-left:15px; border-left: 4px solid #ffcc00; margin-left: 10px;">Latest Files</h3>
        {files_html}

        <script>
            let tg = window.Telegram.WebApp;
            tg.expand();
            if(tg.initDataUnsafe.user && tg.initDataUnsafe.user.photo_url) {{
                document.getElementById('uPic').src = tg.initDataUnsafe.user.photo_url;
            }}
            
            function buyFile(fileName, price) {{
                tg.showConfirm(`আপনি কি ${{price}} কয়েন দিয়ে ফাইলটি আনলক করতে চান?`, function(c) {{
                    if(c) {{
                        // WebApp বন্ধ করে বটকে কমান্ড পাঠাবে
                        tg.openTelegramLink(`https://t.me/{(app.me.username)}?start=get_${{fileName}}`);
                        tg.close();
                    }}
                }});
            }}
        </script>
    </body>
    </html>
    """
    return web.Response(text=html, content_type='text/html')

async def health_check(request):
    return web.Response(text="Bot & Server Running Perfectly!")

async def start_web_server():
    web_app = web.Application()
    web_app.router.add_get('/', health_check)
    web_app.router.add_get('/app', web_app_handler) # মিনি অ্যাপ এর রুট
    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    print(f"✅ Web App Server started on port {PORT}")

# ================= মেইন ফাংশন =================
async def main():
    await init_db()
    print("Starting Web Server...")
    await start_web_server()
    
    print("Starting Telegram Bot...")
    await app.start()
    app.me = await app.get_me() # বটের ইউজারনেম বের করার জন্য
    print("✅ Telegram Bot & Mini App Started Successfully!")
    
    await idle()
    await app.stop()

if __name__ == "__main__":
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        pass
