#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
anonymize.py — обезличивание документов (RU/EN) по проектным правилам DoctorAnon.

Правила:
  * Судебный акт: НЕ трогаем названия судов и ФИО участников (судьи, секретари,
    представители сторон, свидетели, эксперты, прокуроры, иные участники).
    Обезличиваем возраст, адреса, города, а также паспорт/ИНН/СНИЛС/телефоны.
  * Не судебный акт: обезличиваем ФИО, наименования юрлиц, коды статистики,
    ИНН, КПП, ОГРН/ОГРНИП, ОКПО/ОКТМО, адреса, родство, финансовую информацию.
  * PDF  -> белые плашки, текст под ними физически удалён (apply_redactions).
  * DOCX -> конвертация в Markdown, DOCX/MD -> замена на [censored].
  * Распознавание: слой текста PDF, при его отсутствии — Tesseract (rus+eng).

Примеры:
  python anonymize.py doc.pdf
  python anonymize.py doc.docx --mode document
  python anonymize.py scan.pdf --ocr always --dpi 400
"""

from __future__ import annotations

import argparse
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

# --------------------------------------------------------------------------- #
#  Справочники
# --------------------------------------------------------------------------- #

GIVEN_NAMES = set(
    """
    александр алексей анатолий андрей антон аркадий арсений артём артем богдан борис
    вадим валентин валерий василий вениамин виктор виталий владимир владислав всеволод
    вячеслав геннадий георгий герман глеб григорий давид даниил денис дмитрий евгений
    евгений егор ефим захар иван игорь илья иннокентий кирилл константин лев леонид
    максим марат марк матвей михаил надежда никита николай олег павел пётр петр платон
    роман ростислав руслан рустам савелий святослав семён семен сергей станислав
    степан тарас тимофей тимур фёдор федор филипп эдуард юрий яков ярослав
    александра алина алиса алла анастасия ангелина анна антонина валентина валерия
    вера вероника виктория галина дарья диана евгения екатерина елена елизавета
    зинаида зоя инна ирина карина ксения лариса лидия любовь людмила маргарита марина
    мария милана надежда наталья нина оксана ольга полина раиса светлана софия
    софья тамара татьяна ульяна эльвира юлия яна
    """.split()
)

CITY_STEMS = [
    ("Санкт[- ]Петербург", r"[а-яё]{0,2}"), ("СПб", ""), ("Петербург", r"[а-яё]{0,2}"),
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
    ("Пенз", r"[аыуе]{0,2}"), ("Липецк", r"[а-яё]{0,2}"), ("Тул", r"[аыуе]{0,2}"), ("Калининград", r"[а-яё]{0,2}"), ("Балаших", r"[аиуе]{0,2}"),
    ("Курск", r"[а-яё]{0,2}"), ("Севастопол", r"[ьея]{0,2}"), ("Сочи", ""),
    ("Ставропол", r"[ьея]{0,2}"), ("Улан-Удэ", ""), ("Твер", r"[ьияюе]{0,2}"),
    ("Магнитогорск", r"[а-яё]{0,2}"), ("Иванов", r"[ое]"), ("Брянск", r"[а-яё]{0,2}"),
    ("Сургут", r"[а-яё]{0,2}"), ("Владимир", r"[а-яё]{0,2}"), ("Архангельск", r"[а-яё]{0,2}"),
    ("Чита", r"[а-яё]{0,2}"), ("Калуг", r"[аиуе]{0,2}"), ("Смоленск", r"[а-яё]{0,2}"),
    ("Волжск", r"[а-яё]{0,2}"), ("Курган", r"[а-яё]{0,2}"), ("Череповец", r"[а-яё]{0,2}"),
    ("Вологд", r"[аыуе]{0,2}"), ("Саранск", r"[а-яё]{0,2}"), ("Владикавказ", r"[а-яё]{0,2}"),
    ("Мурманск", r"[а-яё]{0,2}"), ("Якутск", r"[а-яё]{0,2}"), ("Тамбов", r"[а-яё]{0,2}"),
    ("Грозн", r"[аыуе]{0,2}"), ("Стерлитамак", r"[а-яё]{0,2}"), ("Кострома", r"[а-яё]{0,2}"),
    ("Петрозаводск", r"[а-яё]{0,2}"), (r"Нижн\w+ Тагил", r"[а-яё]{0,2}"), ("Йошкар-Ол", r"[а-яё]{0,2}"),
    ("Новороссийск", r"[а-яё]{0,2}"), ("Химки", ""), ("Подольск", r"[а-яё]{0,2}"),
    ("Королёв", r"[а-яё]{0,2}"), ("Королев", r"[а-яё]{0,2}"), ("Мытищи", ""),
    ("Люберц", r"[аыуе]{0,2}"), ("Красногорск", r"[а-яё]{0,2}"), ("Домодедово", ""),
    ("Белгород", r"[а-яё]{0,2}"), ("Псков", r"[а-яё]{0,2}"), ("Великий Новгород", r"[а-яё]{0,2}"),
    ("Новочеркасск", r"[а-яё]{0,2}"), ("Шахт", r"[аыуе]{0,2}"), ("Дзержинск", r"[а-яё]{0,2}"),
    ("Орёл", r"[а-яё]{0,2}"), ("Орел", r"[а-яё]{0,2}"), ("Нальчик", r"[а-яё]{0,2}"),
    ("Сыктывкар", r"[а-яё]{0,2}"), ("Норильск", r"[а-яё]{0,2}"), ("Абакан", r"[а-яё]{0,2}"),
]

EN_CITIES = [
    "Moscow", "Saint Petersburg", "St. Petersburg", "Novosibirsk", "Yekaterinburg",
    "London", "New York", "Los Angeles", "Chicago", "Boston", "Washington",
    "Berlin", "Paris", "Madrid", "Rome", "Amsterdam", "Dubai", "Beijing",
    "Tel Aviv", "Toronto", "Sydney",
]

# --------------------------------------------------------------------------- #
#  Валидаторы контрольных сумм (снижают ложные срабатывания)
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
        return (int("".join(map(str, body))) % 11) % 10 == ctrl
    if len(d) == 15:
        return (int("".join(map(str, body))) % 13) % 10 == ctrl
    return False


def snils_ok(s: str) -> bool:
    d = [int(c) for c in re.sub(r"\D", "", s)]
    if len(d) != 11:
        return False
    base = d[:9]
    total = sum(n * (9 - i) for i, n in enumerate(base))
    if total < 100:
        ctrl = total
    elif total in (100, 101):
        ctrl = 0
    else:
        ctrl = total % 101
        if ctrl == 100:
            ctrl = 0
    return ctrl == d[9] * 10 + d[10]


# --------------------------------------------------------------------------- #
#  Правила
# --------------------------------------------------------------------------- #


@dataclass
class Rule:
    id: str
    pattern: str
    scope: str = "always"          # always | court_only | noncourt
    validator: Optional[str] = None
    flags: int = re.IGNORECASE
    group: int = 0                 # 0 = весь матч, иначе номер группы со значением


def _city_regex() -> str:
    parts = [f"{stem}{tail}" for stem, tail in CITY_STEMS]
    en = "|".join(re.escape(c) for c in EN_CITIES)
    return r"(?<![А-Яа-яЁё])(?:" + "|".join(parts) + r"|" + en + r")(?![А-Яа-яЁё])"


ADDR_STREET = (
    r"(?:улиц[аыуе]|ул\.|проспект\w*|пр-т\w*|просп\.|переулок|пер\.|бульвар\w*|б-р|"
    r"шоссе|ш\.|набережн\w+|наб\.|площад\w+|пл\.|проезд\w*|тупик\w*|туп\.|микрорайон|мкр\.|"
    r"Street|St\.|Avenue|Ave\.|Boulevard|Blvd\.|Road|Rd\.|Lane|Drive|Dr\.)"
)

RULES: List[Rule] = [
    # --- прямые идентификаторы (все режимы) ---
    Rule("inn", r"(?<!\d)(\d{10}|\d{12})(?!\d)", "always", "inn"),
    Rule("kpp", r"(?<!\d)\d{4}(?:[0-9A-ZА-Я]{2})\d{3}(?!\d)", "always"),
    Rule("ogrn", r"(?<!\d)(?:\d{13}|\d{15})(?!\d)", "always", "ogrn"),
    Rule("snils", r"\b\d{3}-\d{3}-\d{3}[ -]?\d{2}\b", "always"),
    Rule("passport_series", r"(?:сери[яию]\s*[:№]?\s*)?\b\d{2}\s?\d{2}\s*(?:№\s*)?\d{6}\b", "always"),
    Rule("passport_code", r"код\s+подразделения\s*[:№]?\s*\d{3}-\d{3}", "always"),
    Rule("phone_ru", r"(?:\+7|8)[\s\-(]*\d{3}[\s\-)]*\d{3}[\s\-]?\d{2}[\s\-]?\d{2}\b", "always"),
    Rule("email", r"\b[\w.+-]+@[\w-]+\.[\w.-]{2,}\b", "always", None, 0),
    Rule("bank_acc", r"\b\d{20}\b", "always"),
    Rule("bik", r"(?:БИК\s*[:№]?\s*)?\b(04\d{7})\b", "always", group=1),
    # --- коды статистики (по метке, чтобы не ловить обычные числа) ---
    Rule("okpo", r"(?:ОКПО|ОГРПО)\s*[:№]?\s*(\d{8,10})", "noncourt", group=1),
    Rule("oktmo", r"ОКТМО\s*[:№]?\s*(\d{8,11})", "noncourt", group=1),
    Rule("okato", r"ОКАТО\s*[:№]?\s*(\d{8,11})", "noncourt", group=1),
    Rule("okved", r"ОКВЭД\w*\s*[:№]?\s*([\d.,\s]{2,20})", "noncourt", group=1),
    # --- адреса и города ---
    Rule("addr_street", ADDR_STREET + r"\.?\s+[^,;:\n]{2,60}", "always"),
    Rule("addr_house", r"\b(?:д|дом|кв|квартира|корп|корпус|стр|строение|оф|офис|пом|помещение)\.?\s*№?\s*\d+[а-яa-z]?(?:/\d+)?", "always"),
    Rule("addr_index", r"(?:индекс\s*[:№]?\s*)?\b\d{6}\b(?=\s*,?\s*(?:г\.|город|обл|область|край|респ))", "always"),
    Rule("region", r"(?:респ\w*|област\w*|обл\.|кра[йяюе]|край|округ\w*|АО)\s+[А-ЯЁ][А-Яа-яЁё\-]+(?:\s+[А-ЯЁ][А-Яа-яЁё\-]+)?", "always"),
    Rule("city", _city_regex(), "always"),
    Rule("city_label", r"\b(?:г\.|гор\.|город|пос\.|посёлок|пгт|дер\.|деревня|с\.|село|ст-ца|станица|аул)\s*([А-ЯЁ][А-Яа-яЁё\-]+)", "always", group=1),
    # --- возраст / дата рождения ---
    Rule("age", r"\b(?:возраст\w*|в\s+возрасте)\s*[:—-]?\s*\d{1,3}(?:\s*(?:лет|года|год|л\.))?", "always"),
    Rule("age_years", r"\b\d{1,3}\s*(?:лет|года|год)\b", "always"),
    Rule("dob", r"(?:дата\s+рождения|родил\w*|г\.\s*р\.)\s*[:—-]?\s*\d{1,2}[./]\d{1,2}[./]\d{2,4}", "always"),
    Rule("dob_plain", r"\b\d{1,2}[./]\d{1,2}[./](?:19|20)\d{2}\s*(?:г\.?\s*)?(?:р\.|года рождения)", "always"),
    # --- родство ---
    Rule("kinship", r"\b(?:сын|дочь|дочер[ьи]|мать|матер[ьи]|отец|отца|жена|жены|супруг\w*|брат|брата|сестра|сестры|тесть|тёща|свекор|свёкор|свекровь|опекун\w*|попечител\w*|родственни\w*|родная\s+сестра|родной\s+брат)\b(?:\s+[А-ЯЁ][А-Яа-яЁё\-]+){0,3}", "always"),
    # --- юрлица и ИП ---
    Rule(
        "legal_entity",
        r"\b(?:ООО|ОАО|ЗАО|ПАО|АО|ИП|ФГУП|ГУП|МУП|ГБУЗ|ГБУ|ГКУ|МБУ|МАУ|АНО|НКО|НП|ТСЖ|СНТ|"
        r"LLC|Ltd\.?|Inc\.?|GmbH|Corp\.?)\s*[«\"“]?[^\n,;»\"”]{2,80}[»\"”]?",
        "noncourt",
    ),
    Rule(
        "legal_entity_quoted",
        r"[«\"“][^»\"”\n]{2,80}[»\"”]\s*(?:\(|,)?\s*(?:ООО|ОАО|ЗАО|ПАО|АО|ИП|ГБУЗ|ГБУ|АНО|НКО)",
        "noncourt",
    ),
    Rule(
        "gov_body",
        r"\b(?:Межрайонн\w+|Межрегиональн\w+|ИФНС|ФНС|Федеральн\w+\s+налогов\w+\s+служб\w+|"
        r"Управлени\w+\s+\w+|Министерств\w+|Департамент\w*|Администраци\w+|"
        r"Пенсионн\w+\s+фонд\w*|Фонд\s+\w+|Государственн\w+\s+учреждени\w+)\s+[^\n,;]{3,120}",
        "noncourt",
    ),
    # --- финансовое ---
    Rule("money", r"\b\d[\d\s\u00a0]{2,}(?:[.,]\d{1,2})?\s*(?:руб\w*|₽|тыс\.?\s*руб\w*|млн\w*|млрд\w*|долл\w*|USD|EUR|евро)\b", "noncourt"),
    Rule("account_terms", r"\b(?:расчётн\w+|расчетн\w+|р/с|к/с|корр\.?\s*сч\w*|лицев\w+\s+сч\w*|счёт|счет)\s*[:№]?\s*[\d\s]{5,25}", "noncourt"),
    # --- документные номера ---
    Rule("doc_no", r"№\s*(\d[\d\s\-]{2,})", "noncourt", group=1),
    Rule("long_number", r"\b\d{15,}\b", "always"),
]

# Суд и участники: эти совпадения НЕ маскируем в режиме судебного акта
COURT_KEEP = re.compile(
    r"(?:суд|суда|суду|судом|суде|судебн\w+|арбитражн\w+|кассационн\w+|апелляционн\w+|"
    r"миров\w+\s+суд\w+|судья|судьи|судье|судью|секретар\w+|прокурор\w*|"
    r"истц\w+|ответчик\w*|заявител\w+|треть\w+\s+лиц\w+|представител\w+|"
    r"свидетел\w+|эксперт\w*|специалист\w*|переводчик\w*|присяжн\w+|"
    r"court|judge|plaintiff|defendant|witness|expert|attorney|counsel)\b",
    re.IGNORECASE,
)

# идентификаторы: в судебных актах скрываются, если не указан --court-keep-ids
ID_RULES = {
    "inn", "kpp", "ogrn", "snils", "passport_series", "passport_code",
    "phone_ru", "email", "bank_acc", "bik", "long_number",
}

COURT_MARKERS = [
    r"\bсуд(?:а|у|ом|е|ья|ьи)?\b", r"дело\s*№", r"истц", r"ответчик", r"заявител",
    r"решение", r"постановление", r"определение", r"приговор", r"прокурор",
    r"судья", r"апелляц", r"кассац", r"третье лицо", r"судебное заседание",
    r"court", r"plaintiff", r"defendant",
]


# --------------------------------------------------------------------------- #
#  Утилиты
# --------------------------------------------------------------------------- #


def validate(kind: Optional[str], s: str) -> bool:
    digits = re.sub(r"\D", "", s)
    if kind == "inn":
        return inn10_ok(digits) if len(digits) == 10 else inn12_ok(digits) if len(digits) == 12 else False
    if kind == "ogrn":
        return ogrn_ok(digits)
    if kind == "snils":
        return snils_ok(digits)
    if kind == "passport":
        return 1 <= int(digits[4:6] or 0) <= 31
    return True


def is_court_act(text: str) -> Tuple[bool, List[str]]:
    hits = [p for p in COURT_MARKERS if re.search(p, text, re.IGNORECASE)]
    strong = bool(re.search(r"дело\s*№|судебн\w+\s+(?:акт|заседани)|СУД\b|истец|ответчик", text, re.IGNORECASE))
    return (len(hits) >= 4 and strong), hits


# --------------------------------------------------------------------------- #
#  Разбор страницы на строки со словами
# --------------------------------------------------------------------------- #


@dataclass
class Word:
    text: str
    rect: pymupdf.Rect


@dataclass
class Line:
    text: str
    words: List[Word]
    starts: List[int]  # смещение начала каждого слова в text

    def rects_for(self, a: int, b: int) -> List[pymupdf.Rect]:
        out = []
        for w, st in zip(self.words, self.starts):
            if st < b and st + len(w.text) > a:
                out.append(w.rect)
        return out


def _group_lines(words, joiner=" ") -> List[Line]:
    lines: List[Line] = []
    buf_text, buf_words, starts = "", [], []
    for w in words:
        if buf_words:
            buf_text += joiner
        starts.append(len(buf_text))
        buf_text += w.text
        buf_words.append(w)
    if buf_words:
        lines.append(Line(buf_text, buf_words, starts))
    return lines


def lines_from_text(text: str) -> List[Line]:
    """Строки с точными смещениями внутри исходного текста."""
    lines: List[Line] = []
    for raw in text.split("\n"):
        if not raw.strip():
            continue
        words, starts = [], []
        for m in re.finditer(r"\S+", raw):
            words.append(Word(m.group(), pymupdf.Rect(0, 0, 0, 0)))
            starts.append(m.start())
        lines.append(Line(raw, words, starts))
    return lines


def lines_with_offsets(text: str) -> List[Tuple[int, Line]]:
    """То же, но с абсолютным смещением строки в тексте."""
    out: List[Tuple[int, Line]] = []
    pos = 0
    for raw in text.split("\n"):
        if raw.strip():
            words, starts = [], []
            for m in re.finditer(r"\S+", raw):
                words.append(Word(m.group(), pymupdf.Rect(0, 0, 0, 0)))
                starts.append(m.start())
            out.append((pos, Line(raw, words, starts)))
        pos += len(raw) + 1
    return out


def page_blocks(page: pymupdf.Page) -> List[Line]:
    """Блок текста, строки склеены: ловит значения, разорванные по строкам."""
    raw = page.get_text("words")
    buckets: Dict[int, List[Tuple[int, float, Word]]] = {}
    for x0, y0, x1, y1, w, b, l, _n in raw:
        if not w.strip():
            continue
        buckets.setdefault(b, []).append((l, x0, Word(w, pymupdf.Rect(x0, y0, x1, y1))))
    out: List[Line] = []
    for b in sorted(buckets):
        ws = [t[2] for t in sorted(buckets[b], key=lambda t: (t[0], t[1]))]
        out.append(_group_lines(ws)[0])
    return out


# правила, которым нужен сквозной проход по блоку (значение разбито на строки)
BLOCK_RULES = {
    "passport_series", "passport_code", "snils", "phone_ru", "bank_acc", "bik",
    "inn", "kpp", "ogrn", "long_number", "gov_body", "legal_entity",
    "addr_street", "addr_house", "city_label", "region", "city",
}


def _is_upperish(s: str) -> bool:
    """Строка в основном КАПСОМ (допускаем метку/OCR-шум)."""
    letters = [c for c in s if c.isalpha()]
    if len(letters) < 3:
        return False
    return sum(1 for c in letters if c.isupper()) / len(letters) >= 0.7


def merge_upper_runs(lines: List[Line]) -> List[Line]:
    """Склейка подряд идущих строк КАПСОМ (шапки, штампы, длинные названия)."""
    if not lines:
        return []
    lines = sorted(lines, key=lambda ln: (round(ln.words[0].rect.y0, 1), ln.words[0].rect.x0))
    runs: List[Line] = []
    cur: List[Line] = []
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
                runs.append(_group_lines([w for l in cur for w in l.words])[0])
            cur = [ln] if upper else []
    if len(cur) > 1:
        runs.append(_group_lines([w for l in cur for w in l.words])[0])
    return runs


def page_upper_runs(page: pymupdf.Page) -> List[Line]:
    return merge_upper_runs(page_lines_text_layer(page))


def passport_pairs_from_words(words: List[Word]) -> List[pymupdf.Rect]:
    """Серия и номер паспорта часто лежат в разных ячейках: ищем пару по геометрии."""
    fours = [w for w in words if re.fullmatch(r"\d{4}", w.text)]
    sixes = [w for w in words if re.fullmatch(r"\d{6}", w.text)]
    out: List[pymupdf.Rect] = []
    for f in fours:
        best = None
        for s in sixes:
            dx = s.rect.x0 - f.rect.x1
            dy = s.rect.y0 - f.rect.y0
            if -10 <= dx <= 300 and -40 <= dy <= 80 and abs(dy) <= 80:
                if best is None or abs(dx) + abs(dy) < best[0]:
                    best = (abs(dx) + abs(dy), s)
        if best:
            out.append(f.rect | best[1].rect)
    return out


def passport_pairs(page: pymupdf.Page) -> List[pymupdf.Rect]:
    words = [Word(w, pymupdf.Rect(x0, y0, x1, y1))
             for x0, y0, x1, y1, w, *_ in page.get_text("words") if w.strip()]
    return passport_pairs_from_words(words)


def page_lines_text_layer(page: pymupdf.Page) -> List[Line]:
    raw = page.get_text("words")
    buckets: Dict[Tuple[int, int], List[Word]] = {}
    for x0, y0, x1, y1, w, b, l, _n in raw:
        if not w.strip():
            continue
        buckets.setdefault((b, l), []).append(Word(w, pymupdf.Rect(x0, y0, x1, y1)))
    lines = []
    for key in sorted(buckets):
        ws = sorted(buckets[key], key=lambda x: x.rect.x0)
        lines.append(_group_lines(ws)[0])
    return lines


def find_tesseract() -> Optional[str]:
    cmd = os.environ.get("TESSERACT_CMD")
    if cmd and os.path.exists(cmd):
        return cmd
    for p in (
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
    ):
        if os.path.exists(p):
            return p
    return shutil.which("tesseract")


def tesseract_env() -> dict:
    env = os.environ.copy()
    local = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_tools", "tessdata")
    if os.path.isdir(local):
        env["TESSDATA_PREFIX"] = local
    return env


def ocr_lines(page: pymupdf.Page, exe: str, dpi: int, lang: str = "rus+eng") -> List[Line]:
    pix = page.get_pixmap(dpi=dpi, alpha=False)
    with tempfile.TemporaryDirectory() as td:
        img = os.path.join(td, "p.png")
        pix.save(img)
        res = subprocess.run(
            [exe, img, "stdout", "-l", lang, "--psm", "3", "tsv"],
            capture_output=True, check=True, env=tesseract_env(),
        )
    rows = res.stdout.decode("utf-8", "replace").splitlines()
    scale = 72.0 / dpi
    buckets: Dict[Tuple[int, int, int], List[Word]] = {}
    for row in rows[1:]:
        f = row.split("\t")
        if len(f) < 12 or not f[11].strip():
            continue
        block, par, line = int(f[2]), int(f[3]), int(f[4])
        left, top, w, h = int(f[6]), int(f[7]), int(f[8]), int(f[9])
        rect = pymupdf.Rect(left * scale, top * scale, (left + w) * scale, (top + h) * scale)
        buckets.setdefault((block, par, line), []).append(Word(f[11].strip(), rect))
    lines = []
    for key in sorted(buckets):
        ws = sorted(buckets[key], key=lambda x: x.rect.x0)
        lines.append(_group_lines(ws)[0])
    return lines


# --------------------------------------------------------------------------- #
#  Поиск ФИО
# --------------------------------------------------------------------------- #

PATRONYMIC_END = re.compile(
    r"(?:ович|евич|ьевич|иевич|овна|евна|ьевна|иевна|ична|инична)$", re.IGNORECASE
)
SURNAME_END = re.compile(
    r"(?:ов|ев|ёв|ин|ын|ский|цкий|ская|цкая|ой|ый|ая|ко|ук|юк|ян|дзе|швили|енко|чук|ич|их|ых|son|s|ova|ev|in)$",
    re.IGNORECASE,
)
STRICT_SURNAME_END = re.compile(
    r"(?:ов|ев|ёв|ин|ын|ский|цкий|ская|цкая|ко|ук|юк|ян|дзе|швили|енко|чук|ич|их|ых)$",
    re.IGNORECASE,
)
NAME_STOPWORDS = {
    "российской", "федерации", "россия", "республики", "области", "края", "района",
    "города", "инспекции", "службы", "налоговой", "федеральной", "россии", "город",
    "улица", "государства", "паспорт", "справка", "сведения", "заявление",
}
NAME_MARKERS = {
    "гр", "гр.", "гражданин", "гражданка", "гражданина", "ф.и.о", "ф.и.о.", "фио",
    "ип", "лице", "представитель", "представителя", "судья", "судьи", "секретарь",
    "секретаря", "прокурор", "прокурора", "эксперт", "эксперта", "свидетель", "свидетеля",
    "истец", "истца", "ответчик", "ответчика", "заявитель", "заявителя", "mr", "mrs", "ms", "dr",
}


def _tokenize_cyr(line: Line) -> List[Tuple[int, int, str]]:
    return [(m.start(), m.end(), m.group()) for m in re.finditer(r"[А-Яа-яЁё][А-Яа-яЁё\-]*|\d+", line.text)]


def find_names(line: Line) -> List[Tuple[int, int]]:
    toks = _tokenize_cyr(line)
    spans: List[Tuple[int, int]] = []
    n = len(toks)

    def is_name_tok(t: str) -> bool:
        return bool(re.fullmatch(r"[А-ЯЁ][А-Яа-яЁё\-]+", t)) and len(t) > 1

    for i, (a, b, t) in enumerate(toks):
        low = t.lower()
        if low in NAME_STOPWORDS:
            continue
        # 1) отчество -> захватываем 2 предыдущих токена
        if PATRONYMIC_END.search(low) and is_name_tok(t):
            j = i
            while j > 0 and i - j < 2 and is_name_tok(toks[j - 1][2]):
                j -= 1
            spans.append((toks[j][0], b))
            continue
        # 2) фамилия + известное имя
        if SURNAME_END.search(low) and i + 1 < n and toks[i + 1][2].lower() in GIVEN_NAMES:
            end = toks[i + 1][1]
            if i + 2 < n and PATRONYMIC_END.search(toks[i + 2][2].lower()):
                end = toks[i + 2][1]
            spans.append((a, end))
            continue
        # 3) имя из справочника + фамилия-подобный токен
        if low in GIVEN_NAMES and i + 1 < n and STRICT_SURNAME_END.search(toks[i + 1][2].lower()):
            spans.append((a, toks[i + 1][1]))
            continue
        # 4) маркер перед именем (только явно имя-подобный токен)
        if i > 0 and toks[i - 1][2].lower() in NAME_MARKERS:
            nxt = toks[i][2].lower()
            if not (nxt in GIVEN_NAMES or (is_name_tok(toks[i][2]) and STRICT_SURNAME_END.search(nxt))):
                continue
            end = b
            for k in (i + 1, i + 2):
                if k < n and is_name_tok(toks[k][2]) and toks[k][2].lower() not in NAME_STOPWORDS:
                    end = toks[k][1]
            spans.append((a, end))
            continue
        # 5) инициалы: Иванов И. И.
        if re.fullmatch(r"[А-ЯЁ]\.", t) and i > 0 and STRICT_SURNAME_END.search(toks[i - 1][2].lower()):
            spans.append((toks[i - 1][0], b))

    merged: List[Tuple[int, int]] = []
    for a, b in sorted(spans):
        if merged and a <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b))
        else:
            merged.append((a, b))
    return merged


def english_names(line: Line) -> List[Tuple[int, int]]:
    out = []
    for m in re.finditer(
        r"\b(?:Mr|Mrs|Ms|Dr|Prof)\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\b"
        r"|\b[A-Z][a-z]{2,}\s+[A-Z][a-z]{2,}(?=\s+(?:was|is|said|testified|appeared))",
        line.text,
    ):
        out.append((m.start(), m.end()))
    return out


# --------------------------------------------------------------------------- #
#  Основная логика PDF
# --------------------------------------------------------------------------- #


def collect_hits(lines: List[Line], mode: str, only_ids: Optional[set] = None,
                 court_keep_ids: bool = False):
    rects: List[Tuple[pymupdf.Rect, str]] = []
    stats: Dict[str, int] = {}
    compiled = [(r, re.compile(r.pattern, r.flags)) for r in RULES
                if only_ids is None or r.id in only_ids]

    for line in lines:
        if not line.text.strip():
            continue
        for rule, rx in compiled:
            if rule.scope == "noncourt" and mode == "judicial":
                continue
            if mode == "judicial" and court_keep_ids and rule.id in ID_RULES:
                continue
            for m in rx.finditer(line.text):
                if rule.validator and not validate(rule.validator, m.group()):
                    continue
                if mode == "judicial" and COURT_KEEP.search(m.group()):
                    continue
                if rule.id == "gov_body" and re.search(r"Наименование\s+$", line.text[:m.start()]):
                    continue
                g = rule.group
                a = m.start(g) if g else m.start()
                b = m.end(g) if g else m.end()
                if a < 0 or b < 0:
                    a, b = m.start(), m.end()
                for r in line.rects_for(a, b):
                    rects.append((r, rule.id))
                stats[rule.id] = stats.get(rule.id, 0) + 1
        # ФИО
        if mode != "judicial" and only_ids is None:  # в судебных актах ФИО участников сохраняем
            for a, b in find_names(line) + english_names(line):
                for r in line.rects_for(a, b):
                    rects.append((r, "person_name"))
                stats["person_name"] = stats.get("person_name", 0) + 1
    return rects, stats


def merge_rects(rects: Sequence[pymupdf.Rect], pad: float = 1.2) -> List[pymupdf.Rect]:
    out: List[pymupdf.Rect] = []
    for r in rects:
        r = pymupdf.Rect(r.x0 - pad, r.y0 - pad, r.x1 + pad, r.y1 + pad)
        for i, o in enumerate(out):
            if o.intersects(r):
                out[i] = o | r
                break
        else:
            out.append(r)
    return out


def collect_segments(page: pymupdf.Page) -> List[Tuple[float, float, float, float, float, Tuple]]:
    """Горизонтальные/вертикальные штрихи (подчёркивания, границы) до редактирования."""
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
                segs += [
                    (r.x0, r.y0, r.x1, r.y0, w, tuple(color)),
                    (r.x0, r.y1, r.x1, r.y1, w, tuple(color)),
                    (r.x0, r.y0, r.x0, r.y1, w, tuple(color)),
                    (r.x1, r.y0, r.x1, r.y1, w, tuple(color)),
                ]
    return segs


def restore_lines(page: pymupdf.Page, boxes: Sequence[pymupdf.Rect],
                  segs: Sequence[Tuple[float, float, float, float, float, Tuple]]) -> int:
    """Возвращает подчёркивания/рамки, случайно закрытые белой плашкой."""
    drawn = 0
    for x0, y0, x1, y1, w, color in segs:
        horiz = abs(y1 - y0) <= 0.8 and x1 - x0 > 1
        vert = abs(x1 - x0) <= 0.8 and y1 - y0 > 1
        if not (horiz or vert):
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


def redact_pdf(src: str, dst: str, mode: str, ocr: str, dpi: int, keep_meta: bool = False,
               court_keep_ids: bool = False):
    doc = pymupdf.open(src)
    exe = find_tesseract()
    report = {"file": os.path.basename(src), "mode": mode, "pages": doc.page_count, "rules": {},
              "ocr_pages": 0, "rects": 0, "engine": []}

    full_text = "".join(p.get_text() for p in doc)
    if mode == "auto":
        is_court, markers = is_court_act(full_text)
        mode = "judicial" if is_court else "document"
        report["mode"] = mode
        report["court_markers"] = markers[:6]

    for pno, page in enumerate(doc):
        text = page.get_text().strip()
        image_only = False
        need_ocr = ocr == "always" or (ocr == "auto" and len(text) < 40)
        if need_ocr and exe:
            lines = ocr_lines(page, exe, dpi)
            report["ocr_pages"] += 1
            report["engine"].append(f"p{pno + 1}:tesseract")
            image_only = True
            extras = [merge_upper_runs(lines)]
            words = [w for ln in lines for w in ln.words]
        else:
            lines = page_lines_text_layer(page)
            report["engine"].append(f"p{pno + 1}:textlayer")
            extras = [page_blocks(page), merge_upper_runs(lines)]
            words = [Word(w, pymupdf.Rect(x0, y0, x1, y1))
                     for x0, y0, x1, y1, w, *_ in page.get_text("words") if w.strip()]

        rects, stats = collect_hits(lines, mode, court_keep_ids=court_keep_ids)
        for extra in extras:
            r2, s2 = collect_hits(extra, mode, only_ids=BLOCK_RULES, court_keep_ids=court_keep_ids)
            rects.extend(r2)
            for k, v in s2.items():
                stats[k] = stats.get(k, 0) + v
        if mode != "judicial" and not court_keep_ids:
            for pr in passport_pairs_from_words(words):
                rects.append((pr, "passport_pair"))
                stats["passport_pair"] = stats.get("passport_pair", 0) + 1
        for k, v in stats.items():
            report["rules"][k] = report["rules"].get(k, 0) + v
        boxes = merge_rects([r for r, _ in rects])
        report["rects"] += len(boxes)

        if image_only:
            # нет текстового слоя: выжигаем пиксели, собираем страницу заново
            pix = page.get_pixmap(dpi=dpi, alpha=False)
            im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            dr = ImageDraw.Draw(im)
            sc = pix.width / page.rect.width
            for b in boxes:
                dr.rectangle([b.x0 * sc, b.y0 * sc, b.x1 * sc, b.y1 * sc], fill=(255, 255, 255))
            rect = page.rect
            doc.delete_page(pno)
            new_page = doc.new_page(pno=pno, width=rect.width, height=rect.height)
            new_page.insert_image(rect, stream=_png_bytes(im))
        else:
            segs = collect_segments(page)
            for b in boxes:
                page.add_redact_annot(b, fill=(1, 1, 1), cross_out=False)
            if boxes:
                page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE)
                report["restored_lines"] = report.get("restored_lines", 0) + restore_lines(page, boxes, segs)

    if not keep_meta:
        doc.set_metadata({})
    doc.save(dst, garbage=4, deflate=True, clean=True)
    doc.close()
    return report


def _png_bytes(im: Image.Image) -> bytes:
    import io

    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


# --------------------------------------------------------------------------- #
#  DOCX -> MD и текстовая анонимизация
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
            elif "list" in style or p._p.pPr is not None and p._p.pPr.numPr is not None:
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


def anonymize_text(text: str, mode: str = "auto", court_keep_ids: bool = False) -> Tuple[str, Dict[str, int]]:
    is_court, _ = is_court_act(text)
    if mode == "auto":
        mode = "judicial" if is_court else "document"
    stats: Dict[str, int] = {}

    def sub(rule: Rule, rx: re.Pattern, s: str) -> str:
        def repl(m: re.Match) -> str:
            if rule.validator and not validate(rule.validator, m.group()):
                return m.group()
            if mode == "judicial" and COURT_KEEP.search(m.group()):
                return m.group()
            stats[rule.id] = stats.get(rule.id, 0) + 1
            if rule.group:
                whole = m.group(0)
                gs = m.start(rule.group) - m.start(0)
                ge = m.end(rule.group) - m.start(0)
                if gs >= 0 and ge >= 0:
                    return whole[:gs] + PLACEHOLDER + whole[ge:]
            return PLACEHOLDER
        return rx.sub(repl, s)

    for rule in sorted(RULES, key=lambda r: -len(r.pattern)):
        if rule.scope == "noncourt" and mode == "judicial":
            continue
        if mode == "judicial" and court_keep_ids and rule.id in ID_RULES:
            continue
        text = sub(rule, re.compile(rule.pattern, rule.flags), text)

    if mode != "judicial":
        spans: List[Tuple[int, int]] = []
        for base, ln in lines_with_offsets(text):
            spans.extend((base + a, base + b) for a, b in find_names(ln) + english_names(ln))
        spans.sort()
        merged: List[Tuple[int, int]] = []
        for a, b in spans:
            if merged and a <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], b))
            else:
                merged.append((a, b))
        if merged:
            rebuilt, cursor = [], 0
            for a, b in merged:
                rebuilt.append(text[cursor:a])
                rebuilt.append(PLACEHOLDER)
                cursor = b
                stats["person_name"] = stats.get("person_name", 0) + 1
            rebuilt.append(text[cursor:])
            text = "".join(rebuilt)

    return text, stats


# --------------------------------------------------------------------------- #
#  Верификация результата
# --------------------------------------------------------------------------- #


def verify_pdf(src: str, dst: str, mode: str, ocr: str, dpi: int) -> Dict[str, object]:
    """Проверяем, что в выходном PDF не осталось распознаваемого PII и под плашками пусто."""
    doc = pymupdf.open(dst)
    text = "".join(p.get_text() for p in doc)
    _, leftover = collect_hits(lines_from_text(text), mode)
    return {
        "leftover_rules": leftover,
        "chars_left": len(text),
        "images": sum(len(p.get_images()) for p in doc),
    }


# --------------------------------------------------------------------------- #
#  CLI
# --------------------------------------------------------------------------- #


def main(argv: Optional[Sequence[str]] = None) -> int:
    global PLACEHOLDER
    ap = argparse.ArgumentParser(description="Обезличивание документов RU/EN")
    ap.add_argument("input")
    ap.add_argument("-o", "--out", help="файл результата")
    ap.add_argument("--mode", default="auto", choices=["auto", "judicial", "document"])
    ap.add_argument("--ocr", default="auto", choices=["auto", "always", "never"])
    ap.add_argument("--dpi", type=int, default=300)
    ap.add_argument("--placeholder", default=PLACEHOLDER)
    ap.add_argument("--keep-meta", action="store_true")
    ap.add_argument("--court-keep-ids", action="store_true",
                    help="в судебных актах не скрывать ИНН/ОГРН/СНИЛС/паспорт")
    ap.add_argument("--report", help="куда записать JSON-отчёт")
    args = ap.parse_args(argv)

    PLACEHOLDER = args.placeholder

    src = args.input
    ext = os.path.splitext(src)[1].lower()
    base = os.path.splitext(os.path.basename(src))[0]

    if ext == ".pdf":
        dst = args.out or f"{base}_anon.pdf"
        rep = redact_pdf(src, dst, args.mode, args.ocr, args.dpi, args.keep_meta, args.court_keep_ids)
        rep.update(verify_pdf(src, dst, rep["mode"], args.ocr, args.dpi))
    elif ext in (".docx", ".doc"):
        md = docx_to_md(src)
        anon, stats = anonymize_text(md, args.mode, args.court_keep_ids)
        dst = args.out or f"{base}_anon.md"
        with open(dst, "w", encoding="utf-8") as f:
            f.write(anon)
        rep = {"file": os.path.basename(src), "converted_to_md": True, "rules": stats}
    elif ext in (".md", ".markdown", ".txt"):
        with open(src, encoding="utf-8") as f:
            anon, stats = anonymize_text(f.read(), args.mode, args.court_keep_ids)
        dst = args.out or f"{base}_anon.md"
        with open(dst, "w", encoding="utf-8") as f:
            f.write(anon)
        rep = {"file": os.path.basename(src), "rules": stats}
    else:
        print(f"Неподдерживаемый формат: {ext}", file=sys.stderr)
        return 2

    rep["output"] = dst
    if args.report:
        with open(args.report, "w", encoding="utf-8") as f:
            json.dump(rep, f, ensure_ascii=False, indent=2)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
