import asyncio

# ================= Python 3.10+ Pyrogram Crash Fix =================
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
# ===================================================================

import os
import cv2
import random
from datetime import datetime
from dateutil.relativedelta import relativedelta
from PIL import Image
from aiohttp import web
from pyrogram import Client, filters, idle
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import UserNotParticipant
from motor.motor_asyncio import AsyncIOMotorClient

# ================= কনফিগারেশন =================
API_ID = int(os.environ.get("API_ID", 29904834))
API_HASH = os.environ.get("API_HASH", "8b4fd9ef578af114502feeafa2d31938")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8206083172:AAHP9raleY3l2R2HBTGSVCdpcLQvgn960Mw")
MONGO_URI = os.environ.get("MONGO_URI", "mongodb+srv://akash:akash@cluster0.etisrpx.mongodb.net/?appName=Cluster0")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 7120801813))
FSUB_CHANNEL = os.environ.get("FSUB_CHANNEL", "-1003309004720") # আপনার চ্যানেলের আইডি দিন
SITE_URL = os.environ.get("SITE_URL", "https://amiking-site.vercel.app") # আপনার Vercel সাইটের লিংক
RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL", "https://amiking.onrender.com")

# ================= ডাটাবেস সেটআপ =================
mongo_client = AsyncIOMotorClient(MONGO_URI)
db = mongo_client["FileStoreDB"]
users_db = db["users"]
files_db = db["files"]
settings_db = db["settings"]
redeem_db = db["redeems"]
packages_db = db["packages"]

app = Client("AdvancedFileStoreBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
upload_state = {}

# ================= ল্যান্ডস্কেপ স্ক্রিনশট ফাংশন =================
def generate_landscape_thumb(video_path, output_path):
    try:
        cam = cv2.VideoCapture(video_path)
        ret, frame = cam.read()
        cam.release()
        if not ret: return False
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(frame)
        target_width, target_height = 1280, 720
        img.thumbnail((target_width, target_height), Image.Resampling.LANCZOS)
        background = Image.new('RGB', (target_width, target_height), (0, 0, 0))
        bg_w, bg_h = background.size
        img_w, img_h = img.size
        offset = ((bg_w - img_w) // 2, (bg_h - img_h) // 2)
        background.paste(img, offset)
        background.save(output_path)
        return True
    except:
        return False

# ================= Force Subscribe চেক =================
async def check_fsub(client, user_id):
    if not FSUB_CHANNEL: return True
    try:
        await client.get_chat_member(FSUB_CHANNEL, user_id)
        return True
    except UserNotParticipant:
        return False
    except Exception:
        return True # চ্যানেল এডমিন না থাকলে ইগনোর করবে

# ================= ইউজারের স্ট্যাটাস আপডেট (Premium Expiry) =================
async def check_premium_status(user_data):
    if user_data.get("is_premium") and user_data.get("premium_expiry"):
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

    # ব্লক চেক
    user_data = await users_db.find_one({"user_id": user_id})
    if user_data and user_data.get("is_blocked"):
        return await message.reply_text("🚫 আপনি এই বট থেকে ব্লকড!")

    # Force Subscribe চেক
    is_joined = await check_fsub(client, user_id)
    if not is_joined:
        btn = InlineKeyboardMarkup([[InlineKeyboardButton("📢 জয়েন চ্যানেল", url=f"https://t.me/{str(FSUB_CHANNEL).replace('-100', '')}")],
                                    [InlineKeyboardButton("✅ জয়েন করেছি", callback_data="check_sub")]])
        return await message.reply_text("⚠️ বটটি ব্যবহার করতে প্রথমে আমাদের চ্যানেলে জয়েন করুন!", reply_markup=btn)

    # রেফার সিস্টেম চেক
    if len(message.command) > 1 and not user_data:
        referrer_id = int(message.command[1])
        if referrer_id != user_id:
            settings = await settings_db.find_one({"_id": "bot_settings"})
            ref_coin = settings.get("refer_coin", 10) if settings else 10
            await users_db.update_one({"user_id": referrer_id}, {"$inc": {"coins": ref_coin}})
            await client.send_message(referrer_id, f"🎉 নতুন রেফার! আপনি {ref_coin} Coins পেয়েছেন।")

    # ইউজার সেভ করা
    if not user_data:
        await users_db.insert_one({"user_id": user_id, "name": user_name, "coins": 0, "is_premium": False, "premium_expiry": None, "is_blocked": False, "last_spin": None})
        user_data = await users_db.find_one({"user_id": user_id})

    # প্রিমিয়াম চেক
    is_prem = await check_premium_status(user_data)
    status_text = "👑 Premium" if is_prem else "👤 Regular"
    coins = user_data.get('coins', 0)

    # ওয়েব অ্যাপ লগিন URL
    web_app_url = f"{SITE_URL}?uid={user_id}"

    text = f"👋 স্বাগতম **{user_name}**!\n\n"
    text += f"🔖 **ইউজার আইডি:** `{user_id}`\n"
    text += f"🔰 **স্ট্যাটাস:** {status_text}\n"
    text += f"💰 **ব্যালেন্স:** {coins} Coins\n\n"
    text += f"🔗 **আপনার রেফার লিংক:** `https://t.me/{client.me.username}?start={user_id}`\n\n"
    text += f"🎁 প্রতিদিন ফ্রি স্পিন করতে `/spin` ব্যবহার করুন।"

    btn = InlineKeyboardMarkup([[InlineKeyboardButton("🌐 ওয়েবসাইটে যান (Login)", web_app=web_app_url)]])
    await message.reply_text(text, reply_markup=btn)

# ================= অ্যাডমিন কমান্ডস =================

# ১. /new [File_Name] [Unlock_Coin]
@app.on_message(filters.command("new") & filters.user(ADMIN_ID))
async def new_file_cmd(client, message: Message):
    if len(message.command) < 3:
        return await message.reply_text("ব্যবহার করুন: `/new [ফাইলের নাম] [আনলক কয়েন]`\nউদাহরণ: `/new Spiderman 20`")
    
    file_name = message.text.split(None, 2)[1]
    coin_price = int(message.text.split(None, 2)[2])
    
    upload_state[ADMIN_ID] = {"step": "wait_for_file", "name": file_name, "price": coin_price}
    await message.reply_text(f"📂 **{file_name}** এর জন্য ভিডিও ফাইলটি সেন্ড করুন:")

@app.on_message(filters.private & filters.user(ADMIN_ID) & filters.media & ~filters.command(["new"]))
async def receive_file(client, message: Message):
    if upload_state.get(ADMIN_ID, {}).get("step") == "wait_for_file":
        data = upload_state[ADMIN_ID]
        file_id = message.video.file_id if message.video else (message.document.file_id if message.document else None)
        if not file_id: return await message.reply_text("❌ শুধু ভিডিও সেন্ড করুন!")

        status_msg = await message.reply_text("⏳ প্রসেসিং ও স্ক্রিনশট নেওয়া হচ্ছে...")
        file_path = await client.download_media(message)
        thumb_path = f"thumb_{message.id}.jpg"
        
        success = generate_landscape_thumb(file_path, thumb_path)
        thumb_file_id = None
        if success:
            sent_thumb = await message.reply_photo(photo=thumb_path)
            thumb_file_id = sent_thumb.photo.file_id
            os.remove(thumb_path)
        elif message.video and message.video.thumbs:
            thumb_file_id = message.video.thumbs[0].file_id

        if os.path.exists(file_path): os.remove(file_path)

        await files_db.insert_one({
            "file_name": data["name"],
            "file_id": file_id,
            "thumb_id": thumb_file_id,
            "type": "video",
            "price_coins": data["price"],
            "views": 0
        })
        del upload_state[ADMIN_ID]
        await status_msg.edit_text(f"🎉 ফাইল সাইটে আপলোড হয়েছে!\n**নাম:** {data['name']}\n**প্রাইস:** {data['price']} Coins")

# ২. /delfile, /delall, /notice, /forward
@app.on_message(filters.command("delfile") & filters.user(ADMIN_ID))
async def del_file(client, message: Message):
    name = message.text.split(None, 1)[1]
    res = await files_db.delete_one({"file_name": name})
    await message.reply_text("✅ ডিলিট হয়েছে!" if res.deleted_count > 0 else "❌ পাওয়া যায়নি!")

@app.on_message(filters.command("delall") & filters.user(ADMIN_ID))
async def del_all(client, message: Message):
    await files_db.delete_many({})
    await message.reply_text("🗑️ সব ফাইল ডিলিট হয়েছে!")

@app.on_message(filters.command("notice") & filters.user(ADMIN_ID))
async def set_notice(client, message: Message):
    notice = message.text.split(None, 1)[1]
    await settings_db.update_one({"_id": "bot_settings"}, {"$set": {"notice": notice}}, upsert=True)
    await message.reply_text("📢 নোটিশ আপডেট হয়েছে!")

@app.on_message(filters.command("forward") & filters.user(ADMIN_ID))
async def set_forward(client, message: Message):
    status = message.command[1].lower() == "off"
    await settings_db.update_one({"_id": "bot_settings"}, {"$set": {"protect_content": status}}, upsert=True)
    await message.reply_text(f"⚙️ Forward protection: {'ON' if status else 'OFF'}")

# ৩. প্রিমিয়াম কন্ট্রোল (/addrediem, /rediem, /premium, /delpremium)
@app.on_message(filters.command("addrediem") & filters.user(ADMIN_ID))
async def add_prem_redeem(client, message: Message):
    # /addrediem CODE DAYS MONTHS YEARS
    _, code, d, m, y = message.text.split()
    await redeem_db.insert_one({"code": code, "days": int(d), "months": int(m), "years": int(y), "used": False})
    await message.reply_text(f"🎟️ প্রিমিয়াম কোড জেনারেট হয়েছে: `{code}`")

@app.on_message(filters.command("rediem"))
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
        await message.reply_text("❌ কোড ইনভ্যালিড বা ব্যবহৃত!")

@app.on_message(filters.command("premium") & filters.user(ADMIN_ID))
async def add_premium_direct(client, message: Message):
    # /premium USER_ID DAYS MONTHS YEARS
    _, uid, d, m, y = message.text.split()
    expiry = datetime.now() + relativedelta(days=int(d), months=int(m), years=int(y))
    await users_db.update_one({"user_id": int(uid)}, {"$set": {"is_premium": True, "premium_expiry": expiry}}, upsert=True)
    await message.reply_text(f"✅ ইউজার {uid} প্রিমিয়াম হয়েছে!")

@app.on_message(filters.command("delpremium") & filters.user(ADMIN_ID))
async def del_premium_direct(client, message: Message):
    uid = int(message.command[1])
    await users_db.update_one({"user_id": uid}, {"$set": {"is_premium": False, "premium_expiry": None}})
    await message.reply_text("🚫 ইউজারের প্রিমিয়াম বাতিল হয়েছে!")

# ৪. ইউজারের তথ্য ও স্ট্যাটাস (/stats, /block, /unblock, /refer)
@app.on_message(filters.command("stats") & filters.user(ADMIN_ID))
async def bot_stats(client, message: Message):
    total = await users_db.count_documents({})
    prem = await users_db.count_documents({"is_premium": True})
    blocked = await users_db.count_documents({"is_blocked": True})
    files = await files_db.count_documents({})
    reg = total - prem
    
    text = f"📊 **বট স্ট্যাটিস্টিক্স:**\n\n"
    text += f"👥 মোট ইউজার: {total}\n👑 প্রিমিয়াম ইউজার: {prem}\n👤 রেগুলার ইউজার: {reg}\n"
    text += f"🚫 ব্লকড ইউজার: {blocked}\n📁 মোট ফাইল: {files}\n"
    text += f"🌐 Render URL: `{RENDER_URL}`"
    await message.reply_text(text)

@app.on_message(filters.command("block") & filters.user(ADMIN_ID))
async def block_user(client, message: Message):
    uid = int(message.command[1])
    await users_db.update_one({"user_id": uid}, {"$set": {"is_blocked": True}})
    await message.reply_text(f"🚫 ইউজার {uid} ব্লক হয়েছে!")

@app.on_message(filters.command("unblock") & filters.user(ADMIN_ID))
async def unblock_user(client, message: Message):
    uid = int(message.command[1])
    await users_db.update_one({"user_id": uid}, {"$set": {"is_blocked": False}})
    await message.reply_text(f"✅ ইউজার {uid} আনব্লক হয়েছে!")

@app.on_message(filters.command("refer") & filters.user(ADMIN_ID))
async def set_refer(client, message: Message):
    # /refer 1 10 (বা শুধু 10)
    coin = int(message.command[-1])
    await settings_db.update_one({"_id": "bot_settings"}, {"$set": {"refer_coin": coin}}, upsert=True)
    await message.reply_text(f"✅ প্রতি রেফারে {coin} Coins সেট করা হয়েছে!")

# ৫. প্যাকেজ লিস্ট বিক্রি (/addlist, /dellist)
@app.on_message(filters.command("addlist") & filters.user(ADMIN_ID))
async def add_list(client, message: Message):
    # /addlist 10 10 (10 days 10 Taka)
    d, p = int(message.command[1]), int(message.command[2])
    await packages_db.insert_one({"days": d, "price": p})
    await message.reply_text(f"✅ প্যাকেজ এড হয়েছে: {d} দিন, {p} টাকা")

@app.on_message(filters.command("dellist") & filters.user(ADMIN_ID))
async def del_list(client, message: Message):
    d = int(message.command[1])
    await packages_db.delete_one({"days": d})
    await message.reply_text("✅ প্যাকেজ ডিলিট হয়েছে!")

# ৬. লাকি স্পিন (/luckspin, /spin)
@app.on_message(filters.command("luckspin") & filters.user(ADMIN_ID))
async def set_luckyspin(client, message: Message):
    # /luckspin 10,9,8,5,0,0,1,2,5,10
    values = [int(x) for x in message.command[1].split(",")]
    await settings_db.update_one({"_id": "bot_settings"}, {"$set": {"spin_values": values}}, upsert=True)
    await message.reply_text(f"🎡 স্পিন ভ্যালু এড হয়েছে: {values}")

@app.on_message(filters.command("spin"))
async def daily_spin(client, message: Message):
    user_id = message.from_user.id
    user_data = await users_db.find_one({"user_id": user_id})
    
    # 24 hour check
    if user_data.get("last_spin"):
        if (datetime.now() - user_data["last_spin"]).days < 1:
            return await message.reply_text("⚠️ আপনি আজকের স্পিন করে ফেলেছেন! আগামীকাল আবার চেষ্টা করুন।")
            
    settings = await settings_db.find_one({"_id": "bot_settings"})
    values = settings.get("spin_values", [1, 2, 5, 0, 10]) if settings else [1, 2, 5, 0, 10]
    
    won_coin = random.choice(values)
    
    await users_db.update_one({"user_id": user_id}, {"$inc": {"coins": won_coin}, "$set": {"last_spin": datetime.now()}})
    await message.reply_text(f"🎰 স্পিন ঘুরছে...\n\n🎉 অভিনন্দন! আপনি **{won_coin} Coins** জিতেছেন!")

# ================= Render ক্র্যাশ ফিক্স (Dummy Server) =================
async def handle(request):
    return web.Response(text=f"Bot is running! Render URL: {RENDER_URL}")

async def start_web_server():
    web_app = web.Application()
    web_app.router.add_get('/', handle)
    runner = web.AppRunner(web_app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"✅ Web Server running on port {port}")

# ================= মেইন ফাংশন =================
async def main():
    await app.start()
    print("✅ Telegram Bot Started Successfully!")
    await start_web_server()
    await idle()
    await app.stop()

if __name__ == "__main__":
    loop.run_until_complete(main())
