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
#   BOT_TOKEN               -> BotFather'dan olingan token
#   GOOGLE_SHEET_NAME        -> Google Sheets jadval nomi (ID berilmasa ishlatiladi)
#   GOOGLE_SHEET_ID          -> Google Sheets jadval ID (tavsiya etiladi, eng ishonchli)
#   GOOGLE_CREDENTIALS_JSON  -> credentials.json faylining TO'LIQ MATNI

BOT_TOKEN = os.environ["BOT_TOKEN"].strip()
GOOGLE_SHEET_NAME = os.environ.get("GOOGLE_SHEET_NAME", "Zavod ishchilari")
GOOGLE_SHEET_ID = os.environ.get("GOOGLE_SHEET_ID", "").strip()

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

credentials_info = json.loads(os.environ["GOOGLE_CREDENTIALS_JSON"])
creds = Credentials.from_service_account_info(credentials_info, scopes=SCOPES)
gc = gspread.authorize(creds)

# GOOGLE_SHEET_ID berilgan bo'lsa ID orqali (eng ishonchli), aks holda nomi orqali ochamiz
print(f"[DEBUG] GOOGLE_SHEET_ID uzunligi: {len(GOOGLE_SHEET_ID)}")
if GOOGLE_SHEET_ID:
    print("[DEBUG] ID orqali ulanmoqda...")
    sheet = gc.open_by_key(GOOGLE_SHEET_ID).sheet1
else:
    print(f"[DEBUG] Nom orqali ulanmoqda: {GOOGLE_SHEET_NAME!r}")
    sheet = gc.open(GOOGLE_SHEET_NAME).sheet1


# Agar jadval bo'sh bo'lsa, sarlavhalarni qo'yamiz
HEADERS = [
    "Sana",
    "Telefon",
    "Telegram ID",
    "Username",
    "Ism",
    "Familiya",
    "Yosh",
    "Holat",
    "Amal",
    "Lavozim",
    "Filial",
    "Murojaat turi",
    "Xabar / Sabab",
]
if sheet.row_values(1) != HEADERS:
    sheet.insert_row(HEADERS, 1)


def add_row_to_sheet(data: dict):
    """Google Sheets'ga yangi qator qo'shadi (real-time)."""
    row = [
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        data.get("telefon", "-"),
        data.get("user_id", ""),
        data.get("username", ""),
        data.get("ism", ""),
        data.get("familiya", ""),
        data.get("yosh", ""),
        data.get("holat", "-"),
        data.get("amal", ""),
        data.get("lavozim", "-"),
        data.get("filial", "-"),
        data.get("murojaat_turi", "-"),
        data.get("xabar", "-"),
    ]
    sheet.append_row(row, value_input_option="USER_ENTERED")


# =========================================================
#                       HOLATLAR (FSM)
# =========================================================

class Registration(StatesGroup):
    telefon = State()
    filial = State()
    ism = State()
    familiya = State()
    yosh = State()
    holat = State()
    lavozim = State()
    lavozim_matn = State()


class Ketish(StatesGroup):
    filial = State()
    sabab = State()
    sabab_matn = State()


class TaklifShikoyat(StatesGroup):
    filial = State()
    turi = State()
    matn = State()


# =========================================================
#                       KLAVIATURALAR
# =========================================================

telefon_menu = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="📱 Raqamni yuborish", request_contact=True)]],
    resize_keyboard=True,
    one_time_keyboard=True,
)

holat_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="✅ Hozir ishlayapman")],
        [KeyboardButton(text="🆕 Yangi ishga kirmoqchiman")],
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

main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🚪 Ishdan ketish / bo'shash")],
        [KeyboardButton(text="💬 Taklif va shikoyat")],
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

filial_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Bektemir")],
        [KeyboardButton(text="Bo'ka")],
        [KeyboardButton(text="Parkent")],
    ],
    resize_keyboard=True,
)

murojaat_turi_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="💡 Taklif")],
        [KeyboardButton(text="⚠️ Shikoyat")],
    ],
    resize_keyboard=True,
)


# =========================================================
#                HANDLERLAR — RO'YXATDAN O'TISH
# =========================================================

@dp.message(CommandStart())
async def start_handler(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Assalomu alaykum! Zavod xodimlari uchun botga xush kelibsiz.\n\n"
        "Ro'yxatdan o'tish uchun telefon raqamingizni yuboring:",
        reply_markup=telefon_menu,
    )
    await state.set_state(Registration.telefon)


@dp.message(Registration.telefon, F.contact)
async def get_telefon(message: Message, state: FSMContext):
    await state.update_data(telefon=message.contact.phone_number)
    await message.answer(
        "Rahmat! Qaysi filialga tegishlisiz?",
        reply_markup=filial_menu,
    )
    await state.set_state(Registration.filial)


@dp.message(Registration.telefon)
async def telefon_notogri(message: Message, state: FSMContext):
    await message.answer(
        "Iltimos, pastdagi \"📱 Raqamni yuborish\" tugmasini bosib, raqamingizni yuboring."
    )


@dp.message(Registration.filial, F.text.in_({"Bektemir", "Bo'ka", "Parkent"}))
async def reg_filial_olindi(message: Message, state: FSMContext):
    await state.update_data(filial=message.text.strip())
    await message.answer(
        "Ismingizni kiriting:",
        reply_markup=ReplyKeyboardRemove(),
    )
    await state.set_state(Registration.ism)


@dp.message(Registration.filial)
async def reg_filial_notogri(message: Message, state: FSMContext):
    await message.answer("Iltimos, pastdagi tugmalardan filialni tanlang.")


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
    await message.answer(
        "Siz hozir zavodda ishlaysizmi yoki yangi ishga kirmoqchimisiz?",
        reply_markup=holat_menu,
    )
    await state.set_state(Registration.holat)


@dp.message(Registration.holat, F.text == "✅ Hozir ishlayapman")
async def holat_ishlayapman(message: Message, state: FSMContext):
    await state.update_data(holat="Hozir ishlayapti")
    data = await state.get_data()

    add_row_to_sheet(
        {
            "telefon": data.get("telefon"),
            "user_id": message.from_user.id,
            "username": message.from_user.username or "-",
            "ism": data.get("ism"),
            "familiya": data.get("familiya"),
            "yosh": data.get("yosh"),
            "holat": "Hozir ishlayapti",
            "amal": "Ro'yxatdan o'tdi",
            "filial": data.get("filial", "-"),
        }
    )

    await message.answer(
        f"Rahmat, {data['ism']}! Ro'yxatdan muvaffaqiyatli o'tdingiz ✅\n\n"
        "Quyidagilardan birini tanlang:",
        reply_markup=main_menu,
    )
    await state.set_state(None)


@dp.message(Registration.holat, F.text == "🆕 Yangi ishga kirmoqchiman")
async def holat_yangi_ish(message: Message, state: FSMContext):
    await state.update_data(holat="Yangi ishga kirmoqchi")
    await message.answer(
        "Qaysi lavozimga topshirmoqchisiz?",
        reply_markup=lavozim_menu,
    )
    await state.set_state(Registration.lavozim)


@dp.message(Registration.holat)
async def holat_notogri(message: Message, state: FSMContext):
    await message.answer("Iltimos, pastdagi tugmalardan birini tanlang.")


@dp.message(Registration.lavozim, F.text == "✍️ Boshqa (o'zim yozaman)")
async def lavozim_ozi_yozadi(message: Message, state: FSMContext):
    await message.answer(
        "Lavozim nomini matn ko'rinishida yozing:",
        reply_markup=ReplyKeyboardRemove(),
    )
    await state.set_state(Registration.lavozim_matn)


@dp.message(Registration.lavozim_matn)
async def lavozim_matn_olish(message: Message, state: FSMContext):
    await lavozim_yakunlash(message, state, lavozim=message.text.strip())


@dp.message(Registration.lavozim)
async def lavozim_tanlash(message: Message, state: FSMContext):
    await lavozim_yakunlash(message, state, lavozim=message.text.strip())


async def lavozim_yakunlash(message: Message, state: FSMContext, lavozim: str):
    data = await state.get_data()

    add_row_to_sheet(
        {
            "telefon": data.get("telefon"),
            "user_id": message.from_user.id,
            "username": message.from_user.username or "-",
            "ism": data.get("ism"),
            "familiya": data.get("familiya"),
            "yosh": data.get("yosh"),
            "holat": "Yangi ishga kirmoqchi",
            "amal": "Ro'yxatdan o'tdi",
            "lavozim": lavozim,
            "filial": data.get("filial", "-"),
        }
    )

    await state.update_data(lavozim=lavozim)
    await message.answer(
        f"Rahmat, {data['ism']}! \"{lavozim}\" lavozimiga topshirganingiz qayd qilindi ✅\n\n"
        "Quyidagilardan birini tanlang:",
        reply_markup=main_menu,
    )
    await state.set_state(None)


# =========================================================
#              HANDLERLAR — ISHDAN KETISH
# =========================================================

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
    await ketish_yakunlash(message, state, sabab=message.text.strip())


@dp.message(Ketish.sabab)
async def sabab_tanlash(message: Message, state: FSMContext):
    await ketish_yakunlash(message, state, sabab=message.text.strip())


async def ketish_yakunlash(message: Message, state: FSMContext, sabab: str):
    data = await state.get_data()

    add_row_to_sheet(
        {
            "telefon": data.get("telefon"),
            "user_id": message.from_user.id,
            "username": message.from_user.username or "-",
            "ism": data.get("ism"),
            "familiya": data.get("familiya"),
            "yosh": data.get("yosh"),
            "holat": data.get("holat", "-"),
            "amal": "Ishdan ketmoqchi",
            "xabar": sabab,
        }
    )

    await message.answer(
        "Rahmat! Javobingiz qayd qilindi. Tez orada siz bilan bog'lanishadi 🙏",
        reply_markup=main_menu,
    )
    await state.set_state(None)


# =========================================================
#            HANDLERLAR — TAKLIF VA SHIKOYAT
# =========================================================

@dp.message(F.text == "💬 Taklif va shikoyat")
async def taklif_shikoyat(message: Message, state: FSMContext):
    data = await state.get_data()
    if "ism" not in data:
        await message.answer("Iltimos, avval /start orqali ro'yxatdan o'ting.")
        return

    await message.answer(
        "Qaysi filial bo'yicha murojaat qilmoqchisiz?",
        reply_markup=filial_menu,
    )
    await state.set_state(TaklifShikoyat.filial)


@dp.message(TaklifShikoyat.filial, F.text.in_({"Bektemir", "Bo'ka", "Parkent"}))
async def taklif_filial_olindi(message: Message, state: FSMContext):
    await state.update_data(filial=message.text.strip())
    await message.answer(
        "Murojaat turini tanlang:",
        reply_markup=murojaat_turi_menu,
    )
    await state.set_state(TaklifShikoyat.turi)


@dp.message(TaklifShikoyat.filial)
async def taklif_filial_notogri(message: Message, state: FSMContext):
    await message.answer("Iltimos, pastdagi tugmalardan filialni tanlang.")


@dp.message(TaklifShikoyat.turi, F.text.in_({"💡 Taklif", "⚠️ Shikoyat"}))
async def taklif_turi_olindi(message: Message, state: FSMContext):
    turi = "Taklif" if "Taklif" in message.text else "Shikoyat"
    await state.update_data(murojaat_turi=turi)
    await message.answer(
        "Izohingizni (murojaat matnini) yozing:",
        reply_markup=ReplyKeyboardRemove(),
    )
    await state.set_state(TaklifShikoyat.matn)


@dp.message(TaklifShikoyat.turi)
async def taklif_turi_notogri(message: Message, state: FSMContext):
    await message.answer("Iltimos, pastdagi tugmalardan birini tanlang.")


@dp.message(TaklifShikoyat.matn)
async def taklif_matn_olish(message: Message, state: FSMContext):
    data = await state.get_data()

    add_row_to_sheet(
        {
            "telefon": data.get("telefon"),
            "user_id": message.from_user.id,
            "username": message.from_user.username or "-",
            "ism": data.get("ism"),
            "familiya": data.get("familiya"),
            "yosh": data.get("yosh"),
            "holat": data.get("holat", "-"),
            "amal": "Taklif / Shikoyat",
            "filial": data.get("filial", "-"),
            "murojaat_turi": data.get("murojaat_turi", "-"),
            "xabar": message.text.strip(),
        }
    )

    await message.answer(
        "Rahmat! Murojaatingiz qabul qilindi va qayd etildi ✅\n\n"
        "Yangi murojaat qoldirish uchun istalgan vaqtda /start bosishingiz mumkin.",
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
