import os
from dotenv import load_dotenv
import httpx
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
import requests
from bs4 import BeautifulSoup
import os


load_dotenv()
TOKEN = os.getenv('TOKEN')
# print("TOKEN:", TOKEN)


url = f"https://api.telegram.org/bot{TOKEN}/getMe"

try:
    response = httpx.get(url, timeout=10)
    print(response.json())
except Exception as e:
    print("⛔ خطا:", e)


def build_longman_link(word):
    formatted_word = word.lower().replace(" ", "-")
    return f"https://www.ldoceonline.com/dictionary/{formatted_word}"

def build_oxford_link(word):
    formatted_word = word.lower().replace(" ", "-")
    return f"https://www.oxfordlearnersdictionaries.com/definition/english/{formatted_word}"

def fetch_longman_phonetics(word):
    url = f"https://www.ldoceonline.com/dictionary/{word.lower().replace(' ', '-')}"
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            return None

        soup = BeautifulSoup(response.text, "html.parser")

        # هیپنیشن
        hyphen_tag = soup.find("span", class_="HYPHENATION")
        hyphenation = hyphen_tag.text.strip() if hyphen_tag else None

        # فونتیک بریتیش
        pron_tag = soup.find("span", class_="PRON")
        british_ipa = pron_tag.text.strip() if pron_tag else None

        # فونتیک آمریکن
        amevar_tag = soup.find("span", class_="AMEVARPRON")
        american_ipa = None
        if amevar_tag:
            text = amevar_tag.get_text(separator=" ", strip=True).replace("$", "").strip()
            american_ipa = text if text else None

        return {
            "hyphenation": hyphenation,
            "british_ipa": british_ipa,
            "american_ipa": american_ipa
        }

    except Exception as e:
        print(f"⚠️ خطا در واکشی فونتیک: {e}")
        return None

def fetch_longman_data(word):
    url = build_longman_link(word)
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            return {}, {}

        soup = BeautifulSoup(response.text, "html.parser")
        audio_tags = soup.find_all("span", class_="speaker")

        # تلفظ صوتی
        audio_results = {}
        for tag in audio_tags:
            if tag.has_attr("data-src-mp3"):
                mp3_url = tag["data-src-mp3"]
                if "breProns" in mp3_url:
                    audio_results["british"] = mp3_url
                elif "ameProns" in mp3_url:
                    audio_results["american"] = mp3_url

        return audio_results

    except Exception as e:
        print(f"⚠️ خطا در واکشی اطلاعات لانگمن: {str(e)}")
        return {}, {}

async def handle_word(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"پیام دریافت شد: {update.message.text}")
    word = update.message.text.strip()
    longman_link = build_longman_link(word)
    oxford_link = build_oxford_link(word)

    # نمایش لینک‌های Longman و Oxford
    await update.message.reply_text(
        f"کلمه: {word}\n\n"
        f"📚 Longman: {longman_link}\n\n"
        f"📖 Oxford: {oxford_link}"
    )

    # واکشی فونتیک‌ها و هیپنیشن از لانگمن
    phonetics = fetch_longman_phonetics(word)
    if phonetics:
        message = f"کلمه: {word}"
        if phonetics["hyphenation"]:
            message += f"\n🔸 {phonetics['hyphenation']}"
        if phonetics["british_ipa"]:
            message += f"\n🇬🇧 BrE: /{phonetics['british_ipa']}/"
        if phonetics["american_ipa"]:
            message += f"\n🇺🇸 AmE: /{phonetics['american_ipa']}/"
        await update.message.reply_text(message)

    audio_urls= fetch_longman_data(word)

    if not audio_urls:
        await update.message.reply_text("⚠️ تلفظی برای این کلمه در لانگمن پیدا نشد.")
        return
    

    for accent in ["british", "american"]:
        caption = f"🔉 {accent.capitalize()} ({word})"
     
        if accent == "british":
            ipa = phonetics["british_ipa"]
        elif accent == "american":
            ipa = phonetics["american_ipa"]
        
        if ipa:
            caption += f"\n💡 {ipa}"

        if accent in audio_urls:
            url = audio_urls[accent]
            try:
                headers = {"User-Agent": "Mozilla/5.0"}
                response = requests.get(url, headers=headers)

                if response.status_code == 200 and response.headers["Content-Type"].startswith("audio"):
                    file_name = f"{word}_{accent}.mp3"
                    with open(file_name, "wb") as f:
                        f.write(response.content)

                    await update.message.reply_audio(
                        audio=open(file_name, "rb"),
                        caption=caption
                    )
                    os.remove(file_name)

                else:
                    await update.message.reply_text(f"⚠️ تلفظ {accent} برای '{word}' پیدا نشد یا دانلود نشد.")
            except Exception as e:
                await update.message.reply_text(f"❌ خطا در دانلود تلفظ {accent}: {str(e)}")
        else:
            await update.message.reply_text(f"⚠️ تلفظ {accent} در لانگمن برای این کلمه موجود نیست.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("به بات Akinglish خوش آمدید.")
    await update.message.reply_text("سلام! 👋 کلمه یا عبارت رو بفرست، تلفظ و فونتیک لانگمن و لینک‌هاش رو برات می‌فرستم.")

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_word))

    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
