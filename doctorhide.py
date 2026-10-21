#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
DoctorHide — обезличивание документов (PDF, DOCX, MD/TXT, изображения).

Что скрывается (по умолчанию — всё, что включено в профиле):
  person     ФИО (фамилия, имя, отчество)
  identity   документы личности: паспорт, водительское, загранпаспорт, военный билет,
             свидетельство о рождении, код подразделения
  codes      присвоенные коды: ИНН, КПП, ОГРН/ОГРНИП, ОКПО, ОКТМО, ОКАТО, ОКВЭД, СНИЛС, полис ОМС
  address    адреса проживания/регистрации
  realty     недвижимость и права на неё (собственность, аренда, кадастровый номер, площадь)
  contacts   телефоны, e-mail, мессенджеры
  bank       счета, карты, БИК, банк
  finance    доходы, зарплата, суммы, долги, кредиты, налоги
  property   движимое имущество: авто, VIN, госномер
  employment место работы и должность
  leisure    места отдыха: санатории, отели, курорты, туры
  birth      возраст и дата рождения
  kinship    родство
  org        наименования организаций
  docno      номера документов

Вывод:
  PDF        белые плашки, исходный текст под ними удалён (apply_redactions);
             остальное содержимое остаётся текстом — файл читается и ищется.
             Скан-страница без текстового слоя пересобирается из того же растра
             с выжженными областями (вёрстка 1:1).
  Изображения PNG/JPEG/TIFF — белые плашки выжигаются в пикселях, формат сохраняется.
  DOCX       конвертируется в Markdown, значения заменяются на [censored].
  MD/TXT     значения заменяются на [censored].

Выбор пользователя:
  --list-categories        показать категории и выйти
  --keep cat1,cat2         не скрывать эти категории
  --only cat1,cat2         скрывать только эти категории
  --ask                    показать, что найдено, и спросить, что оставить

Примеры:
  python doctorhide.py doc.pdf
  python doctorhide.py doc.pdf --ask
  python doctorhide.py паспорт.png --keep docno
  python doctorhide.py решение.pdf --mode judicial
  python doctorhide.py "docs/*.pdf"
"""

from __future__ import annotations

import argparse
import glob
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import pymupdf
from PIL import Image, ImageDraw

PLACEHOLDER = "[censored]"
SAFE_NAME = False
BAR_BORDER = True
TEXT_LAYER = True
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}

# --------------------------------------------------------------------------- #
#  Категории
# --------------------------------------------------------------------------- #

CATEGORIES: Dict[str, str] = {
    "person": "ФИО (фамилия, имя, отчество)",
    "identity": "Документы личности (паспорт, в/у, загранпаспорт, военный билет)",
    "codes": "Коды: ИНН, КПП, ОГРН, ОКПО, ОКТМО, ОКАТО, ОКВЭД, СНИЛС, ОМС",
    "address": "Адреса проживания и регистрации",
    "realty": "Недвижимость и права на неё (собственность, аренда)",
    "contacts": "Телефоны, e-mail, мессенджеры",
    "bank": "Банковские счета, карты, БИК",
    "finance": "Финансовое состояние: доходы, суммы, долги, кредиты",
    "property": "Имущество: авто, VIN, госномер",
    "employment": "Место работы и должность",
    "leisure": "Места отдыха: санатории, отели, курорты",
    "birth": "Возраст и дата рождения",
    "kinship": "Родство",
    "org": "Наименования организаций",
    "docno": "Номера документов",
}

# в судебных актах эти категории по умолчанию НЕ скрываются
JUDICIAL_KEEP = {"person", "org", "docno"}

# --------------------------------------------------------------------------- #
#  Справочники
# --------------------------------------------------------------------------- #

GIVEN_NAMES = set(
    """
    александр алексей анатолий андрей антон аркадий арсений артём артем богдан борис
    вадим валентин валерий василий вениамин виктор виталий владимир владислав всеволод
    вячеслав геннадий георгий герман глеб григорий давид даниил денис дмитрий евгений
    егор ефим захар иван игорь илья иннокентий кирилл константин лев леонид максим марат
    марк матвей михаил никита николай олег павел пётр петр платон роман ростислав руслан
    рустам савелий святослав семён семен сергей станислав степан тарас тимофей тимур
    фёдор федор филипп эдуард юрий яков ярослав
    александра алина алиса алла анастасия ангелина анна антонина валентина валерия вера
    вероника виктория галина дарья диана евгения екатерина елена елизавета зинаида зоя
    инна ирина карина ксения лариса лидия любовь людмила маргарита марина мария милана
    надежда наталья нина оксана ольга полина раиса светлана софия софья тамара татьяна
    ульяна эльвира юлия яна
    """.split()
)

CITY_STEMS = [
    ("Санкт[- ]Петербург", r"[а-яё]*"), ("СПб", ""), ("Петербург", r"[а-яё]*"),
    ("Москв", r"[а-яё]{0,2}"), ("Новосибирск", r"[а-яё]{0,2}"), ("Екатеринбург", r"[а-яё]{0,2}"),
    ("Казан", r"[ьияюе]{0,2}"), (r"Нижн\w+ Новгород", r"[а-яё]{0,3}"), ("Челябинск", r"[а-яё]{0,2}"),
    ("Самар", r"[аыуе]{0,2}"), ("Омск", r"[а-яё]{0,2}"), ("Ростов", r"[а-яё]{0,3}"),
    ("Уф", r"[аыуе]{0,1}"), ("Красноярск", r"[а-яё]{0,2}"), ("Воронеж", r"[а-яё]{0,2}"),
    ("Перм", r"[ьияюе]{0,2}"), ("Волгоград", r"[а-яё]{0,2}"), ("Краснодар", r"[а-яё]{0,2}"),
    ("Саратов", r"[а-яё]{0,2}"), ("Тюмен", r"[ьияюе]{0,2}"), ("Тольятти", ""),
    ("Ижевск", r"[а-яё]{0,2}"), ("Барнаул", r"[а-яё]{0,2}"), ("Ульяновск", r"[а-яё]{0,2}"),
    ("Иркутск", r"[а-яё]{0,2}"), ("Хабаровск", r"[а-яё]{0,2}"), ("Ярославл", r"[ьея]{0,2}"),
    ("Владивосток", r"[а-яё]{0,2}"), ("Махачкал", r"[аыуе]{0,2}"), ("Томск", r"[а-яё]{0,2}"),
    ("Оренбург", r"[а-яё]{0,2}"), ("Кемеров", r"[аоуе]{0,2}"), ("Новокузнецк", r"[а-яё]{0,2}"),
    ("Рязан", r"[ьияюе]{0,2}"), ("Астрахан", r"[ьияюе]{0,2}"), (r"Набережн\w+ Челн", r"[а-яё]{0,2}"),
    ("Пенз", r"[аыуе]{0,2}"), ("Липецк", r"[а-яё]{0,2}"), ("Тул", r"[аыуе]{0,2}"),
    ("Калининград", r"[а-яё]{0,2}"), ("Балаших", r"[аиуе]{0,2}"), ("Курск", r"[а-яё]{0,2}"),
    ("Севастопол", r"[ьея]{0,2}"), ("Сочи", ""), ("Ставропол", r"[ьея]{0,2}"),
    ("Улан-Удэ", ""), ("Твер", r"[ьияюе]{0,2}"), ("Магнитогорск", r"[а-яё]{0,2}"),
    ("Иванов", r"[ое]"), ("Брянск", r"[а-яё]{0,2}"), ("Сургут", r"[а-яё]{0,2}"),
    ("Владимир", r"[а-яё]{0,2}"), ("Архангельск", r"[а-яё]{0,2}"), ("Чита", r"[а-яё]{0,2}"),
    ("Калуг", r"[аиуе]{0,2}"), ("Смоленск", r"[а-яё]{0,2}"), ("Волжск", r"[а-яё]{0,2}"),
    ("Курган", r"[а-яё]{0,2}"), ("Череповец", r"[а-яё]{0,2}"), ("Вологд", r"[аыуе]{0,2}"),
    ("Саранск", r"[а-яё]{0,2}"), ("Владикавказ", r"[а-яё]{0,2}"), ("Мурманск", r"[а-яё]{0,2}"),
    ("Якутск", r"[а-яё]{0,2}"), ("Тамбов", r"[а-яё]{0,2}"), ("Грозн", r"[аыуе]{0,2}"),
    ("Стерлитамак", r"[а-яё]{0,2}"), ("Кострома", r"[а-яё]{0,2}"), ("Петрозаводск", r"[а-яё]{0,2}"),
    (r"Нижн\w+ Тагил", r"[а-яё]{0,2}"), ("Йошкар-Ол", r"[а-яё]{0,2}"), ("Новороссийск", r"[а-яё]{0,2}"),
    ("Химки", ""), ("Подольск", r"[а-яё]{0,2}"), ("Королёв", r"[а-яё]{0,2}"), ("Королев", r"[а-яё]{0,2}"),
    ("Мытищи", ""), ("Люберц", r"[аыуе]{0,2}"), ("Красногорск", r"[а-яё]{0,2}"), ("Домодедово", ""),
    ("Белгород", r"[а-яё]{0,2}"), ("Псков", r"[а-яё]{0,2}"), ("Великий Новгород", r"[а-яё]{0,2}"),
    ("Новочеркасск", r"[а-яё]{0,2}"), ("Шахт", r"[аыуе]{0,2}"), ("Дзержинск", r"[а-яё]{0,2}"),
    ("Орёл", r"[а-яё]{0,2}"), ("Орел", r"[а-яё]{0,2}"), ("Нальчик", r"[а-яё]{0,2}"),
    ("Сыктывкар", r"[а-яё]{0,2}"), ("Норильск", r"[а-яё]{0,2}"), ("Абакан", r"[а-яё]{0,2}"),
]
EN_CITIES = ["Moscow", "Saint Petersburg", "St. Petersburg", "Novosibirsk", "Yekaterinburg",
             "London", "New York", "Los Angeles", "Chicago", "Boston", "Washington", "Berlin",
             "Paris", "Madrid", "Rome", "Amsterdam", "Dubai", "Beijing", "Tel Aviv", "Toronto"]

# --------------------------------------------------------------------------- #
#  Валидаторы
# --------------------------------------------------------------------------- #


def inn10_ok(s: str) -> bool:
    d = [int(c) for c in s]
    return sum(d[i] * w for i, w in enumerate([2, 4, 10, 3, 5, 9, 4, 6, 8])) % 11 % 10 == d[9]


def inn12_ok(s: str) -> bool:
    d = [int(c) for c in s]
    c1 = sum(d[i] * w for i, w in enumerate([7, 2, 4, 10, 3, 5, 9, 4, 6, 8])) % 11 % 10
    c2 = sum(d[i] * w for i, w in enumerate([3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8])) % 11 % 10
    return c1 == d[10] and c2 == d[11]


def ogrn_ok(s: str) -> bool:
    d = [int(c) for c in s]
    body, ctrl = d[:-1], d[-1]
    if len(d) == 13:
        return int("".join(map(str, body))) % 11 % 10 == ctrl
    if len(d) == 15:
        return int("".join(map(str, body))) % 13 % 10 == ctrl
    return False


def validate(kind: Optional[str], s: str) -> bool:
    digits = re.sub(r"\D", "", s)
    if kind == "inn":
        return inn10_ok(digits) if len(digits) == 10 else inn12_ok(digits) if len(digits) == 12 else False
    if kind == "ogrn":
        return ogrn_ok(digits)
    return True


# --------------------------------------------------------------------------- #
#  Правила: (категория, id, шаблон, валидатор, группа)
# --------------------------------------------------------------------------- #

_D = lambda p: re.compile(p, re.IGNORECASE)

STREET = (
    r"(?:улиц[аыуе]|ул\.|проспект\w*|пр-т\w*|просп\.|переулок|пер\.|бульвар\w*|б-р|"
    r"шоссе|ш\.|набережн\w+|наб\.|площад\w+|пл\.|проезд\w*|тупик\w*|туп\.|микрорайон|мкр\.|"
    r"Street|St\.|Avenue|Ave\.|Boulevard|Blvd\.|Road|Rd\.|Lane|Drive|Dr\.)"
)
_CITY = r"(?<![А-Яа-яЁё])(?:" + "|".join(f"{s}{t}" for s, t in CITY_STEMS) + r"|" + \
        "|".join(re.escape(c) for c in EN_CITIES) + r")(?![А-Яа-яЁё])"

RULES: List[Tuple[str, str, str, Optional[str], int]] = [
    # --- codes ---
    ("codes", "inn", r"(?<!\d)(\d{10}|\d{12})(?!\d)", "inn", 0),
    ("codes", "kpp", r"(?<!\d)\d{4}(?:[0-9A-ZА-Я]{2})\d{3}(?!\d)", None, 0),
    ("codes", "ogrn", r"(?<!\d)(?:\d{13}|\d{15})(?!\d)", "ogrn", 0),
    ("codes", "snils", r"\b\d{3}-\d{3}-\d{3}[ -]?\d{2}\b", None, 0),
    ("codes", "okpo", r"(?:ОКПО|ОГРПО)\s*[:№]?\s*(\d{8,10})", None, 1),
    ("codes", "oktmo", r"ОКТМО\s*[:№]?\s*(\d{8,11})", None, 1),
    ("codes", "okato", r"ОКАТО\s*[:№]?\s*(\d{8,11})", None, 1),
    ("codes", "okved", r"ОКВЭД\w*\s*[:№]?\s*([\d.,\s]{2,20})", None, 1),
    ("codes", "oms", r"(?:полис\w*[^\d\n]{0,20}|ОМС[^\d\n]{0,20})(\d{11,16})", None, 1),
    # --- identity ---
    ("identity", "passport", r"(?:сери[яию]\s*[:№]?\s*)?\b\d{2}\s?\d{2}\s*(?:№\s*)?\d{6}\b", None, 0),
    ("identity", "passport_code", r"код\s+подразделения\s*[:№]?\s*\d{3}-\d{3}", None, 0),
    ("identity", "drv_series", r"\b\d{2}\s?\d{2}\s?\d{6}\b", None, 0),
    ("identity", "doc_word",
     r"(?:паспорт\w*|загранпаспорт\w*|водительск\w*\s+удостоверени\w*|военн\w+\s+билет\w*|"
     r"свидетельств\w+\s+о\s+рождени\w+|полис\w*\s+ОМС)\s*(?:сери[яию]|№|:)\s*[^\n]{2,60}", None, 0),
    # --- address ---
    ("address", "addr_street", STREET + r"\.?\s+[^,;:\n]{2,60}", None, 0),
    ("address", "street_before",
     r"\b[А-ЯЁ][А-Яа-яЁё\-]+(?:\s+[А-ЯЁ][А-Яа-яЁё\-]+)?\s+"
     r"(?:ул\.|улица|пр-т|проспект|пер\.|переулок|наб\.|набережная|ш\.|шоссе|"
     r"пл\.|площадь|б-р|бульвар|проезд|туп\.)", None, 0),
    ("address", "addr_house",
     r"\b(?:д|дом|кв|квартира|корп|корпус|стр|строение|оф|офис|пом|помещение)\.?\s*№?\s*\d+[а-яa-z]?(?:/\d+)?", None, 0),
    ("address", "addr_index", r"(?:индекс\s*[:№]?\s*)?\b\d{6}\b(?=\s*,?\s*(?:г\.|город|обл|область|край|респ))", None, 0),
    ("address", "region",
     r"(?:респ\w*|област\w*|обл\.|кра[йяюе]|округ\w*|АО)\s+[А-ЯЁ][А-Яа-яЁё\-]+(?:\s+[А-ЯЁ][А-Яа-яЁё\-]+)?", None, 0),
    ("address", "district", r"\b[А-ЯЁ][А-Яа-яЁё\-]+\s+район(?:а|у|е|ом)?(?![а-яё])", None, 0),
    ("address", "city", _CITY, None, 0),
    ("address", "city_label",
     r"\b(?:г\.|гор\.|город|пос\.|посёлок|пгт|дер\.|деревня|с\.|село|ст-ца|станица|аул)(?!\w)\s*([А-ЯЁ][А-Яа-яЁё\-]+)", None, 1),
    # --- realty ---
    ("realty", "cadastral", r"\b\d{2}:\d{2}:\d{6,7}:\d+\b", None, 0),
    ("realty", "realty_obj",
     r"(?:квартир\w*|жил\w+\s+помещени\w*|гараж\w*|машино-мест\w*|нежил\w+\s+помещени\w*|"
     r"земельн\w+\s+участ\w*|дачн\w+\s+участ\w*|домовладени\w*)"
     r"\s*(?:№\s*\d+[^\n]{0,40}|площад\w*[^\n]{0,20}\d[^\n]{0,20})", None, 0),
    ("realty", "realty_right",
     r"(?:прав[оа]\s+(?:собственности|аренды|безвозмездного пользования|хозяйственного ведения|"
     r"оперативного управления)|на\s+праве\s+\w+)\s+на\s+[^\n]{2,60}", None, 0),
    ("realty", "area", r"\b\d+[.,]?\d*\s*(?:кв\.?\s*м|м2|кв\.?м|гектар\w*|га\b)", None, 0),
    # --- contacts ---
    ("contacts", "phone", r"(?:\+7|8)[\s\-(]*\d{3}[\s\-)]*\d{3}[\s\-]?\d{2}[\s\-]?\d{2}\b", None, 0),
    ("contacts", "email", r"\b[\w.+-]+@[\w-]+\.[\w.-]{2,}\b", None, 0),
    ("contacts", "messenger",
     r"(?:telegram|whatsapp|whats\s?app|viber|телеграм|ватсап|вибер)[\s:]*@?[A-Za-z0-9_]{3,}", None, 0),
    # --- bank ---
    ("bank", "bank_acc", r"\b\d{20}\b", None, 0),
    ("bank", "bik", r"(?:БИК\s*[:№]?\s*)?\b(04\d{7})\b", None, 1),
    ("bank", "card", r"\b(?:\d{4}[ -]?){3}\d{4}\b", None, 0),
    ("bank", "bank_name", r"\b[А-ЯЁ][А-Яа-яЁё\-]*(?:банк|Банк)\b", None, 0),
    ("bank", "account_terms",
     r"\b(?:расчётн\w+|расчетн\w+|р/с|к/с|корр\.?\s*сч\w*|лицев\w+\s+сч\w*|счёт|счет)\s*[:№]?\s*[\d\s]{5,25}", None, 0),
    # --- finance ---
    ("finance", "money",
     r"\b\d[\d\s\u00a0]{2,}(?:[.,]\d{1,2})?\s*(?:руб\w*|₽|тыс\.?\s*руб\w*|млн\w*|млрд\w*|долл\w*|USD|EUR|евро)\b", None, 0),
    ("finance", "income",
     r"(?:доход|заработн\w+\s+плат|зарплат|выручк|прибыл|задолженност|кредит|займ|ипотек|"
     r"налог|пенси|пособи)\w*[^\n\d]{0,30}(\d[\d\s\u00a0]{2,}(?:[.,]\d{1,2})?\s*"
     r"(?:руб\w*|₽|тыс\w*|млн\w*|млрд\w*|долл\w*|USD|EUR|евро)?)", None, 1),
    # --- property ---
    ("property", "vin", r"\b[A-HJ-NPR-Z0-9]{17}\b", None, 0),
    ("property", "plate", r"\b[АВЕКМНОРСТУХ]\d{3}[АВЕКМНОРСТУХ]{2}\d{2,3}\b", None, 0),
    ("property", "vehicle",
     r"(?:автомобил\w*|транспортн\w+\s+средств\w*|мотоцикл\w*|снегоход\w*|катер\w*|лодк\w*|прицеп\w*)"
     r"\s+(?:[А-ЯЁA-Z\x22«][^\n]{0,40}|\d[^\n]{0,30})", None, 0),
    # --- employment ---
    ("employment", "job",
     r"(?:место\s+работы|работает|работодател\w*|трудоустроен\w*|должност\w*|"
     r"в\s+должности|служб\w+\s+в)\s*[:—-]?\s*(?=[^\n]{0,80}(?:[А-ЯЁ]|«))[^\n]{0,80}", None, 0),
    # --- leisure ---
    ("leisure", "leisure",
     r"(?:мест\w*\s+отдыха|отдыхал\w*|санатори\w*|курорт\w*|отел\w*|гостиниц\w*|"
     r"пансионат\w*|путёвк\w*|путевк\w*)\s*[:—-]?\s*(?=[^\n]{0,60}(?:[А-ЯЁ]|«))[^\n]{0,60}", None, 0),
    # --- birth ---
    ("birth", "age", r"\b(?:возраст\w*|в\s+возрасте)\s*[:—-]?\s*\d{1,3}(?:\s*(?:лет|года|год|л\.))?", None, 0),
    ("birth", "age_years", r"\b\d{1,3}\s*(?:лет|года|год)\b", None, 0),
    ("birth", "dob", r"(?:дата\s+рождения|родил\w*|г\.\s*р\.)\s*[:—-]?\s*\d{1,2}[./]\d{1,2}[./]\d{2,4}", None, 0),
    ("birth", "dob_plain", r"\b\d{1,2}[./]\d{1,2}[./](?:19|20)\d{2}\s*(?:г\.?\s*)?(?:р\.|года рождения)", None, 0),
    # --- kinship ---
    ("kinship", "kinship",
     r"\b(?:сын|дочь|дочер[ьи]|мать|матер[ьи]|отец|отца|жена|жены|супруг\w*|брат|брата|сестра|"
     r"сестры|тесть|тёща|свекор|свёкор|свекровь|опекун\w*|попечител\w*|родственни\w*)\b"
     r"(?:\s+[А-ЯЁ][А-Яа-яЁё\-]+){0,3}", None, 0),
    # --- org ---
    ("org", "legal_entity",
     r"\b(?:ООО|ОАО|ЗАО|ПАО|АО|ИП|ФГУП|ГУП|МУП|ГБУЗ|ГБУ|ГКУ|МБУ|МАУ|АНО|НКО|НП|ТСЖ|СНТ|"
     r"LLC|Ltd\.?|Inc\.?|GmbH|Corp\.?)\s*[«\"“]?[^\n,;»\"”]{2,80}[»\"”]?", None, 0),
    ("org", "gov_body",
     r"\b(?:Межрайонн\w+|Межрегиональн\w+|ИФНС|ФНС|Федеральн\w+\s+налогов\w+\s+служб\w+|"
     r"Управлени\w+\s+\w+|Министерств\w+|Департамент\w*|Администраци\w+|"
     r"Пенсионн\w+\s+фонд\w*|Государственн\w+\s+учреждени\w+)\s+[^\n,;]{3,120}", None, 0),
    ("org", "institution",
     r"\b(?:ГБОУ|МБОУ|ГКОУ|МКОУ|ГАОУ|МАОУ|СОШ|ООШ|НОШ)\b[^\n,;]{0,70}", None, 0),
    ("org", "institution_named",
     r"\b(?:Дворец\w*|Театр\w*|Гимнази\w+|Лице\w+)\s+[А-ЯЁа-яё\-]+(?:\s+[А-ЯЁа-яё\-]+){0,6}", None, 0),
    # --- docno ---
    ("docno", "doc_no", r"№\s*(\d[\d\s\-]{2,})", None, 1),
    ("docno", "long_number", r"\b\d{15,}\b", None, 0),
]

BLOCK_RULES = {
    "passport", "passport_code", "drv_series", "snils", "phone", "bank_acc", "bik", "inn",
    "kpp", "ogrn", "long_number", "gov_body", "legal_entity", "addr_street", "addr_house",
    "city_label", "region", "city", "cadastral", "realty_obj", "account_terms", "card",
}

ID_RULES = {"inn", "kpp", "ogrn", "snils", "passport", "passport_code", "drv_series",
            "phone", "email", "bank_acc", "bik", "card", "long_number"}

# участники суда: их ФИО в судебных актах сохраняются
COURT_MARKERS = [
    r"\bсуд(?:а|у|ом|е|ья|ьи)?\b", r"дело\s*№", r"истц", r"ответчик", r"заявител",
    r"решение", r"постановление", r"определение", r"приговор", r"прокурор",
    r"судья", r"апелляц", r"кассац", r"третье лицо", r"судебное заседание",
    r"court", r"plaintiff", r"defendant",
]

# --------------------------------------------------------------------------- #
#  Строки/слова
# --------------------------------------------------------------------------- #


@dataclass
class Word:
    text: str
    rect: pymupdf.Rect


@dataclass
class Line:
    text: str
    words: List[Word]
    starts: List[int]

    def rects_for(self, a: int, b: int) -> List[pymupdf.Rect]:
        out = []
        for w, st in zip(self.words, self.starts):
            if st < b and st + len(w.text) > a:
                out.append(w.rect)
        return out


def _group_lines(words: List[Word], joiner: str = " ") -> List[Line]:
    text, starts = "", []
    for w in words:
        if text:
            text += joiner
        starts.append(len(text))
        text += w.text
    return [Line(text, words, starts)] if words else []


def page_lines(page: pymupdf.Page) -> List[Line]:
    buckets: Dict[Tuple[int, int], List[Word]] = {}
    for x0, y0, x1, y1, w, b, l, _n in page.get_text("words"):
        if w.strip():
            buckets.setdefault((b, l), []).append(Word(w, pymupdf.Rect(x0, y0, x1, y1)))
    out = []
    for key in sorted(buckets):
        ws = sorted(buckets[key], key=lambda x: x.rect.x0)
        out.extend(_group_lines(ws))
    return out


def page_blocks(page: pymupdf.Page) -> List[Line]:
    buckets: Dict[int, List[Tuple[int, float, Word]]] = {}
    for x0, y0, x1, y1, w, b, l, _n in page.get_text("words"):
        if w.strip():
            buckets.setdefault(b, []).append((l, x0, Word(w, pymupdf.Rect(x0, y0, x1, y1))))
    out = []
    for b in sorted(buckets):
        ws = [t[2] for t in sorted(buckets[b], key=lambda t: (t[0], t[1]))]
        out.extend(_group_lines(ws))
    return out


def _is_upperish(s: str) -> bool:
    letters = [c for c in s if c.isalpha()]
    if len(letters) < 3:
        return False
    return sum(1 for c in letters if c.isupper()) / len(letters) >= 0.7


def merge_upper_runs(lines: List[Line]) -> List[Line]:
    if not lines:
        return []
    lines = sorted(lines, key=lambda ln: (round(ln.words[0].rect.y0, 1), ln.words[0].rect.x0))
    runs, cur = [], []
    for ln in lines:
        upper = _is_upperish(ln.text)
        if not cur:
            if upper:
                cur = [ln]
            continue
        prev = cur[-1]
        dy = ln.words[0].rect.y0 - prev.words[0].rect.y1
        dx = abs(ln.words[0].rect.x0 - prev.words[0].rect.x0)
        if upper and -2 <= dy <= 25 and dx <= 25:
            cur.append(ln)
        else:
            if len(cur) > 1:
                runs.extend(_group_lines([w for l in cur for w in l.words]))
            cur = [ln] if upper else []
    if len(cur) > 1:
        runs.extend(_group_lines([w for l in cur for w in l.words]))
    return runs


def passport_pairs(words: List[Word]) -> List[pymupdf.Rect]:
    fours = [w for w in words if re.fullmatch(r"\d{4}", w.text)]
    sixes = [w for w in words if re.fullmatch(r"\d{6}", w.text)]
    out = []
    for f in fours:
        best = None
        for s in sixes:
            dx = s.rect.x0 - f.rect.x1
            dy = s.rect.y0 - f.rect.y0
            if -10 <= dx <= 300 and -40 <= dy <= 80:
                if best is None or abs(dx) + abs(dy) < best[0]:
                    best = (abs(dx) + abs(dy), s)
        if best:
            out.append(f.rect | best[1].rect)
    return out


def lines_from_text(text: str) -> List[Line]:
    out = []
    for raw in text.split("\n"):
        if not raw.strip():
            continue
        words, starts = [], []
        for m in re.finditer(r"\S+", raw):
            words.append(Word(m.group(), pymupdf.Rect(0, 0, 0, 0)))
            starts.append(m.start())
        out.append(Line(raw, words, starts))
    return out


def lines_with_offsets(text: str) -> List[Tuple[int, Line]]:
    out, pos = [], 0
    for raw in text.split("\n"):
        if raw.strip():
            words, starts = [], []
            for m in re.finditer(r"\S+", raw):
                words.append(Word(m.group(), pymupdf.Rect(0, 0, 0, 0)))
                starts.append(m.start())
            out.append((pos, Line(raw, words, starts)))
        pos += len(raw) + 1
    return out


# --------------------------------------------------------------------------- #
#  ФИО
# --------------------------------------------------------------------------- #

PATRONYMIC = re.compile(
    r"(?:[ое]вич(?:а|у|ем)?|[ое]вн(?:а|ы|е|у)|ьевич(?:а|у|ем)?|ьевн(?:а|ы|е|у)|"
    r"иевич(?:а|у|ем)?|иевн(?:а|ы|е|у)|иничн(?:а|ы|е|у)|ичн(?:а|ы|е|у))$",
    re.I,
)
SURNAME = re.compile(r"(?:ов|ев|ёв|ин|ын|ова|ева|ёва|ина|ына|ский|цкий|ская|цкая|ой|ый|ая|ко|ук|юк|ян|дзе|швили|енко|чук|ич|их|ых|son|s|ova|ev|in)$", re.I)
SURNAME_STRICT = re.compile(r"(?:ов|ев|ёв|ин|ын|ова|ева|ёва|ина|ына|ский|цкий|ская|цкая|ко|ук|юк|ян|дзе|швили|енко|чук|ич|их|ых)$", re.I)
NAME_STOP = {"российской", "федерации", "россия", "республики", "области", "края", "района",
             "города", "инспекции", "службы", "налоговой", "федеральной", "россии", "город",
             "улица", "государства", "паспорт", "справка", "сведения", "заявление"}
NAME_MARKERS = {"гр", "гр.", "гражданин", "гражданка", "гражданина", "ф.и.о", "ф.и.о.", "фио",
                "ип", "лице", "представитель", "представителя", "судья", "судьи", "секретарь",
                "секретаря", "прокурор", "прокурора", "эксперт", "эксперта", "свидетель",
                "свидетеля", "истец", "истца", "ответчик", "ответчика", "заявитель", "заявителя",
                "mr", "mrs", "ms", "dr"}


def _tokens(line: Line):
    return [(m.start(), m.end(), m.group())
            for m in re.finditer(r"[А-ЯЁ]\.[А-ЯЁ]?\.?|[А-Яа-яЁё][А-Яа-яЁё\-]*|\d+", line.text)]


def find_names(line: Line) -> List[Tuple[int, int]]:
    toks = _tokens(line)
    n = len(toks)
    spans: List[Tuple[int, int]] = []

    def name_tok(t: str) -> bool:
        return bool(re.fullmatch(r"[А-ЯЁ][А-Яа-яЁё\-]+", t)) and len(t) > 1

    for i, (a, b, t) in enumerate(toks):
        low = t.lower()
        if low in NAME_STOP:
            continue
        if PATRONYMIC.search(low) and name_tok(t):
            j = i
            while j > 0 and i - j < 2 and name_tok(toks[j - 1][2]):
                j -= 1
            spans.append((toks[j][0], b))
            continue
        if SURNAME.search(low) and i + 1 < n and toks[i + 1][2].lower() in GIVEN_NAMES:
            end = toks[i + 1][1]
            if i + 2 < n and PATRONYMIC.search(toks[i + 2][2].lower()):
                end = toks[i + 2][1]
            spans.append((a, end))
            continue
        if low in GIVEN_NAMES and i + 1 < n and SURNAME_STRICT.search(toks[i + 1][2].lower()):
            spans.append((a, toks[i + 1][1]))
            continue
        if i > 0 and toks[i - 1][2].lower() in NAME_MARKERS:
            nxt = low
            if not (nxt in GIVEN_NAMES or (name_tok(t) and SURNAME_STRICT.search(nxt))):
                continue
            end = b
            for k in (i + 1, i + 2):
                if k < n and name_tok(toks[k][2]) and toks[k][2].lower() not in NAME_STOP:
                    end = toks[k][1]
            spans.append((a, end))
            continue
        if (re.fullmatch(r"[А-ЯЁ]\.(?:[А-ЯЁ]\.)?", t) and i + 1 < n
                and SURNAME.search(toks[i + 1][2])):
            spans.append((a, toks[i + 1][1]))
            continue
        if re.fullmatch(r"[А-ЯЁ]\.(?:[А-ЯЁ]\.)?", t) and i > 0 and SURNAME.search(toks[i - 1][2]):
            end = b
            if i + 1 < n and re.fullmatch(r"[А-ЯЁ]\.", toks[i + 1][2]):
                end = toks[i + 1][1]
            spans.append((toks[i - 1][0], end))

    merged: List[Tuple[int, int]] = []
    for a, b in sorted(spans):
        if merged and a <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b))
        else:
            merged.append((a, b))
    return merged


def english_names(line: Line) -> List[Tuple[int, int]]:
    out = []
    for m in re.finditer(r"\b(?:Mr|Mrs|Ms|Dr|Prof)\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\b", line.text):
        out.append((m.start(), m.end()))
    return out


# --------------------------------------------------------------------------- #
#  Детект
# --------------------------------------------------------------------------- #


def is_court_act(text: str) -> bool:
    hits = [p for p in COURT_MARKERS if re.search(p, text, re.I)]
    strong = bool(re.search(r"дело\s*№|судебн\w+\s+(?:акт|заседани)|СУД\b|истец|ответчик", text, re.I))
    return len(hits) >= 4 and strong


def collect_hits(lines: List[Line], enabled: set, mode: str, only_ids: Optional[set] = None,
                 keep_ids: bool = False):
    rects: List[Tuple[pymupdf.Rect, str]] = []
    stats: Dict[str, int] = {}
    compiled = []
    for cat, rid, pat, val, grp in RULES:
        if cat not in enabled:
            continue
        if only_ids is not None and rid not in only_ids:
            continue
        if mode == "judicial" and keep_ids and rid in ID_RULES:
            continue
        compiled.append((cat, rid, re.compile(pat, re.I), val, grp))

    for line in lines:
        if not line.text.strip():
            continue
        for cat, rid, rx, val, grp in compiled:
            for m in rx.finditer(line.text):
                if val and not validate(val, m.group()):
                    continue
                if mode == "judicial" and re.search(r"(?<![а-яё])суд", m.group(), re.I):
                    continue
                if rid == "gov_body" and re.search(r"Наименование\s+$", line.text[:m.start()]):
                    continue
                a, b = (m.start(grp), m.end(grp)) if grp else (m.start(), m.end())
                if a < 0 or b < 0:
                    a, b = m.start(), m.end()
                for r in line.rects_for(a, b):
                    rects.append((r, cat))
                stats[cat] = stats.get(cat, 0) + 1
        if "person" in enabled and only_ids is None:
            person_spans = find_names(line) + english_names(line)
            for a, b in person_spans:
                for r in line.rects_for(a, b):
                    rects.append((r, "person"))
                stats["person"] = stats.get("person", 0) + 1
            # в строке с ФИО даты — это даты рождения, их тоже закрываем
            if person_spans and "birth" in enabled and not keep_ids:
                for m in re.finditer(r"\b\d{2}[.\-]\d{2}[.\-](?:19|20)\d{2}\b", line.text):
                    for r in line.rects_for(m.start(), m.end()):
                        rects.append((r, "birth"))
                    stats["birth"] = stats.get("birth", 0) + 1
    return rects, stats


def merge_rects(rects: Sequence[pymupdf.Rect], pad_x: float = 2.6, pad_y: float = 1.1,
                row_gap: float = 14.0, row_tol: float = 3.5) -> List[pymupdf.Rect]:
    """Собирает плашки в сплошные белые полосы.

    Соседние слова одной строки склеиваются, если зазор меньше row_gap, поэтому
    «ЯКОВЛЕВ-ЗАВАЛЬЕВСКИЙ ВЯЧЕСЛАВ АЛЕКСАНДРОВИЧ» закрывается одной полосой,
    а не тремя обрубками. Поля по краям увеличены — текст не выглядывает из-под плашки.
    """
    boxes = [pymupdf.Rect(r.x0 - pad_x, r.y0 - pad_y, r.x1 + pad_x, r.y1 + pad_y) for r in rects]
    merged = True
    while merged:
        merged = False
        out: List[pymupdf.Rect] = []
        for r in boxes:
            for i, o in enumerate(out):
                same_row = abs(o.y0 - r.y0) <= row_tol and abs(o.y1 - r.y1) <= row_tol
                near = (r.x0 - o.x1) <= row_gap and (o.x0 - r.x1) <= row_gap
                if same_row and near:
                    out[i] = o | r
                    merged = True
                    break
            else:
                out.append(r)
        boxes = out
    return boxes


# --------------------------------------------------------------------------- #
#  OCR
# --------------------------------------------------------------------------- #


def find_tesseract() -> Optional[str]:
    cmd = os.environ.get("TESSERACT_CMD")
    if cmd and os.path.exists(cmd):
        return cmd
    for p in (r"C:\Program Files\Tesseract-OCR\tesseract.exe",
              r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
              os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe")):
        if os.path.exists(p):
            return p
    return shutil.which("tesseract")


def tesseract_env() -> dict:
    env = os.environ.copy()
    local = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_tools", "tessdata")
    if os.path.isdir(local):
        env["TESSDATA_PREFIX"] = local
    return env


def _ocr_tsv(img_path: str, exe: str, lang: str = "rus+eng") -> List[str]:
    res = subprocess.run([exe, img_path, "stdout", "-l", lang, "--psm", "3", "tsv"],
                         capture_output=True, check=True, env=tesseract_env())
    return res.stdout.decode("utf-8", "replace").splitlines()


def _lines_from_tsv(rows: List[str], scale: float) -> List[Line]:
    buckets: Dict[Tuple[int, int, int], List[Word]] = {}
    for row in rows[1:]:
        f = row.split("\t")
        if len(f) < 12 or not f[11].strip():
            continue
        key = (int(f[2]), int(f[3]), int(f[4]))
        left, top, w, h = int(f[6]), int(f[7]), int(f[8]), int(f[9])
        rect = pymupdf.Rect(left * scale, top * scale, (left + w) * scale, (top + h) * scale)
        buckets.setdefault(key, []).append(Word(f[11].strip(), rect))
    out = []
    for key in sorted(buckets):
        out.extend(_group_lines(sorted(buckets[key], key=lambda x: x.rect.x0)))
    return out


def ocr_page(page: pymupdf.Page, exe: str, dpi: int) -> List[Line]:
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "p.png")
        page.get_pixmap(dpi=dpi, alpha=False).save(p)
        return _lines_from_tsv(_ocr_tsv(p, exe), 72.0 / dpi)


def ocr_image(path: str, exe: str) -> List[Line]:
    return _lines_from_tsv(_ocr_tsv(path, exe), 1.0)


# --------------------------------------------------------------------------- #
#  Векторные линии
# --------------------------------------------------------------------------- #


def collect_segments(page: pymupdf.Page):
    segs = []
    for d in page.get_drawings():
        w = d.get("width") or 0.7
        color = d.get("color") or (0.0, 0.0, 0.0)
        if d.get("color") is None and d.get("fill") is not None:
            continue
        for it in d["items"]:
            if it[0] == "l":
                p1, p2 = it[1], it[2]
                segs.append((min(p1.x, p2.x), min(p1.y, p2.y), max(p1.x, p2.x), max(p1.y, p2.y), w, tuple(color)))
            elif it[0] == "re":
                r = it[1]
                segs += [(r.x0, r.y0, r.x1, r.y0, w, tuple(color)),
                         (r.x0, r.y1, r.x1, r.y1, w, tuple(color)),
                         (r.x0, r.y0, r.x0, r.y1, w, tuple(color)),
                         (r.x1, r.y0, r.x1, r.y1, w, tuple(color))]
    return segs


def restore_lines(page: pymupdf.Page, boxes: Sequence[pymupdf.Rect], segs) -> int:
    drawn = 0
    for x0, y0, x1, y1, w, color in segs:
        horiz = abs(y1 - y0) <= 0.8 and x1 - x0 > 1
        vert = abs(x1 - x0) <= 0.8 and y1 - y0 > 1
        if not horiz and not vert:
            continue
        if horiz:
            hit = [b for b in boxes if b.y0 - 1.5 <= y0 <= b.y1 + 3 and x1 >= b.x0 - 1 and x0 <= b.x1 + 1]
            if hit:
                a = max(x0, min(b.x0 for b in hit) - 1.5)
                c = min(x1, max(b.x1 for b in hit) + 1.5)
                if c > a:
                    page.draw_line((a, y0), (c, y0), color=color, width=w)
                    drawn += 1
        else:
            hit = [b for b in boxes if b.x0 - 1.5 <= x0 <= b.x1 + 1.5 and y1 >= b.y0 - 1 and y0 <= b.y1 + 1]
            if hit:
                a = max(y0, min(b.y0 for b in hit) - 1.5)
                c = min(y1, max(b.y1 for b in hit) + 1.5)
                if c > a:
                    page.draw_line((x0, a), (x0, c), color=color, width=w)
                    drawn += 1
    return drawn


# --------------------------------------------------------------------------- #
#  PDF
# --------------------------------------------------------------------------- #


def _page_lines_and_extras(page: pymupdf.Page, exe: Optional[str], ocr: str, dpi: int):
    text = page.get_text().strip()
    need_ocr = ocr == "always" or (ocr == "auto" and len(text) < 40)
    if need_ocr and exe:
        lines = ocr_page(page, exe, dpi)
        extras = [merge_upper_runs(lines)]
        words = [w for ln in lines for w in ln.words]
        return lines, extras, words, True
    lines = page_lines(page)
    extras = [page_blocks(page), merge_upper_runs(lines)]
    words = [Word(w, pymupdf.Rect(x0, y0, x1, y1))
             for x0, y0, x1, y1, w, *_ in page.get_text("words") if w.strip()]
    return lines, extras, words, False


def scan_pdf(src: str, mode: str, enabled: set, ocr: str, dpi: int, keep_ids: bool):
    """Только обнаружение, без изменения файла. Возвращает счётчики и боксы по страницам."""
    doc = pymupdf.open(src)
    exe = find_tesseract()
    per_page = []
    totals: Dict[str, int] = {}
    for page in doc:
        lines, extras, words, scanned = _page_lines_and_extras(page, exe, ocr, dpi)
        rects, stats = collect_hits(lines, enabled, mode, keep_ids=keep_ids)
        for extra in extras:
            r2, s2 = collect_hits(extra, enabled, mode, only_ids=BLOCK_RULES, keep_ids=keep_ids)
            rects += r2
            for k, v in s2.items():
                stats[k] = stats.get(k, 0) + v
        if "identity" in enabled:
            for pr in passport_pairs(words):
                rects.append((pr, "identity"))
                stats["identity"] = stats.get("identity", 0) + 1
        boxes = merge_rects([r for r, _ in rects])
        per_page.append((page.number, boxes, scanned))
        for k, v in stats.items():
            totals[k] = totals.get(k, 0) + v
    doc.close()
    return per_page, totals


def _hidden_font():
    """Шрифт с кириллицей для невидимого текстового слоя."""
    for p in (r"C:\Windows\Fonts\arial.ttf",
              r"C:\Windows\Fonts\DejaVuSans.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        if os.path.exists(p):
            return p
    return None


def _insert_invisible_text(page, lines, boxes, report) -> int:
    """Кладёт слова OCR невидимым слоем (render_mode=3), пропуская закрытые плашками."""
    path = _hidden_font()
    if not path:
        report["text_layer_warning"] = "нет шрифта с кириллицей"
        return 0
    try:
        font = pymupdf.Font(fontfile=path)
    except Exception as err:
        report["text_layer_warning"] = f"шрифт не загрузился: {err}"
        return 0
    writer = pymupdf.TextWriter(page.rect)
    n = 0
    for line in lines:
        kept = [(w, w.text) for w in line.words
                if w.text.strip() and not any(w.rect.intersects(b) for b in boxes)]
        if not kept:
            continue
        heights = sorted(w.rect.height for w, _ in kept)
        h = heights[len(heights) // 2]
        baseline = pymupdf.Point(kept[0][0].rect.x0, max(w.rect.y1 for w, _ in kept) - 0.2 * h)
        text = " ".join(t for _, t in kept)
        try:
            writer.append(baseline, text, font=font, fontsize=h * 0.8)
            n += len(kept)
        except Exception:
            continue
    if n:
        writer.write_text(page, color=(0, 0, 0), render_mode=3)
    report["text_layer_words"] = report.get("text_layer_words", 0) + n
    return n


def render_pdf(src: str, dst: str, mode: str, enabled: set, ocr: str, dpi: int,
               keep_meta: bool, keep_ids: bool):
    doc = pymupdf.open(src)
    exe = find_tesseract()
    report = {"file": os.path.basename(src), "mode": mode, "pages": doc.page_count,
              "categories": {}, "boxes": 0, "scanned_pages": 0, "restored_lines": 0}
    for page in doc:
        lines, extras, words, scanned = _page_lines_and_extras(page, exe, ocr, dpi)
        rects, stats = collect_hits(lines, enabled, mode, keep_ids=keep_ids)
        for extra in extras:
            r2, s2 = collect_hits(extra, enabled, mode, only_ids=BLOCK_RULES, keep_ids=keep_ids)
            rects += r2
            for k, v in s2.items():
                stats[k] = stats.get(k, 0) + v
        if "identity" in enabled:
            for pr in passport_pairs(words):
                rects.append((pr, "identity"))
                stats["identity"] = stats.get("identity", 0) + 1
        boxes = merge_rects([r for r, _ in rects])
        report["boxes"] += len(boxes)
        for k, v in stats.items():
            report["categories"][k] = report["categories"].get(k, 0) + v

        if scanned:
            report["scanned_pages"] += 1
            pix = page.get_pixmap(dpi=dpi, alpha=False)
            im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            dr = ImageDraw.Draw(im)
            sc = pix.width / page.rect.width
            for b in boxes:
                dr.rectangle([b.x0 * sc, b.y0 * sc, b.x1 * sc, b.y1 * sc], fill=(255, 255, 255),
                             outline=(184, 184, 184) if BAR_BORDER else None,
                             width=1 if BAR_BORDER else 0)
            rect = page.rect
            pno = page.number
            doc.delete_page(pno)
            new_page = doc.new_page(pno=pno, width=rect.width, height=rect.height)
            buf = io.BytesIO()
            im.save(buf, format="PNG")
            new_page.insert_image(rect, stream=buf.getvalue())
            if TEXT_LAYER and lines:
                _insert_invisible_text(new_page, lines, boxes, report)
        else:
            segs = collect_segments(page)
            for b in boxes:
                page.add_redact_annot(b, fill=(1, 1, 1), cross_out=False)
            if boxes:
                page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE)
                report["restored_lines"] += restore_lines(page, boxes, segs)
                if BAR_BORDER:
                    for b in boxes:
                        page.draw_rect(b, color=(0.72, 0.72, 0.72), width=0.5, fill=None)
    if not keep_meta:
        doc.set_metadata({})
    try:
        doc.subset_fonts()
    except Exception:
        pass
    os.makedirs(os.path.dirname(os.path.abspath(dst)) or ".", exist_ok=True)
    doc.save(dst, garbage=4, deflate=True, clean=True)
    doc.close()
    return report


def verify_pdf(dst: str, enabled: set, mode: str) -> Dict[str, int]:
    doc = pymupdf.open(dst)
    text = "".join(p.get_text() for p in doc)
    doc.close()
    _, stats = collect_hits(lines_from_text(text), enabled, mode)
    return stats


# --------------------------------------------------------------------------- #
#  Изображения
# --------------------------------------------------------------------------- #


def render_image(src: str, dst: str, mode: str, enabled: set, keep_ids: bool):
    exe = find_tesseract()
    if not exe:
        raise RuntimeError("Tesseract не найден: изображения без OCR не обезличить")
    lines = ocr_image(src, exe)
    rects, stats = collect_hits(lines, enabled, mode, keep_ids=keep_ids)
    for extra in (merge_upper_runs(lines),):
        r2, s2 = collect_hits(extra, enabled, mode, only_ids=BLOCK_RULES, keep_ids=keep_ids)
        rects += r2
        for k, v in s2.items():
            stats[k] = stats.get(k, 0) + v
    if "identity" in enabled:
        for pr in passport_pairs([w for ln in lines for w in ln.words]):
            rects.append((pr, "identity"))
            stats["identity"] = stats.get("identity", 0) + 1
    boxes = merge_rects([r for r, _ in rects])

    im = Image.open(src)
    fmt = (im.format or "PNG").upper()
    im = im.convert("RGB")
    dr = ImageDraw.Draw(im)
    for b in boxes:
        dr.rectangle([b.x0, b.y0, b.x1, b.y1], fill=(255, 255, 255),
                     outline=(184, 184, 184) if BAR_BORDER else None,
                     width=1 if BAR_BORDER else 0)
    save_kwargs = {}
    if fmt in ("JPEG", "JPG"):
        save_kwargs = {"quality": 95, "subsampling": 0}
    im.save(dst, format=fmt if fmt in ("PNG", "JPEG", "TIFF", "BMP", "WEBP") else "PNG", **save_kwargs)
    return {"file": os.path.basename(src), "mode": mode, "categories": stats,
            "boxes": len(boxes), "size": list(im.size)}


# --------------------------------------------------------------------------- #
#  DOCX / текст
# --------------------------------------------------------------------------- #


def docx_to_md(path: str) -> str:
    from docx import Document
    from docx.oxml.ns import qn
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    d = Document(path)
    out: List[str] = []
    for child in d.element.body.iterchildren():
        if child.tag == qn("w:p"):
            p = Paragraph(child, d)
            text = p.text.strip()
            if not text:
                out.append("")
                continue
            style = (p.style.name or "").lower()
            if style.startswith("heading"):
                lvl = re.sub(r"\D", "", style) or "1"
                out.append("#" * min(int(lvl), 6) + " " + text)
            elif "list" in style or (p._p.pPr is not None and p._p.pPr.numPr is not None):
                out.append("- " + text)
            elif style.startswith("title"):
                out.append("# " + text)
            else:
                out.append(text)
        elif child.tag == qn("w:tbl"):
            t = Table(child, d)
            rows = [[c.text.strip().replace("\n", " ") for c in r.cells] for r in t.rows]
            if not rows:
                continue
            width = max(len(r) for r in rows)
            rows = [r + [""] * (width - len(r)) for r in rows]
            out.append("| " + " | ".join(rows[0]) + " |")
            out.append("|" + "|".join(["---"] * width) + "|")
            for r in rows[1:]:
                out.append("| " + " | ".join(r) + " |")
            out.append("")
    return "\n".join(out).strip() + "\n"


def _rule_order(rule):
    """Длинные шаблоны раньше коротких; названия учреждений — раньше городов и адресов."""
    cat, rid, pat, val, grp = rule
    priority = 0 if rid.startswith("institution") else 1
    return (priority, -len(pat))


def anonymize_text(text: str, mode: str, enabled: set, keep_ids: bool):
    stats: Dict[str, int] = {}

    def sub(cat, rid, rx, val, grp):
        def repl(m):
            if val and not validate(val, m.group()):
                return m.group()
            stats[cat] = stats.get(cat, 0) + 1
            if grp:
                whole = m.group(0)
                gs = m.start(grp) - m.start(0)
                ge = m.end(grp) - m.start(0)
                if gs >= 0 and ge >= 0:
                    return whole[:gs] + PLACEHOLDER + whole[ge:]
            return PLACEHOLDER
        return rx.sub(repl, text)

    for cat, rid, pat, val, grp in sorted(RULES, key=_rule_order):
        if cat not in enabled:
            continue
        if mode == "judicial" and keep_ids and rid in ID_RULES:
            continue
        text = sub(cat, rid, re.compile(pat, re.I), val, grp)

    if "person" in enabled:
        spans = []
        for base, ln in lines_with_offsets(text):
            spans.extend((base + a, base + b) for a, b in find_names(ln) + english_names(ln))
        spans.sort()
        merged = []
        for a, b in spans:
            if merged and a <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], b))
            else:
                merged.append((a, b))
        if merged:
            parts, cur = [], 0
            for a, b in merged:
                parts.append(text[cur:a])
                parts.append(PLACEHOLDER)
                cur = b
                stats["person"] = stats.get("person", 0) + 1
            parts.append(text[cur:])
            text = "".join(parts)
    return text, stats


# --------------------------------------------------------------------------- #
#  CLI
# --------------------------------------------------------------------------- #


def print_categories():
    print("Категории (по умолчанию скрываются все):")
    for key, title in CATEGORIES.items():
        print(f"  {key:11s} {title}")


def ask_categories(found: Dict[str, int]) -> set:
    enabled = set(CATEGORIES)
    if not found:
        print("Ничего не найдено — скрывать нечего.")
        return enabled
    print("\nНайдено:")
    for key in CATEGORIES:
        if found.get(key):
            print(f"  {key:11s} {found[key]:3d}  {CATEGORIES[key]}")
    print("\nЧто оставить открытым? Категории через запятую, Enter — скрыть всё: ", end="")
    raw = input().strip()
    if not raw:
        return enabled
    for part in re.split(r"[,\s]+", raw):
        if part in CATEGORIES:
            enabled.discard(part)
        elif part in ("all", "все"):
            return enabled
    return enabled


def out_name(src: str, ext: str) -> str:
    if SAFE_NAME:
        return f"document_anon{ext}"
    base, _ = os.path.splitext(src)
    return f"{base}_anon{ext}"


def process(path: str, args, enabled: Optional[set] = None):
    ext = os.path.splitext(path)[1].lower()
    base, _ = os.path.splitext(os.path.basename(path))

    if ext == ".pdf":
        doc = pymupdf.open(path)
        full = "".join(p.get_text() for p in doc)
        doc.close()
        mode = args.mode
        if mode == "auto":
            mode = "judicial" if is_court_act(full) else "document"
        enabled = set(enabled) if enabled is not None else default_enabled(mode, args)
        if args.ask:
            _, found = scan_pdf(path, mode, enabled, args.ocr, args.dpi, args.court_keep_ids)
            enabled = ask_categories(found)
        dst = args.out or out_name(path, ".pdf")
        if not dst.lower().endswith(".pdf"):
            fixed = os.path.splitext(dst)[0] + ".pdf"
            print(f"PDF сохраняется только в PDF: {dst} -> {fixed}", file=sys.stderr)
            dst = fixed
        rep = render_pdf(path, dst, mode, enabled, args.ocr, args.dpi, args.keep_meta, args.court_keep_ids)
        left = verify_pdf(dst, enabled, mode)
        rep["mode"] = mode
        rep["kept_categories"] = sorted(set(CATEGORIES) - enabled)
        rep["leftover"] = left
        rep["output"] = dst
        return rep

    if ext in IMAGE_EXT:
        enabled = set(enabled) if enabled is not None else default_enabled(args.mode, args)
        dst = args.out or out_name(path, ext)
        rep = render_image(path, dst, args.mode, enabled, args.court_keep_ids)
        rep["kept_categories"] = sorted(set(CATEGORIES) - enabled)
        rep["output"] = dst
        return rep

    if ext in (".docx", ".doc"):
        md = docx_to_md(path)
        mode = args.mode
        if mode == "auto":
            mode = "judicial" if is_court_act(md) else "document"
        enabled = set(enabled) if enabled is not None else default_enabled(mode, args)
        if args.ask:
            _, found = collect_hits(lines_from_text(md), enabled, mode)
            enabled = ask_categories(found)
        anon, stats = anonymize_text(md, mode, enabled, args.court_keep_ids)
        dst = args.out or out_name(path, ".md")
        with open(dst, "w", encoding="utf-8") as f:
            f.write(anon)
        return {"file": os.path.basename(path), "mode": mode, "converted_to_md": True,
                "categories": stats, "kept_categories": sorted(set(CATEGORIES) - enabled),
                "output": dst}

    if ext in (".md", ".markdown", ".txt"):
        with open(path, encoding="utf-8") as f:
            raw = f.read()
        mode = args.mode
        if mode == "auto":
            mode = "judicial" if is_court_act(raw) else "document"
        enabled = set(enabled) if enabled is not None else default_enabled(mode, args)
        if args.ask:
            _, found = collect_hits(lines_from_text(raw), enabled, mode)
            enabled = ask_categories(found)
        anon, stats = anonymize_text(raw, mode, enabled, args.court_keep_ids)
        dst = args.out or out_name(path, ext)
        with open(dst, "w", encoding="utf-8") as f:
            f.write(anon)
        return {"file": os.path.basename(path), "mode": mode, "categories": stats,
                "kept_categories": sorted(set(CATEGORIES) - enabled), "output": dst}

    raise SystemExit(f"Неподдерживаемый формат: {ext}")


def default_enabled(mode: str, args) -> set:
    enabled = set(CATEGORIES)
    if mode == "judicial":
        enabled -= JUDICIAL_KEEP
        if args.court_keep_ids:
            pass
    if args.only:
        enabled &= set(args.only)
    if args.keep:
        enabled -= set(args.keep)
    return enabled


def main(argv: Optional[Sequence[str]] = None) -> int:
    global PLACEHOLDER, SAFE_NAME, BAR_BORDER, TEXT_LAYER
    ap = argparse.ArgumentParser(description="DoctorHide — обезличивание документов")
    ap.add_argument("inputs", nargs="*", help="файлы, маски (docs\\*.pdf) или папки")
    ap.add_argument("-o", "--out", help="файл результата (для одного входа)")
    ap.add_argument("--mode", default="auto", choices=["auto", "judicial", "document"])
    ap.add_argument("--keep", nargs="+", default=[], metavar="CAT",
                    help="категории, которые НЕ скрывать")
    ap.add_argument("--only", nargs="+", default=[], metavar="CAT",
                    help="скрывать только эти категории")
    ap.add_argument("--ask", action="store_true", help="показать найденное и спросить, что оставить")
    ap.add_argument("--list-categories", action="store_true")
    ap.add_argument("--ocr", default="auto", choices=["auto", "always", "never"])
    ap.add_argument("--dpi", type=int, default=300)
    ap.add_argument("--placeholder", default=PLACEHOLDER)
    ap.add_argument("--no-text-layer", action="store_true",
                    help="не добавлять невидимый текстовый слой в сканы")
    ap.add_argument("--no-bar-border", action="store_true",
                    help="плашки без серой обводки (только белая заливка)")
    ap.add_argument("--safe-name", action="store_true",
                    help="имя результата без исходного названия: document_anon.<ext>")
    ap.add_argument("--keep-meta", action="store_true")
    ap.add_argument("--court-keep-ids", action="store_true",
                    help="в судебных актах не скрывать ИНН/ОГРН/СНИЛС/паспорт")
    ap.add_argument("--report", help="записать JSON-отчёт сюда")
    ap.add_argument("--json", action="store_true", help="печатать только JSON")
    args = ap.parse_args(argv)

    if args.list_categories:
        print_categories()
        return 0

    PLACEHOLDER = args.placeholder
    SAFE_NAME = args.safe_name
    BAR_BORDER = not args.no_bar_border
    TEXT_LAYER = not args.no_text_layer

    files: List[str] = []
    for item in args.inputs:
        if os.path.isdir(item):
            for name in sorted(os.listdir(item)):
                if os.path.splitext(name)[1].lower() in ({".pdf", ".docx", ".doc", ".md", ".markdown",
                                                          ".txt"} | IMAGE_EXT):
                    files.append(os.path.join(item, name))
        elif any(ch in item for ch in "*?["):
            files.extend(sorted(glob.glob(item)))
        else:
            files.append(item)
    if not files:
        ap.error("не указаны входные файлы")

    results = []
    enabled = None
    missing = 0
    for path in files:
        if not os.path.exists(path):
            print(f"нет файла: {path}", file=sys.stderr)
            missing += 1
            continue
        rep = process(path, args, enabled)
        if args.keep is not None and enabled is None and (args.keep or args.only):
            enabled = default_enabled(rep.get("mode", args.mode), args)
        results.append(rep)
        if not args.json:
            cats = ", ".join(f"{k}:{v}" for k, v in sorted(rep.get("categories", {}).items())) or "—"
            print(f"\n{rep['file']} → {rep['output']}")
            print(f"  режим: {rep.get('mode')}  категории: {cats}")
            if rep.get("boxes") is not None:
                print(f"  плашек: {rep['boxes']}  восстановлено линий: {rep.get('restored_lines', 0)}")
            if rep.get("leftover"):
                print(f"  ВНИМАНИЕ, остались совпадения: {rep['leftover']}")

    if not results:
        print("ни одного файла не обработано", file=sys.stderr)
        return 2

    if args.report:
        with open(args.report, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
