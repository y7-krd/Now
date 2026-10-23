import asyncio
import logging
import os
import sqlite3
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message, FSInputFile
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from pyrogram import Client

# ==========================================
# ⚙️ ڕێکخستنەکان (CONFIGURATIONS)
# ==========================================
BOT_TOKEN = "8673929801:AAFTZ0Y99erugl-_wZZFkGj3oa4maYBmIcI"
CHANNEL_USERNAME = "dev_y7_krd"         # ئایدی کەناڵ بێ @
MAIN_ADMIN_ID = 7643191802               # ئایدی سەرەکی خاوەن بۆت

API_ID = 34584240                        
API_HASH = "eba4f8333cba5f9697a1d20779d4d6e9"

# ==========================================
# 💾 SQLite DATABASE SYSTEM
# ==========================================
DB_PATH = "bot_database.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # خشتەی بەکارهێنەرانی ڕێگەپێدراو (Access Table)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS allowed_users (
            user_id INTEGER PRIMARY KEY,
            expire_time TEXT
        )
    ''')
    
    # خشتەی کەسانی بانکراو (Banned Users)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS banned_users (
            user_id INTEGER PRIMARY KEY
        )
    ''')
    
    # خشتەی هەموو بەکارهێنەرانی بۆت
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS all_users (
            user_id INTEGER PRIMARY KEY
        )
    ''')
    
    # زیایدکردنی ئادۆمینی سەرەکی بێ بەسەرچوون
    cursor.execute('INSERT OR IGNORE INTO allowed_users (user_id, expire_time) VALUES (?, ?)', (MAIN_ADMIN_ID, "NEVER"))
    conn.commit()
    conn.close()

init_db()

def is_user_banned(user_id: int) -> bool:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM banned_users WHERE user_id = ?', (user_id,))
    res = cursor.fetchone()
    conn.close()
    return res is not None

def is_user_allowed(user_id: int) -> bool:
    if user_id == MAIN_ADMIN_ID:
        return True
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT expire_time FROM allowed_users WHERE user_id = ?', (user_id,))
    res = cursor.fetchone()
    
    if not res:
        conn.close()
        return False
        
    expire_str = res[0]
    if expire_str == "NEVER":
        conn.close()
        return True
        
    expire_dt = datetime.strptime(expire_str, "%Y-%m-%d %H:%M:%S")
    if datetime.now() > expire_dt:
        # کاتەکەی بەسەرچووە، لایببە
        cursor.execute('DELETE FROM allowed_users WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
        return False
        
    conn.close()
    return True

def add_allowed_user(user_id: int, duration_str: str = "NEVER"):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    expire_val = "NEVER"
    if duration_str != "NEVER":
        unit = duration_str[-1].lower()
        val = int(duration_str[:-1])
        now = datetime.now()
        if unit == 'm':
            expire_dt = now + timedelta(minutes=val)
        elif unit == 'h':
            expire_dt = now + timedelta(hours=val)
        elif unit == 'd':
            expire_dt = now + timedelta(days=val)
        else:
            expire_dt = now + timedelta(days=val)
        expire_val = expire_dt.strftime("%Y-%m-%d %H:%M:%S")
        
    cursor.execute('INSERT OR REPLACE INTO allowed_users (user_id, expire_time) VALUES (?, ?)', (user_id, expire_val))
    conn.commit()
    conn.close()

def remove_allowed_user(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM allowed_users WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

def ban_user_db(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO banned_users (user_id) VALUES (?)', (user_id,))
    cursor.execute('DELETE FROM allowed_users WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

def unban_user_db(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM banned_users WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

def register_user_db(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO all_users (user_id) VALUES (?)', (user_id,))
    conn.commit()
    conn.close()

# ==========================================
# 🚀 دەستپێکردنی BOT & CLIENT
# ==========================================
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

user_client = Client("info_session", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ==========================================
# 🛑 FSM STATES
# ==========================================
class Form(StatesGroup):
    waiting_for_username = State()
    waiting_for_grant_input = State()
    waiting_for_revoke_input = State()
    waiting_for_ban_input = State()
    waiting_for_unban_input = State()
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
    register_user_db(user_id)
    
    # 1. پشکنینی بان بوون
    if is_user_banned(user_id):
        await message.answer("⛔️ **تۆ ڕاگیراویت (Ban) لە بەکارهێنانی ئەم بۆتە.**")
        return

    # 2. پشکنینی جۆینکردنی کەناڵ
    if not await check_joined(user_id):
        await message.answer(
            f"⚠️ **سڵاو بەڕێز!**\n\nبۆ بەکارهێنانی ئەم بۆتە، پێویستە سەرەتا جۆینی کەناڵی فەرمی ئێمە بێت:\n👉 @{CHANNEL_USERNAME}",
            reply_markup=get_join_keyboard(),
            parse_mode="Markdown"
        )
        return

    # 3. پشکنینی مافی بەکارهێنان
    if not is_user_allowed(user_id):
        req_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📩 داواکردنی مافی بەکارهێنان", callback_data="request_access")]
        ])
        await message.answer(
            "❌ **داواکاری ڕەتکرایەوە!**\nئێوە مافی بەکارهێنانی ئەم بۆتەتان نییە.\nدەتتوانیت ڕاستەوخۆ داواکاری بنێریت بۆ بەڕێوەبەر:",
            reply_markup=req_kb
        )
        return

    # 4. چوونه ژوورەوە بۆ کەسانی ڕێگەپێدراو
    await message.answer(
        f"🌹 **سڵاو بەڕێز {message.from_user.first_name}!**\n\nبه‌خێربێیت بۆ **Y7_KRD INFO BOT**. تکایە بژاردەیەک هەڵبژێرە:",
        reply_markup=get_main_keyboard(user_id)
    )

@dp.callback_query(F.data == "check_subscription")
async def check_sub_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    if is_user_banned(user_id):
        await callback.answer("⛔️ تۆ بان کراویت!", show_alert=True)
        return

    if await check_joined(user_id):
        await callback.message.delete()
        if is_user_allowed(user_id):
            await callback.message.answer("✅ **سوپاس بۆ جۆینبوونەکەت!**\nئێستا دەتوانیت بۆتەکە بەکاربێنیت.", reply_markup=get_main_keyboard(user_id))
        else:
            req_kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📩 داواکردنی مافی بەکارهێنان", callback_data="request_access")]
            ])
            await callback.message.answer("❌ **تۆ جۆین بوویت، بەڵام مافی بەکارهێنانی بۆتەکەت نییە.**", reply_markup=req_kb)
    else:
        await callback.answer("❌ هێشتا جۆینی کەناڵ نەبوویت!", show_alert=True)

# ==========================================
# 📩 سیستەمی داواکاری (REQUEST ACCESS)
# ==========================================
@dp.callback_query(F.data == "request_access")
async def send_request_to_admin(callback: CallbackQuery):
    user = callback.from_user
    if is_user_banned(user.id):
        await callback.answer("⛔️ تۆ رێگەپێدراو نییت!", show_alert=True)
        return

    # ناردنی پەیام بۆ ئادۆمین
    admin_action_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ قبوڵکردن (1 مانگ)", callback_data=f"approve_{user.id}_30d"),
            InlineKeyboardButton(text="♾️ بەکارهێنانی هەتاهەتایی", callback_data=f"approve_{user.id}_never")
        ],
        [InlineKeyboardButton(text="❌ ڕەتکردنەوە", callback_data=f"reject_{user.id}")]
    ])
    
    req_msg = (
        f"📥 **داواکاری نوێ بۆ بەکارهێنانی بۆت!**\n\n"
        f"👤 **ناو:** {user.first_name} {user.last_name or ''}\n"
        f"🔗 **یوزەرنەیام:** @{user.username if user.username else 'نییەتی'}\n"
        f"🆔 **ئایدی (ID):** `{user.id}`"
    )
    
    try:
        await bot.send_message(chat_id=MAIN_ADMIN_ID, text=req_msg, reply_markup=admin_action_kb, parse_mode="Markdown")
        await callback.answer("✅ داواکارییەکەت ڕەوانەی بەڕێوەبەر کرا.", show_alert=True)
        await callback.message.edit_text("⏳ **داواکارییەکەت نێردرا. تکایە چاوەڕوانی وەڵامی بەڕێوەبەر بە.**")
    except Exception:
        await callback.answer("❌ هەڵەیەک ڕوویدا لە ناردنی داواکاری.", show_alert=True)

@dp.callback_query(F.data.startswith("approve_"))
async def approve_user_req(callback: CallbackQuery):
    if callback.from_user.id != MAIN_ADMIN_ID:
        return
    
    parts = callback.data.split("_")
    target_id = int(parts[1])
    dur = parts[2]
    
    add_allowed_user(target_id, "NEVER" if dur == "never" else "30d")
    
    await callback.message.edit_text(callback.message.text + f"\n\n✅ **داواکاریەکە قبوڵکرا! ({dur})**")
    try:
        await bot.send_message(chat_id=target_id, text="🎉 **بەخێر بەیت! داواکاری بەکارهێنانی بۆتەکەت لەلایەن بەڕێوەبەرەوە قبوڵکرا.**\nدەتتوانیت بژاردەی /start لێبده‌یت.")
    except Exception:
        pass

@dp.callback_query(F.data.startswith("reject_"))
async def reject_user_req(callback: CallbackQuery):
    if callback.from_user.id != MAIN_ADMIN_ID:
        return
    
    target_id = int(callback.data.split("_")[1])
    await callback.message.edit_text(callback.message.text + "\n\n❌ **داواکاریەکە ڕەتکرایەوە.**")
    try:
        await bot.send_message(chat_id=target_id, text="❌ **داواکاری بەکارهێنانی بۆتەکەت ڕەتکرایەوە.**")
    except Exception:
        pass

# ==========================================
# 🔎 گەڕان بەدوای یوزەرنەیام (SEARCH USER)
# ==========================================
@dp.callback_query(F.data == "search_user")
async def ask_username(callback: CallbackQuery, state: FSMContext):
    if not is_user_allowed(callback.from_user.id):
        await callback.answer("⛔️ تۆ مافی بەکارهێنانی ئەم بەشەت نییە!", show_alert=True)
        return
    
    await callback.message.answer("✏️ **تکایە یوزەرنەیامی کەسی مەبەست بنێرە:**\n(بێ نیشانەی `@` یاخود بە نیشانەی `@`وە)")
    await state.set_state(Form.waiting_for_username)

@dp.message(Form.waiting_for_username)
async def process_username(message: Message, state: FSMContext):
    username = message.text.replace("@", "").strip()
    status_msg = await message.answer("⏳ **تکایە چاوەڕێ بکە... زانیارییەکان لە وەرگرتندان...**")

    try:
        user = await user_client.get_users(username)
        
        user_id = user.id
        first_name = user.first_name or "دیاری نەکراو"
        last_name = user.last_name or ""
        phone = user.phone_number if user.phone_number else "شاردراوەتەوە / دیار نییە"
        
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

        photos = [p async for p in user_client.get_chat_photos(user_id, limit=1)]
        if photos:
            photo_path = await user_client.download_media(photos[0].file_id)
            await message.answer_photo(photo=FSInputFile(photo_path), caption=report, parse_mode="Markdown")
            if os.path.exists(photo_path):
                os.remove(photo_path)
        else:
            await message.answer(report, parse_mode="Markdown")

        await status_msg.delete()

    except Exception as e:
        await status_msg.edit_text(f"❌ **هەڵەیەک ڕوویدا:**\nکەسەکە نەدۆزرایەوە یاخود یوزەرنەیامەکە هەڵەیە.\n`{str(e)}`", parse_mode="Markdown")
    
    await state.clear()

# ==========================================
# ⚙️ پانێڵی بەڕێوەبەر (POWERFUL ADMIN PANEL)
# ==========================================
@dp.callback_query(F.data == "admin_panel")
async def admin_panel(callback: CallbackQuery):
    if callback.from_user.id != MAIN_ADMIN_ID:
        await callback.answer("⛔️ ئەم بەشە تەنها بۆ خاوەنی سەرەکی بۆتەکەیە!", show_alert=True)
        return

    admin_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ زیایدکردنی ماف (Add Access)", callback_data="add_access"), InlineKeyboardButton(text="➖ لابردنی ماف (Revoke)", callback_data="revoke_access")],
        [InlineKeyboardButton(text="⛔️ بانکردن (Ban User)", callback_data="ban_user"), InlineKeyboardButton(text="🟢 لابردنی بان (Unban)", callback_data="unban_user")],
        [InlineKeyboardButton(text="📋 لیستی ڕێگەپێدراوەکان", callback_data="list_access"), InlineKeyboardButton(text="📊 ئامارەکان (Stats)", callback_data="bot_stats")],
        [InlineKeyboardButton(text="📢 ناردنی پەیام (Broadcast)", callback_data="broadcast")]
    ])
    
    await callback.message.answer("⚙️ **بەخێربێیت بۆ پانێڵی بەڕێوەبەری سەرەکی Y7_KRD:**", reply_markup=admin_kb)

# --- Add Access ---
@dp.callback_query(F.data == "add_access")
async def grant_access_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != MAIN_ADMIN_ID: return
    await callback.message.answer("🔢 **تکایە ID یاخود Username ی کەسەکە بنێرە، دابڕاوی لەگەڵ کات (ئارەزوومەندانە):**\n\n**نموونەکان:**\n• `123456789` (هەتاهەتایی)\n• `123456789 30d` (بۆ ٣٠ ڕۆژ)\n• `@username 7d` (بۆ ٧ ڕۆژ)\n• `@username 12h` (بۆ ١٢ کاژێر)")
    await state.set_state(Form.waiting_for_grant_input)

@dp.message(Form.waiting_for_grant_input)
async def grant_access_finish(message: Message, state: FSMContext):
    parts = message.text.strip().split()
    target = parts[0]
    duration = parts[1] if len(parts) > 1 else "NEVER"
    
    target_id = None
    if target.isdigit():
        target_id = int(target)
    else:
        try:
            u = await user_client.get_users(target)
            target_id = u.id
        except Exception:
            await message.answer("❌ **یوزەرنەیام یان ئایدی هەڵەیە!**")
            await state.clear()
            return
            
    add_allowed_user(target_id, duration)
    await message.answer(f"✅ **مافی بەکارهێنان بە ئایدی `{target_id}` درا.**\n⏱ ماوە: `{duration}`", parse_mode="Markdown")
    await state.clear()

# --- Revoke Access ---
@dp.callback_query(F.data == "revoke_access")
async def revoke_access_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != MAIN_ADMIN_ID: return
    await callback.message.answer("🗑 **ئایدی یاخود یوزەرنەیامی ئەو کەسە بنێرە کە دەتەوێت مافەکەی لێبستێنیتەوە:**")
    await state.set_state(Form.waiting_for_revoke_input)

@dp.message(Form.waiting_for_revoke_input)
async def revoke_access_finish(message: Message, state: FSMContext):
    target = message.text.strip()
    target_id = None
    if target.isdigit():
        target_id = int(target)
    else:
        try:
            u = await user_client.get_users(target)
            target_id = u.id
        except Exception:
            await message.answer("❌ **یوزەرنەیام یان ئایدی هەڵەیە!**")
            await state.clear()
            return
            
    remove_allowed_user(target_id)
    await message.answer(f"✅ **مافی بەکارهێنان لە ئایدی `{target_id}` سەندرایەوە.**", parse_mode="Markdown")
    await state.clear()

# --- Ban User ---
@dp.callback_query(F.data == "ban_user")
async def ban_user_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != MAIN_ADMIN_ID: return
    await callback.message.answer("⛔️ **ئایدی یاخود یوزەرنەیامی ئەو کەسە بنێرە کە دەتەوێت بان (Ban) بێت:**")
    await state.set_state(Form.waiting_for_ban_input)

@dp.message(Form.waiting_for_ban_input)
async def ban_user_finish(message: Message, state: FSMContext):
    target = message.text.strip()
    target_id = None
    if target.isdigit():
        target_id = int(target)
    else:
        try:
            u = await user_client.get_users(target)
            target_id = u.id
        except Exception:
            await message.answer("❌ **یوزەرنەیام یان ئایدی هەڵەیە!**")
            await state.clear()
            return
            
    ban_user_db(target_id)
    await message.answer(f"✅ **ئایدی `{target_id}` بە سەرکەوتوویی بان کرا.**", parse_mode="Markdown")
    await state.clear()

# --- Unban User ---
@dp.callback_query(F.data == "unban_user")
async def unban_user_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != MAIN_ADMIN_ID: return
    await callback.message.answer("🟢 **ئایدی یاخود یوزەرنەیامی ئەو کەسە بنێرە کە دەتەوێت دەربچێت لە بان (Unban):**")
    await state.set_state(Form.waiting_for_unban_input)

@dp.message(Form.waiting_for_unban_input)
async def unban_user_finish(message: Message, state: FSMContext):
    target = message.text.strip()
    target_id = None
    if target.isdigit():
        target_id = int(target)
    else:
        try:
            u = await user_client.get_users(target)
            target_id = u.id
        except Exception:
            await message.answer("❌ **یوزەرنەیام یان ئایدی هەڵەیە!**")
            await state.clear()
            return
            
    unban_user_db(target_id)
    await message.answer(f"✅ **ئایدی `{target_id}` لە بان دەرکرا.**", parse_mode="Markdown")
    await state.clear()

# --- List Access ---
@dp.callback_query(F.data == "list_access")
async def list_allowed_users_cb(callback: CallbackQuery):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, expire_time FROM allowed_users')
    rows = cursor.fetchall()
    conn.close()
    
    users_str = "\n".join([f"• `{r[0]}` | ماوە: `{r[1]}`" for r in rows]) if rows else "هیچ کەسێک دیاری نەکراوە."
    await callback.message.answer(f"📋 **لیستی ئەو کەسانەی مافی بەکارهێنانیان هەیە:**\n\n{users_str}", parse_mode="Markdown")

# --- Stats ---
@dp.callback_query(F.data == "bot_stats")
async def show_stats(callback: CallbackQuery):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM all_users')
    total_users = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM allowed_users')
    allowed_count = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM banned_users')
    banned_count = cursor.fetchone()[0]
    conn.close()

    msg = f"📊 **ئامارەکانی بۆتی Y7_KRD:**\n\n👥 **کۆی بەکارهێنەران:** {total_users}\n🔑 **کەسانی ڕێگەپێدراو:** {allowed_count}\n⛔️ **کەسانی بانکراو:** {banned_count}"
    await callback.message.answer(msg, parse_mode="Markdown")

# --- Broadcast ---
@dp.callback_query(F.data == "broadcast")
async def ask_broadcast_msg(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != MAIN_ADMIN_ID: return
    await callback.message.answer("📢 **تکایە ئەو دەقە بنێرە کە دەتەوێت بۆ هەموو بەکارهێنەران بڕوات:**")
    await state.set_state(Form.waiting_for_broadcast)

@dp.message(Form.waiting_for_broadcast)
async def send_broadcast(message: Message, state: FSMContext):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM all_users')
    rows = cursor.fetchall()
    conn.close()

    count = 0
    for r in rows:
        uid = r[0]
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
    print("🤖 Y7_KRD Bot is running with full power and SQLite persistence...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
