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
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import UserNotParticipant
from motor.motor_asyncio import AsyncIOMotorClient

# ================= আপনার অরিজিনাল কনফিগারেশন =================
API_ID = 29904834
API_HASH = "8b4fd9ef578af114502feeafa2d31938"
BOT_TOKEN = "8206083172:AAHP9raleY3l2R2HBTGSVCdpcLQvgn960Mw"
MONGO_URI = "mongodb+srv://akash:akash@cluster0.etisrpx.mongodb.net/?appName=Cluster0"
ADMIN_ID = 7120801813
FSUB_CHANNEL = "-1003309004720"
SITE_URL = "https://amiking-site.vercel.app" 
RENDER_URL = "https://amiking.onrender.com"

# Render পোর্ট অটোমেটিক নেবে, না পেলে 10000 ব্যবহার করবে
PORT = int(os.environ.get("PORT", 10000))

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
    except Exception as e:
        print(f"Thumbnail Error: {e}")
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
        return True 

# ================= ইউজারের প্রিমিয়াম স্ট্যাটাস চেক =================
async def check_premium_status(user_data):
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
            try:
                await client.send_message(referrer_id, f"🎉 নতুন রেফার! আপনি {ref_coin} Coins পেয়েছেন।")
            except:
                pass

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

@app.on_callback_query(filters.regex("check_sub"))
async def check_sub_callback(client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    is_joined = await check_fsub(client, user_id)
    
    if is_joined:
        await callback_query.answer("✅ চ্যানেলে জয়েন করার জন্য ধন্যবাদ!", show_alert=True)
        await callback_query.message.delete()
        await start_cmd(client, callback_query.message)
    else:
        await callback_query.answer("⚠️ আপনি এখনো আমাদের চ্যানেলে জয়েন করেননি! আগে জয়েন করুন।", show_alert=True)

# ================= অ্যাডমিন কমান্ডস =================

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

@app.on_message(filters.command("stats") & filters.user(ADMIN_ID))
async def bot_stats(client, message: Message):
    total = await users_db.count_documents({})
    prem = await users_db.count_documents({"is_premium": True})
    blocked = await users_db.count_documents({"is_blocked": True})
    files = await files_db.count_documents({})
    reg = total - prem
    
    text = f"📊 **বট স্ট্যাটিস্টিক্স:**\n\n"
    text += f"👥 মোট ইউজার: {total}\n👑 প্রিমিয়াম ইউজার: {prem}\n👤 রেগুলার ইউজার: {reg}\n"
    text += f"🚫 ব্লকড ইউজার: {blocked}\n📁 মোট ফাইল: {files}"
    await message.reply_text(text)

@app.on_message(filters.command("spin") & filters.private)
async def daily_spin(client, message: Message):
    user_id = message.from_user.id
    user_data = await users_db.find_one({"user_id": user_id})
    
    if user_data and user_data.get("last_spin"):
        if (datetime.now() - user_data["last_spin"]).days < 1:
            return await message.reply_text("⚠️ আপনি আজকের স্পিন করে ফেলেছেন! আগামীকাল আবার চেষ্টা করুন।")
            
    settings = await settings_db.find_one({"_id": "bot_settings"})
    values = settings.get("spin_values", [1, 2, 5, 0, 10]) if settings else [1, 2, 5, 0, 10]
    won_coin = random.choice(values)
    
    await users_db.update_one({"user_id": user_id}, {"$inc": {"coins": won_coin}, "$set": {"last_spin": datetime.now()}})
    await message.reply_text(f"🎰 স্পিন ঘুরছে...\n\n🎉 অভিনন্দন! আপনি **{won_coin} Coins** জিতেছেন!")

# ================= Render ক্র্যাশ ফিক্স (Dummy Web Server) =================
async def handle_request(request):
    return web.Response(text="Bot is Running Successfully on Render!")

async def start_web_server():
    web_app = web.Application()
    web_app.router.add_get('/', handle_request)
    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    print(f"✅ Web Server started on port {PORT}")

# ================= মেইন ফাংশন =================
async def main():
    # ⚠️ পোর্ট এরর এড়াতে সবার আগে ওয়েব সার্ভার চালু করছি
    print("Starting Web Server for Render...")
    await start_web_server()
    
    # সার্ভার চালুর পর বট স্টার্ট হবে
    print("Starting Telegram Bot...")
    await app.start()
    print("✅ Telegram Bot Started Successfully!")
    
    await idle()
    await app.stop()

if __name__ == "__main__":
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        print("Bot Stopped!")
