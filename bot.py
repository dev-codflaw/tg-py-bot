import os
from datetime import datetime
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv
import tempfile
from pymongo import MongoClient
import cloudinary
import cloudinary.uploader

# Load environment variables
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_STR = os.getenv("MONGO_STR")

CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET")

# Cloudinary setup
cloudinary.config(
    cloud_name=CLOUDINARY_CLOUD_NAME,
    api_key=CLOUDINARY_API_KEY,
    api_secret=CLOUDINARY_API_SECRET
)

# MongoDB setup
client = MongoClient(MONGO_STR)
db = client["telegram_db"]
collection = db["lax_itsm"]

async def handle_image_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message or update.channel_post
    print("📥 Handler triggered...")

    # Validate image + caption
    if not message or not message.photo or not message.caption:
        print("⚠️ Image or caption missing.")
        if message:
            await message.reply_text("⚠️ Please send an image *with* a caption.")
        return

    try:
        photo = message.photo[-1]
        file = await context.bot.get_file(photo.file_id)

        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        filename = f"{message.chat.id}_{photo.file_unique_id}_{timestamp}.jpg"

        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_file:
            await file.download_to_drive(temp_file.name)

            print("📤 Uploading to Cloudinary...")
            upload_result = cloudinary.uploader.upload(
                temp_file.name,
                folder="telegram_uploads",
                public_id=filename
            )

            image_url = upload_result.get("secure_url")
            if not image_url:
                raise Exception("Cloudinary upload failed.")

            print(f"✅ Uploaded to Cloudinary: {image_url}")

        # Save metadata to MongoDB
        doc = {
            "chat_id": message.chat.id,
            "chat_type": message.chat.type.name,
            "caption": message.caption,
            "image_url": image_url,
            "timestamp": message.date
        }
        collection.insert_one(doc)
        print(f"📦 Saved to MongoDB: {doc}")

        # Success reply
        reply_text = f"✅ Ticket created!\n🧾 ticket_id: {message.chat.id}\n📝 Caption: {message.caption}"
        await message.reply_text(reply_text)

    except Exception as e:
        print(f"❌ Upload failed: {e}")
        await message.reply_text("❌ Failed to upload image or save data.")

# Handle only text messages
async def handle_only_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message or update.channel_post
    if message and message.text:
        print("✉️ Only text received — rejecting.")
        await message.reply_text("⚠️ Please send an image *with* text (caption).")

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(MessageHandler(filters.PHOTO, handle_image_upload))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_only_text))

    print("🤖 Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
