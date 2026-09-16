import os
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
from motor.motor_asyncio import AsyncIOMotorClient

# ================= কনফিগারেশন =================
API_ID = int(os.environ.get("API_ID", "29904834"))
API_HASH = os.environ.get("API_HASH", "8b4fd9ef578af114502feeafa2d31938")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8206083172:AAHP9raleY3l2R2HBTGSVCdpcLQvgn960Mw")
MONGO_URI = os.environ.get("MONGO_URI", "mongodb+srv://akash:akash@cluster0.etisrpx.mongodb.net/?appName=Cluster0")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "7120801813")) # আপনার টেলিগ্রাম ইউজার আইডি

app = Client("AdvancedFileStoreBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ================= ডাটাবেস সেটআপ =================
mongo_client = AsyncIOMotorClient(MONGO_URI)
db = mongo_client["FileStoreDB"]
users_db = db["users"]
files_db = db["files"]
settings_db = db["settings"]
redeem_db = db["redeems"]

# State Management for /new command
upload_state = {}

# ================= অ্যাডমিন কমান্ডস =================

# ১. /new - ফাইল এড করা এবং অটো স্ক্রিনশট নেওয়া
@app.on_message(filters.command("new") & filters.user(ADMIN_ID) & filters.private)
async def new_file_cmd(client, message: Message):
    upload_state[ADMIN_ID] = {"step": "wait_for_file"}
    await message.reply_text("📂 দয়া করে ভিডিও, অডিও বা ডকুমেন্ট ফাইলটি সেন্ড করুন:")

@app.on_message(filters.private & filters.user(ADMIN_ID) & filters.media & ~filters.command(["new"]))
async def receive_file(client, message: Message):
    if upload_state.get(ADMIN_ID, {}).get("step") == "wait_for_file":
        file_id = None
        thumb_id = None
        file_type = None

        # ফাইলের ধরন ও অটো-স্ক্রিনশট (Thumbnail) সংগ্রহ করা
        if message.video:
            file_id = message.video.file_id
            file_type = "video"
            if message.video.thumbs:
                thumb_id = message.video.thumbs[0].file_id # টেলিগ্রামের অটো স্ক্রিনশট
        elif message.document:
            file_id = message.document.file_id
            file_type = "document"
            if message.document.thumbs:
                thumb_id = message.document.thumbs[0].file_id
        
        if not file_id:
            return await message.reply_text("❌ সাপোর্ট করে না এমন ফাইল!")

        upload_state[ADMIN_ID] = {
            "step": "wait_for_name",
            "file_id": file_id,
            "thumb_id": thumb_id,
            "file_type": file_type
        }
        await message.reply_text("✅ ফাইল রিসিভ হয়েছে! (স্ক্রিনশট অটো সেভ হয়েছে)\n\n📝 এবার এই ফাইলের একটি নাম লিখে সেন্ড করুন:")

@app.on_message(filters.private & filters.user(ADMIN_ID) & filters.text & ~filters.command(["new"]))
async def receive_filename(client, message: Message):
    if upload_state.get(ADMIN_ID, {}).get("step") == "wait_for_name":
        file_name = message.text
        data = upload_state[ADMIN_ID]
        
        # ডাটাবেসে সেভ করা
        file_doc = {
            "file_name": file_name,
            "file_id": data["file_id"],
            "thumb_id": data["thumb_id"],
            "type": data["file_type"],
            "price_coins": 20 # ডিফল্ট আনলক কয়েন
        }
        result = await files_db.insert_one(file_doc)
        
        del upload_state[ADMIN_ID]
        await message.reply_text(f"🎉 ফাইল সফলভাবে ডাটাবেস ও ওয়েবসাইটে এড হয়েছে!\n\n**নাম:** {file_name}\n**File DB ID:** `{result.inserted_id}`")

# ২. /forward off / on (ফরওয়ার্ড রেস্ট্রিকশন কন্ট্রোল)
@app.on_message(filters.command("forward") & filters.user(ADMIN_ID))
async def forward_control(client, message: Message):
    if len(message.command) > 1:
        status = message.command[1].lower()
        if status in ["on", "off"]:
            is_protected = True if status == "off" else False # off মানে রেস্ট্রিক্টেড
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

# ৫. /notice (সাইট বা বটের নোটিশ সেট করা)
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
        await message.reply_text(f"👑 ইউজার `{target_user}` কে প্রিমিয়াম এক্সেস দেওয়া হয়েছে!")
    else:
        await message.reply_text("ব্যবহার করুন: `/addpremium [User ID]`")

# ৭. /delpremium (ইউজারের প্রিমিয়াম বাতিল করা)
@app.on_message(filters.command("delpremium") & filters.user(ADMIN_ID))
async def del_premium(client, message: Message):
    if len(message.command) > 1:
        target_user = int(message.command[1])
        await users_db.update_one({"user_id": target_user}, {"$set": {"is_premium": False}}, upsert=True)
        await message.reply_text(f"🚫 ইউজার `{target_user}` এর প্রিমিয়াম এক্সেস বাতিল করা হয়েছে!")
    else:
        await message.reply_text("ব্যবহার করুন: `/delpremium [User ID]`")

# ৮. /addrediem (রিডিম কোড বানানো)
@app.on_message(filters.command("addrediem") & filters.user(ADMIN_ID))
async def add_redeem_code(client, message: Message):
    try:
        cmd, code, amount = message.text.split()
        await redeem_db.insert_one({"code": code, "coins": int(amount), "used_by": []})
        await message.reply_text(f"🎟️ নতুন রিডিম কোড তৈরি হয়েছে!\n\n**কোড:** `{code}`\n**কয়েন:** {amount}")
    except ValueError:
        await message.reply_text("❌ ভুল ফরম্যাট! ব্যবহার করুন:\n`/addrediem [কোড] [কয়েনের পরিমাণ]`")

# ================= ইউজার কমান্ডস =================

# ৯. /rediem (ইউজার রিডিম কোড ব্যবহার করবে)
@app.on_message(filters.command("rediem"))
async def use_redeem_code(client, message: Message):
    if len(message.command) > 1:
        code = message.command[1]
        user_id = message.from_user.id
        
        # ডাটাবেসে কোড চেক করা
        code_data = await redeem_db.find_one({"code": code})
        
        if code_data:
            if user_id in code_data.get("used_by", []):
                return await message.reply_text("⚠️ আপনি আগেই এই কোডটি ব্যবহার করেছেন!")
            
            coins = code_data["coins"]
            
            # ইউজারের একাউন্টে কয়েন যোগ করা
            await users_db.update_one({"user_id": user_id}, {"$inc": {"coins": coins}}, upsert=True)
            # কোডটি এই ইউজার ব্যবহার করেছে তা মার্ক করা
            await redeem_db.update_one({"code": code}, {"$push": {"used_by": user_id}})
            
            await message.reply_text(f"✅ অভিনন্দন! আপনি **{coins} Coins** পেয়েছেন। এটি ওয়েবসাইটে আপডেট হয়েছে।")
        else:
            await message.reply_text("❌ কোডটি ইনভ্যালিড বা ভুল!")
    else:
        await message.reply_text("ব্যবহার করুন: `/rediem [কোড]`")


# বট স্টার্ট কমান্ড (ইউজারদের ডাটাবেসে সেভ করতে)
@app.on_message(filters.command("start") & filters.private)
async def start_cmd(client, message: Message):
    user_id = message.from_user.id
    # ইউজার ডাটাবেসে না থাকলে যুক্ত করবে
    await users_db.update_one(
        {"user_id": user_id}, 
        {"$setOnInsert": {"coins": 0, "is_premium": False}}, 
        upsert=True
    )
    await message.reply_text("স্বাগতম! ওয়েবসাইট থেকে ভিডিও আনলক করতে আপনার কয়েন ব্যবহার করুন।")

if __name__ == "__main__":
    print("Bot is running...")
    app.run()
