import os
import asyncio
import cv2
from PIL import Image
from aiohttp import web
from pyrogram import Client, filters, idle
from pyrogram.types import Message
from motor.motor_asyncio import AsyncIOMotorClient

# ================= কনফিগারেশন =================
API_ID = 29904834
API_HASH = "8b4fd9ef578af114502feeafa2d31938"
BOT_TOKEN = "8206083172:AAHP9raleY3l2R2HBTGSVCdpcLQvgn960Mw"
MONGO_URI = "mongodb+srv://akash:akash@cluster0.etisrpx.mongodb.net/?appName=Cluster0"
ADMIN_ID = 7120801813

# ================= অ্যাপ ইনিশিয়ালাইজেশন =================
app = Client("AdvancedFileStoreBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ================= ডাটাবেস সেটআপ =================
mongo_client = AsyncIOMotorClient(MONGO_URI)
db = mongo_client["FileStoreDB"]
users_db = db["users"]
files_db = db["files"]
settings_db = db["settings"]
redeem_db = db["redeems"]

upload_state = {}

# ================= ল্যান্ডস্কেপ স্ক্রিনশট ফাংশন =================
def generate_landscape_thumb(video_path, output_path):
    try:
        # ভিডিও থেকে ফ্রেম নেওয়া
        cam = cv2.VideoCapture(video_path)
        ret, frame = cam.read()
        cam.release()
        
        if not ret:
            return False
            
        # ছবিকে ল্যান্ডস্কেপ (1280x720) সাইজে কনভার্ট করা
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
        print(f"Screenshot Error: {e}")
        return False

# ================= অ্যাডমিন কমান্ডস =================

# ১. /new - ফাইল এড করা, অটো ল্যান্ডস্কেপ স্ক্রিনশট এবং ভিউ কাউন্ট
@app.on_message(filters.command("new") & filters.user(ADMIN_ID) & filters.private)
async def new_file_cmd(client, message: Message):
    upload_state[ADMIN_ID] = {"step": "wait_for_file"}
    await message.reply_text("📂 দয়া করে ভিডিও ফাইলটি সেন্ড করুন:")

@app.on_message(filters.private & filters.user(ADMIN_ID) & filters.media & ~filters.command(["new"]))
async def receive_file(client, message: Message):
    if upload_state.get(ADMIN_ID, {}).get("step") == "wait_for_file":
        file_id = message.video.file_id if message.video else (message.document.file_id if message.document else None)
        
        if not file_id:
            return await message.reply_text("❌ এটি সাপোর্ট করে না এমন ফাইল! দয়া করে ভিডিও সেন্ড করুন।")

        status_msg = await message.reply_text("⏳ ভিডিও ডাউনলোড হচ্ছে এবং ল্যান্ডস্কেপ (Landscape) স্ক্রিনশট তৈরি করা হচ্ছে... দয়া করে অপেক্ষা করুন।")
        
        # ফাইল ডাউনলোড এবং স্ক্রিনশট তৈরি
        file_path = await client.download_media(message)
        thumb_path = f"thumb_{message.id}.jpg"
        success = generate_landscape_thumb(file_path, thumb_path)
        
        thumb_file_id = None
        if success:
            # ল্যান্ডস্কেপ স্ক্রিনশট টেলিগ্রামে সেভ করা
            sent_thumb = await message.reply_photo(photo=thumb_path, caption="✅ ল্যান্ডস্কেপ স্ক্রিনশট সফলভাবে নেওয়া হয়েছে!")
            thumb_file_id = sent_thumb.photo.file_id
            os.remove(thumb_path)
        else:
            await message.reply_text("⚠️ স্ক্রিনশট নেওয়া সম্ভব হয়নি। ডিফল্ট থাম্বনেইল ব্যবহার করা হবে।")
            if message.video and message.video.thumbs:
                thumb_file_id = message.video.thumbs[0].file_id

        # স্টোরেজ খালি করার জন্য ভিডিও ডিলিট
        if os.path.exists(file_path):
            os.remove(file_path)

        upload_state[ADMIN_ID] = {
            "step": "wait_for_name",
            "file_id": file_id,
            "thumb_id": thumb_file_id,
            "file_type": "video"
        }
        await status_msg.edit_text("✅ ফাইল প্রসেসিং সম্পন্ন হয়েছে!\n\n📝 এবার সাইটের জন্য এই ভিডিওর একটি নাম লিখে সেন্ড করুন:")

@app.on_message(filters.private & filters.user(ADMIN_ID) & filters.text & ~filters.command(["new"]))
async def receive_filename(client, message: Message):
    if upload_state.get(ADMIN_ID, {}).get("step") == "wait_for_name":
        file_name = message.text
        data = upload_state[ADMIN_ID]
        
        # ডাটাবেসে সেভ করা (views: 0 সহ)
        file_doc = {
            "file_name": file_name,
            "file_id": data["file_id"],
            "thumb_id": data["thumb_id"],
            "type": data["file_type"],
            "price_coins": 20,
            "views": 0  # <--- ভিউ কাউন্ট শুরু হবে এখান থেকে
        }
        result = await files_db.insert_one(file_doc)
        
        del upload_state[ADMIN_ID]
        await message.reply_text(f"🎉 ভিডিওটি সফলভাবে ডাটাবেসে এড হয়েছে!\n\n**নাম:** {file_name}\n**ভিউজ:** 0 (সাইট থেকে ভিউ হলে বাড়বে)\n**File DB ID:** `{result.inserted_id}`")

# ২. /forward off / on (ফরওয়ার্ড রেস্ট্রিকশন)
@app.on_message(filters.command("forward") & filters.user(ADMIN_ID))
async def forward_control(client, message: Message):
    if len(message.command) > 1:
        status = message.command[1].lower()
        if status in ["on", "off"]:
            is_protected = True if status == "off" else False
            await settings_db.update_one({"_id": "bot_settings"}, {"$set": {"protect_content": is_protected}}, upsert=True)
            await message.reply_text(f"⚙️ Forward protection is now **{'ON' if is_protected else 'OFF'}**")
    else:
        await message.reply_text("ব্যবহার করুন: `/forward on` অথবা `/forward off`")

# ৩. /delall (সব ফাইল ডিলিট)
@app.on_message(filters.command("delall") & filters.user(ADMIN_ID))
async def delete_all_files(client, message: Message):
    await files_db.delete_many({})
    await message.reply_text("🗑️ ডাটাবেস এবং ওয়েবসাইট থেকে **সব ফাইল** ডিলিট করা হয়েছে!")

# ৪. /delfile (নির্দিষ্ট ফাইল ডিলিট)
@app.on_message(filters.command("delfile") & filters.user(ADMIN_ID))
async def delete_specific_file(client, message: Message):
    if len(message.command) > 1:
        file_name_or_id = message.text.split(None, 1)[1]
        result = await files_db.delete_one({"file_name": file_name_or_id})
        if result.deleted_count > 0:
            await message.reply_text(f"✅ `{file_name_or_id}` ফাইলটি ডিলিট হয়েছে।")
        else:
            await message.reply_text("❌ এই নামের কোনো ফাইল পাওয়া যায়নি।")
    else:
        await message.reply_text("ব্যবহার করুন: `/delfile [ফাইলের নাম]`")

# ৫. /notice (সাইট বা বটের নোটিশ)
@app.on_message(filters.command("notice") & filters.user(ADMIN_ID))
async def set_notice(client, message: Message):
    if len(message.command) > 1:
        notice_text = message.text.split(None, 1)[1]
        await settings_db.update_one({"_id": "bot_settings"}, {"$set": {"notice": notice_text}}, upsert=True)
        await message.reply_text(f"📢 নোটিশ আপডেট করা হয়েছে:\n\n{notice_text}")
    else:
        await message.reply_text("ব্যবহার করুন: `/notice [আপনার মেসেজ]`")

# ৬. /addpremium (ইউজারকে প্রিমিয়াম দেওয়া)
@app.on_message(filters.command("addpremium") & filters.user(ADMIN_ID))
async def add_premium(client, message: Message):
    if len(message.command) > 1:
        target_user = int(message.command[1])
        await users_db.update_one({"user_id": target_user}, {"$set": {"is_premium": True}}, upsert=True)
        await message.reply_text(f"👑 ইউজার `{target_user}` কে প্রিমিয়াম দেওয়া হয়েছে!")
    else:
        await message.reply_text("ব্যবহার করুন: `/addpremium [User ID]`")

# ৭. /delpremium (ইউজারের প্রিমিয়াম বাতিল করা)
@app.on_message(filters.command("delpremium") & filters.user(ADMIN_ID))
async def del_premium(client, message: Message):
    if len(message.command) > 1:
        target_user = int(message.command[1])
        await users_db.update_one({"user_id": target_user}, {"$set": {"is_premium": False}}, upsert=True)
        await message.reply_text(f"🚫 ইউজার `{target_user}` এর প্রিমিয়াম বাতিল করা হয়েছে!")
    else:
        await message.reply_text("ব্যবহার করুন: `/delpremium [User ID]`")

# ৮. /addrediem (রিডিম কোড বানানো)
@app.on_message(filters.command("addrediem") & filters.user(ADMIN_ID))
async def add_redeem_code(client, message: Message):
    try:
        cmd, code, amount = message.text.split()
        await redeem_db.insert_one({"code": code, "coins": int(amount), "used_by": []})
        await message.reply_text(f"🎟️ রিডিম কোড তৈরি হয়েছে!\n\n**কোড:** `{code}`\n**কয়েন:** {amount}")
    except ValueError:
        await message.reply_text("❌ ভুল ফরম্যাট! ব্যবহার করুন:\n`/addrediem [কোড] [কয়েনের পরিমাণ]`")

# ================= ইউজার কমান্ডস =================

# ৯. /rediem (রিডিম কোড ব্যবহার করা)
@app.on_message(filters.command("rediem"))
async def use_redeem_code(client, message: Message):
    if len(message.command) > 1:
        code = message.command[1]
        user_id = message.from_user.id
        
        code_data = await redeem_db.find_one({"code": code})
        
        if code_data:
            if user_id in code_data.get("used_by", []):
                return await message.reply_text("⚠️ আপনি আগেই এই কোডটি ব্যবহার করেছেন!")
            
            coins = code_data["coins"]
            await users_db.update_one({"user_id": user_id}, {"$inc": {"coins": coins}}, upsert=True)
            await redeem_db.update_one({"code": code}, {"$push": {"used_by": user_id}})
            
            await message.reply_text(f"✅ অভিনন্দন! আপনি **{coins} Coins** পেয়েছেন।")
        else:
            await message.reply_text("❌ কোডটি ইনভ্যালিড বা ভুল!")
    else:
        await message.reply_text("ব্যবহার করুন: `/rediem [কোড]`")


# ================= Render ক্র্যাশ ফিক্স করার জন্য Web Server =================
async def handle(request):
    return web.Response(text="Bot is running successfully on Render! No more crashes.")

async def start_web_server():
    web_app = web.Application()
    web_app.router.add_get('/', handle)
    runner = web.AppRunner(web_app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080)) # Render অটোমেটিক এই পোর্টটি দিবে
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"✅ Dummy Web Server started on port {port} (Prevents Render Crash)")

# ================= মেইন ফাংশন =================
async def main():
    await app.start()
    print("✅ Telegram Bot Started!")
    
    # Render-কে খুশি রাখতে ওয়েব সার্ভার রান করানো
    await start_web_server()
    
    # বটকে সবসময় সচল রাখা
    await idle()
    await app.stop()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
