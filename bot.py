import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message, FSInputFile
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from pyrogram import Client

# ==========================================
# ⚙️ ڕێکخستنەکان (CONFIGURATIONS)
# ==========================================
BOT_TOKEN = "8673929801:AAFTZ0Y99erugl-_wZZFkGj3oa4maYBmIcI"      # تۆکنی بۆتەکەت لە BotFather وەربگرە
CHANNEL_USERNAME = "dev_y7_krd"         # ئایدی کەناڵ بێ @
MAIN_ADMIN_ID = 7643191802               # ئایدی سەرەکی خاوەن بۆت

# زانیارییەکانی API Telegram (لە my.telegram.org وەربگرە)
API_ID = 34584240                       # API ID لێرە دابنێ
API_HASH = "eba4f8333cba5f9697a1d20779d4d6e9"         # API Hash لێرە دابنێ

# داتابەیسی بێچووک لە ناو میمۆری
allowed_users = {MAIN_ADMIN_ID}
all_users_db = set()

# ==========================================
# 🚀 دەستپێکردنی BOT & CLIENT
# ==========================================
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Pyrogram Client بۆ هێنانی زانیاری کوور و وێنە
user_client = Client("info_session", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ==========================================
# 🛑 FSM STATES
# ==========================================
class Form(StatesGroup):
    waiting_for_username = State()
    waiting_for_grant_id = State()
    waiting_for_broadcast = State()

# ==========================================
# 🔍 پشکنینی جۆینبوونی کەناڵ (FORCE JOIN)
# ==========================================
async def check_joined(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=f"@{CHANNEL_USERNAME}", user_id=user_id)
        return member.status in ["creator", "administrator", "member"]
    except Exception:
        return False

def get_join_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 جۆین بوون لە کەناڵ", url=f"https://t.me/{CHANNEL_USERNAME}")],
        [InlineKeyboardButton(text="✅ پشکنین (Check)", callback_data="check_subscription")]
    ])

def get_main_keyboard(user_id: int):
    buttons = [
        [InlineKeyboardButton(text="🔍 گەڕان بەدوای یوزەرنەیام (Username)", callback_data="search_user")]
    ]
    if user_id == MAIN_ADMIN_ID:
        buttons.append([InlineKeyboardButton(text="⚙️ پانێڵی بەڕێوەبەر (Admin Panel)", callback_data="admin_panel")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# ==========================================
# 📩 دەستپێک (/start)
# ==========================================
@dp.message(Command("start"))
async def start_cmd(message: Message):
    user_id = message.from_user.id
    all_users_db.add(user_id)
    
    if not await check_joined(user_id):
        await message.answer(
            f"⚠️ **سڵاو بەڕێز!**\n\nبۆ بەکارهێنانی ئەم بۆتە، پێویستە سەرەتا جۆینی کەناڵی فەرمی ئێمە بێت:\n👉 @{CHANNEL_USERNAME}",
            reply_markup=get_join_keyboard(),
            parse_mode="Markdown"
        )
        return

    if user_id not in allowed_users:
        await message.answer("❌ **داواکاری ڕەتکرایەوە!**\nئێوە ڕێگەپێدانی بەکارهێنانی ئەم بۆتەتان نییە. پەیوەندی بە بەڕێوەبەرەوە بکەن.")
        return

    await message.answer(
        f"🌹 **سڵاو بەڕێز {message.from_user.first_name}!**\n\nبه‌خێربێیت بۆ **Y7_KRD INFO BOT**. تکایە یەکێک لە بژاردەکانی خوارەوە هەڵبژێرە:",
        reply_markup=get_main_keyboard(user_id)
    )

@dp.callback_query(F.data == "check_subscription")
async def check_sub_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    if await check_joined(user_id):
        await callback.message.delete()
        if user_id in allowed_users:
            await callback.message.answer("✅ **سوپاس بۆ جۆینبوونەکەت!**\nئێستا دەتوانیت بۆتەکە بەکاربێنیت.", reply_markup=get_main_keyboard(user_id))
        else:
            await callback.message.answer("❌ **تۆ جۆین بوویت، بەڵام مافی بەکارهێنانی بۆتەکەت نییە.**")
    else:
        await callback.answer("❌ هێشتا جۆینی کەناڵ نەبوویت! تکایە پێشتر جۆین ببە.", show_alert=True)

# ==========================================
# 🔎 گەڕان بەدوای یوزەرنەیام (SEARCH USER)
# ==========================================
@dp.callback_query(F.data == "search_user")
async def ask_username(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in allowed_users:
        await callback.answer("⛔️ تۆ مافی بەکارهێنانی ئەم بەشەت نییە!", show_alert=True)
        return
    
    await callback.message.answer("✏️ **تکایە یوزەرنەیامی کەسی مەبەست بنێرە:**\n(بێ نیشانەی `@` یاخود بە نیشانەی `@`وە)")
    await state.set_state(Form.waiting_for_username)

@dp.message(Form.waiting_for_username)
async def process_username(message: Message, state: FSMContext):
    username = message.text.replace("@", "").strip()
    status_msg = await message.answer("⏳ **تکایە چاوەڕێ بکە... زانیارییەکان لە وەرگرتندان...**")

    try:
        # هێنانی زانیاری ڕاستەوخۆ بە Pyrogram
        user = await user_client.get_users(username)
        
        user_id = user.id
        first_name = user.first_name or "دیاری نەکراو"
        last_name = user.last_name or ""
        phone = user.phone_number if user.phone_number else "شاردراوەتەوە / دیار نییە"
        
        # هێنانی گروپە هەوبەشەکان
        common_chats = await user_client.get_common_chats(user_id)
        common_groups_text = "\n".join([f"• {chat.title}" for chat in common_chats]) if common_chats else "هیچ گروپێکی هەوبەش نۆزرایەوە"

        report = (
            f"👤 **زانیارییە تێروتەسەلەکانی بەکارهێنەر:**\n\n"
            f"🆔 **ئایدی (ID):** `{user_id}`\n"
            f"✏️ **ناو:** {first_name} {last_name}\n"
            f"🔗 **یوزەرنەیام:** @{user.username if user.username else 'نییەتی'}\n"
            f"📞 **ژمارەی تەلەفۆن:** `{phone}`\n\n"
            f"👥 **گروپە هەوبەشەکان ({len(common_chats)}):**\n{common_groups_text}\n\n"
            f"📢 **کەناڵ/گروپە دروستکراوەکان و جۆینبووەکان:**\n"
            f"*(ئەو کەناڵانەی بە ئاشکرا دیارن)*"
        )

        # دابەزاندنی وێنەی پڕۆفایل (ئەگەر هەبێت)
        photos = [p async for p in user_client.get_chat_photos(user_id, limit=1)]
        if photos:
            photo_path = await user_client.download_media(photos[0].file_id)
            await message.answer_photo(photo=FSInputFile(photo_path), caption=report, parse_mode="Markdown")
            os.remove(photo_path)
        else:
            await message.answer(report, parse_mode="Markdown")

        await status_msg.delete()

    except Exception as e:
        await status_msg.edit_text(f"❌ **هەڵەیەک ڕوویدا:**\nکەسەکە نەدۆزرایەوە یاخود یوزەرنەیامەکە هەڵەیە.\n`{str(e)}`", parse_mode="Markdown")
    
    await state.clear()

# ==========================================
# ⚙️ پانێڵی بەڕێوەبەر (ADMIN PANEL)
# ==========================================
@dp.callback_query(F.data == "admin_panel")
async def admin_panel(callback: CallbackQuery):
    if callback.from_user.id != MAIN_ADMIN_ID:
        await callback.answer("⛔️ ئەم بەشە تەنها بۆ خاوەنی سەرەکی بۆتەکەیە!", show_alert=True)
        return

    admin_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ زیایدکردنی ڕێگەپێدان (Add Access)", callback_data="add_access")],
        [InlineKeyboardButton(text="📋 لیستی کەسانی ڕێگەپێدراو", callback_data="list_access")],
        [InlineKeyboardButton(text="📊 ئاماری بۆت (Stats)", callback_data="bot_stats")],
        [InlineKeyboardButton(text="📢 ناردنی پەیام (Broadcast)", callback_data="broadcast")]
    ])
    
    await callback.message.answer("⚙️ **بەخێربێیت بۆ پانێڵی بەڕێوەبەری Y7_KRD:**", reply_markup=admin_kb)

@dp.callback_query(F.data == "add_access")
async def grant_access_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != MAIN_ADMIN_ID:
        return
    await callback.message.answer("🔢 **تکایە ئایدی (ID) ئۆ ئەو کەسە بنێرە کە دەتەوێت مافی بەکارهێنانی بۆتی بپێبدرێت:**")
    await state.set_state(Form.waiting_for_grant_id)

@dp.message(Form.waiting_for_grant_id)
async def grant_access_finish(message: Message, state: FSMContext):
    try:
        new_id = int(message.text.strip())
        allowed_users.add(new_id)
        await message.answer(f"✅ **بە سەرکەوتوویی مافی بەکارهێنان بە ئایدی `{new_id}` درا.**", parse_mode="Markdown")
    except ValueError:
        await message.answer("❌ **ئایدی هەڵەیە! تکایە تەنها ژمارە بنێرە.**")
    
    await state.clear()

@dp.callback_query(F.data == "list_access")
async def list_allowed_users(callback: CallbackQuery):
    users_str = "\n".join([f"• `{uid}`" for uid in allowed_users])
    await callback.message.answer(f"📋 **لیستی ئەو ئایدییانەی مافی بەکارهێنانیان هەیە:**\n\n{users_str}", parse_mode="Markdown")

@dp.callback_query(F.data == "bot_stats")
async def show_stats(callback: CallbackQuery):
    msg = f"📊 **ئامارەکانی بۆت:**\n\n👥 **کۆی بەکارهێنەران:** {len(all_users_db)}\n🔑 **کەسانی ڕێگەپێدراو:** {len(allowed_users)}"
    await callback.message.answer(msg, parse_mode="Markdown")

@dp.callback_query(F.data == "broadcast")
async def ask_broadcast_msg(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != MAIN_ADMIN_ID:
        return
    await callback.message.answer("📢 **تکایە ئەو دەقە بنێرە کە دەتەوێت بۆ هەموو بەکارهێنەران بڕوات:**")
    await state.set_state(Form.waiting_for_broadcast)

@dp.message(Form.waiting_for_broadcast)
async def send_broadcast(message: Message, state: FSMContext):
    count = 0
    for uid in all_users_db:
        try:
            await bot.send_message(chat_id=uid, text=message.text)
            count += 1
        except Exception:
            pass
    await message.answer(f"✅ **پەیامەکە ب سەرکەوتوویی بۆ {count} کەس نێردرا.**")
    await state.clear()

# ==========================================
# 🏁 RUNNING THE BOT
# ==========================================
async def main():
    await user_client.start()
    print("🤖 Y7_KRD Bot is running successfully...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
