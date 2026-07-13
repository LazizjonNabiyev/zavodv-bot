import asyncio
import json
import logging
import os
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
)

import gspread
from google.oauth2.service_account import Credentials

# =========================================================
#                      SOZLAMALAR
# =========================================================
# MUHIM: Tokenlar va kalitlar kodga YOZILMAYDI!
# Ular Railway'ning "Variables" bo'limida muhit o'zgaruvchisi
# sifatida saqlanadi, kod esa ularni shu yerdan o'qiydi.
#
# Railway Variables bo'limiga qo'shiladigan nomlar:
#   BOT_TOKEN            -> BotFather'dan olingan token
#   GOOGLE_SHEET_NAME     -> Google Sheets jadval nomi (ixtiyoriy, default bor)
#   GOOGLE_CREDENTIALS_JSON -> credentials.json faylining TO'LIQ MATNI

BOT_TOKEN = os.environ["BOT_TOKEN"].strip()
GOOGLE_SHEET_NAME = os.environ.get("GOOGLE_SHEET_NAME", "Zavod ishchilari")

# --- VAQTINCHALIK TEKSHIRUV: muammo topilgach o'chirib tashlanadi ---
print(f"[DEBUG] Token uzunligi: {len(BOT_TOKEN)}")
print(f"[DEBUG] Boshi: {BOT_TOKEN[:6]!r}  Oxiri: {BOT_TOKEN[-6:]!r}")
print(f"[DEBUG] ':' bormi: {':' in BOT_TOKEN}")
# ------------------------------------------------------------------

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# =========================================================
#                 GOOGLE SHEETS ULANISH
# =========================================================

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# credentials.json ning ichidagi matn to'g'ridan-to'g'ri
# GOOGLE_CREDENTIALS_JSON muhit o'zgaruvchisidan olinadi
credentials_info = json.loads(os.environ["GOOGLE_CREDENTIALS_JSON"])
creds = Credentials.from_service_account_info(credentials_info, scopes=SCOPES)
gc = gspread.authorize(creds)
sheet = gc.open(GOOGLE_SHEET_NAME).sheet1

# Agar jadval bo'sh bo'lsa, sarlavhalarni qo'yamiz
HEADERS = [
    "Sana",
    "Telegram ID",
    "Username",
    "Ism",
    "Familiya",
    "Yosh",
    "Amal",
    "Lavozim",
    "Sabab",
]
if sheet.row_values(1) != HEADERS:
    sheet.insert_row(HEADERS, 1)


def add_row_to_sheet(data: dict):
    """Google Sheets'ga yangi qator qo'shadi (real-time)."""
    row = [
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        data.get("user_id", ""),
        data.get("username", ""),
        data.get("ism", ""),
        data.get("familiya", ""),
        data.get("yosh", ""),
        data.get("amal", ""),
        data.get("lavozim", "-"),
        data.get("sabab", ""),
    ]
    sheet.append_row(row, value_input_option="USER_ENTERED")


# =========================================================
#                       HOLATLAR (FSM)
# =========================================================

class Registration(StatesGroup):
    ism = State()
    familiya = State()
    yosh = State()


class Ketish(StatesGroup):
    sabab = State()
    sabab_matn = State()


class YangiIsh(StatesGroup):
    lavozim = State()
    lavozim_matn = State()


# =========================================================
#                       KLAVIATURALAR
# =========================================================

main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🆕 Yangi ishga kirish")],
        [KeyboardButton(text="🚪 Ishdan ketish / bo'shash")],
    ],
    resize_keyboard=True,
)

lavozim_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🔧 Ishchi")],
        [KeyboardButton(text="⚙️ Usta / Ustaxona boshlig'i")],
        [KeyboardButton(text="🧑‍💼 Muhandis")],
        [KeyboardButton(text="🚚 Haydovchi")],
        [KeyboardButton(text="🛡️ Qorovul")],
        [KeyboardButton(text="📦 Ombor xodimi")],
        [KeyboardButton(text="✍️ Boshqa (o'zim yozaman)")],
    ],
    resize_keyboard=True,
)

sabab_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="💰 Maosh past")],
        [KeyboardButton(text="🏭 Ish sharoiti yoqmadi")],
        [KeyboardButton(text="👨‍👩‍👧 Oilaviy sabablar")],
        [KeyboardButton(text="🏥 Sog'liq sababli")],
        [KeyboardButton(text="🧭 Boshqa ish topdim")],
        [KeyboardButton(text="✍️ Boshqa sabab (o'zim yozaman)")],
    ],
    resize_keyboard=True,
)


# =========================================================
#                       HANDLERLAR
# =========================================================

@dp.message(CommandStart())
async def start_handler(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Assalomu alaykum! Zavod xodimlari uchun botga xush kelibsiz.\n\n"
        "Ro'yxatdan o'tish uchun ismingizni kiriting:",
        reply_markup=ReplyKeyboardRemove(),
    )
    await state.set_state(Registration.ism)


@dp.message(Registration.ism)
async def get_ism(message: Message, state: FSMContext):
    await state.update_data(ism=message.text.strip())
    await message.answer("Familiyangizni kiriting:")
    await state.set_state(Registration.familiya)


@dp.message(Registration.familiya)
async def get_familiya(message: Message, state: FSMContext):
    await state.update_data(familiya=message.text.strip())
    await message.answer("Yoshingizni kiriting (faqat raqam):")
    await state.set_state(Registration.yosh)


@dp.message(Registration.yosh)
async def get_yosh(message: Message, state: FSMContext):
    if not message.text.strip().isdigit():
        await message.answer("Iltimos, yoshingizni faqat raqamda kiriting (masalan: 27):")
        return

    await state.update_data(yosh=message.text.strip())
    data = await state.get_data()

    await message.answer(
        f"Rahmat, {data['ism']}! Ro'yxatdan muvaffaqiyatli o'tdingiz ✅\n\n"
        "Quyidagilardan birini tanlang:",
        reply_markup=main_menu,
    )
    # Holatni to'liq tozalamaymiz - ism/familiya/yosh keyingi bosqichlarda kerak bo'ladi
    await state.set_state(None)


@dp.message(F.text == "🆕 Yangi ishga kirish")
async def yangi_ish(message: Message, state: FSMContext):
    data = await state.get_data()
    if "ism" not in data:
        await message.answer("Iltimos, avval /start orqali ro'yxatdan o'ting.")
        return

    await message.answer(
        "Qaysi lavozimga topshirmoqchisiz?",
        reply_markup=lavozim_menu,
    )
    await state.set_state(YangiIsh.lavozim)


@dp.message(YangiIsh.lavozim, F.text == "✍️ Boshqa (o'zim yozaman)")
async def lavozim_ozi_yozadi(message: Message, state: FSMContext):
    await message.answer(
        "Lavozim nomini matn ko'rinishida yozing:",
        reply_markup=ReplyKeyboardRemove(),
    )
    await state.set_state(YangiIsh.lavozim_matn)


@dp.message(YangiIsh.lavozim_matn)
async def lavozim_matn_olish(message: Message, state: FSMContext):
    await yangi_ish_yakunlash(message, state, lavozim=message.text.strip())


@dp.message(YangiIsh.lavozim)
async def lavozim_tanlash(message: Message, state: FSMContext):
    await yangi_ish_yakunlash(message, state, lavozim=message.text.strip())


async def yangi_ish_yakunlash(message: Message, state: FSMContext, lavozim: str):
    data = await state.get_data()

    add_row_to_sheet(
        {
            "user_id": message.from_user.id,
            "username": message.from_user.username or "-",
            "ism": data.get("ism"),
            "familiya": data.get("familiya"),
            "yosh": data.get("yosh"),
            "amal": "Yangi ishga kirdi",
            "lavozim": lavozim,
            "sabab": "-",
        }
    )
    await message.answer(
        f"Tabriklaymiz! \"{lavozim}\" lavozimiga topshirganingiz qayd qilindi ✅",
        reply_markup=main_menu,
    )
    await state.set_state(None)


@dp.message(F.text == "🚪 Ishdan ketish / bo'shash")
async def ishdan_ketish(message: Message, state: FSMContext):
    data = await state.get_data()
    if "ism" not in data:
        await message.answer("Iltimos, avval /start orqali ro'yxatdan o'ting.")
        return

    await message.answer(
        "Ishdan ketish sababini tanlang:",
        reply_markup=sabab_menu,
    )
    await state.set_state(Ketish.sabab)


@dp.message(Ketish.sabab, F.text == "✍️ Boshqa sabab (o'zim yozaman)")
async def sabab_ozi_yozadi(message: Message, state: FSMContext):
    await message.answer(
        "Sababni matn ko'rinishida yozing:",
        reply_markup=ReplyKeyboardRemove(),
    )
    await state.set_state(Ketish.sabab_matn)


@dp.message(Ketish.sabab_matn)
async def sabab_matn_olish(message: Message, state: FSMContext):
    await yozish_va_yakunlash(message, state, sabab=message.text.strip())


@dp.message(Ketish.sabab)
async def sabab_tanlash(message: Message, state: FSMContext):
    await yozish_va_yakunlash(message, state, sabab=message.text.strip())


async def yozish_va_yakunlash(message: Message, state: FSMContext, sabab: str):
    data = await state.get_data()

    add_row_to_sheet(
        {
            "user_id": message.from_user.id,
            "username": message.from_user.username or "-",
            "ism": data.get("ism"),
            "familiya": data.get("familiya"),
            "yosh": data.get("yosh"),
            "amal": "Ishdan ketmoqchi",
            "sabab": sabab,
        }
    )

    await message.answer(
        "Rahmat! Javobingiz qayd qilindi. Tez orada siz bilan bog'lanishadi 🙏",
        reply_markup=main_menu,
    )
    await state.set_state(None)


# =========================================================
#                       ISHGA TUSHIRISH
# =========================================================

async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
