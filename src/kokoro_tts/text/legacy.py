"""Built-in conservative Chinese text normalization.

This module keeps AngeVoice's lightweight 2.6.x TN rules separate from model
runtime code. It intentionally covers common TTS cases only: dates, times,
amounts, percentages, phone-like long numbers, and plain numeric input.
"""

from __future__ import annotations

import re

from ..zh_rules import normalize_chinese_rules

_DIGITS_ZH = {
    "0": "零",
    "1": "一",
    "2": "二",
    "3": "三",
    "4": "四",
    "5": "五",
    "6": "六",
    "7": "七",
    "8": "八",
    "9": "九",
}
_DIGITS_ZH_READING = {**_DIGITS_ZH, "1": "幺"}

_DATE_CONTEXT_BEFORE = (
    "日期", "日子", "生日", "活动", "会议", "考试", "开会", "发布", "上线", "更新",
    "维护", "开服", "截止", "截至", "预约", "计划", "预计", "定在", "改到",
    "推迟到", "提前到", "报名", "放假", "假期", "档期", "排期", "工期", "节日",
)
_DATE_CONTEXT_AFTER = (
    "号", "日", "当天", "那天", "这天", "之前", "之后", "以前", "以后", "前", "后",
    "开始", "结束", "上线", "发布", "更新", "开服", "维护", "截止", "截至", "报名",
    "活动", "会议", "考试", "开会", "放假", "假期", "见", "再说",
)
_DATE_CONTEXT_WORDS = ("今天", "明天", "昨天", "后天", "前天", "今年", "明年", "去年", "本月", "下月", "上月")


def spell_digits(text: str, use_yao: bool = False) -> str:
    """Read a digit sequence character-by-character."""

    table = _DIGITS_ZH_READING if use_yao else _DIGITS_ZH
    return "".join(table.get(ch, ch) for ch in text)


def _read_under_10000(value: int) -> str:
    if value == 0:
        return "零"
    units = ["", "十", "百", "千"]
    parts: list[str] = []
    zero_pending = False
    pos = 0
    n = value

    while n > 0:
        digit = n % 10
        if digit == 0:
            if parts:
                zero_pending = True
        else:
            part = _DIGITS_ZH[str(digit)] + units[pos]
            if zero_pending:
                parts.append("零")
                zero_pending = False
            parts.append(part)
        n //= 10
        pos += 1

    spoken = "".join(reversed(parts)).rstrip("零")
    if spoken.startswith("一十"):
        spoken = spoken[1:]
    return spoken or "零"


def read_small_int(value: int) -> str:
    """Read an integer in common Chinese numeric form."""

    if value < 0:
        return "负" + read_small_int(-value)
    if value < 10000:
        return _read_under_10000(value)

    group_units = ["", "万", "亿", "兆", "京"]
    groups: list[int] = []
    number = int(value)
    while number > 0:
        groups.append(number % 10000)
        number //= 10000

    if len(groups) > len(group_units):
        return spell_digits(str(value))

    parts: list[str] = []
    zero_pending = False
    for index in range(len(groups) - 1, -1, -1):
        group = groups[index]
        if group == 0:
            if parts:
                zero_pending = True
            continue
        if parts and (zero_pending or group < 1000):
            parts.append("零")
        zero_pending = False
        parts.append(_read_under_10000(group) + group_units[index])
    return "".join(parts) or "零"


def _read_time_hour(value: int) -> str:
    return "两" if value == 2 else read_small_int(value)


def _read_clock_time(hour: int, minute: int) -> str:
    spoken = _read_time_hour(hour) + "点"
    if minute == 0:
        return spoken + "整"
    if minute < 10:
        return spoken + "零" + _DIGITS_ZH[str(minute)] + "分"
    return spoken + read_small_int(minute) + "分"


def _read_month_day(month: int, day: int) -> str:
    return f"{read_small_int(month)}月{read_small_int(day)}日"


def _looks_like_short_date_context(text: str, start: int, end: int) -> bool:
    """Heuristically decide whether M.D / M-D means month-day."""

    before = text[max(0, start - 8):start]
    after = text[end:end + 8]
    if any(after.startswith(item) for item in _DATE_CONTEXT_AFTER):
        return True
    if any(item in before for item in _DATE_CONTEXT_BEFORE):
        return True
    if any(item in before or item in after for item in _DATE_CONTEXT_WORDS):
        return True
    if before.endswith(("在", "于", "到", "从", "至", "距", "等到")) and not after.startswith(("版", "版本", "元", "%")):
        return True
    return False


def normalize_short_month_day(text: str) -> str:
    """Normalize contextual M.D dates before decimal processing."""

    def repl(match: re.Match[str]) -> str:
        month = int(match.group("month"))
        day = int(match.group("day"))
        if not (1 <= month <= 12 and 1 <= day <= 31):
            return match.group(0)
        if not _looks_like_short_date_context(text, match.start(), match.end()):
            return match.group(0)
        return _read_month_day(month, day)

    return re.sub(
        r"(?<![\dA-Za-z])(?P<month>1[0-2]|0?[1-9])[./-](?P<day>3[01]|[12]\d|0?[1-9])(?![\dA-Za-z])",
        repl,
        text,
    )


def _read_decimal_amount(raw: str) -> str:
    number = raw.replace(",", "")
    integer, dot, frac = number.partition(".")
    spoken = read_small_int(int(integer))
    if dot and frac:
        spoken += "点" + spell_digits(frac)
    return spoken


def _read_money_amount(raw: str) -> str:
    number = raw.replace(",", "")
    integer, dot, frac = number.partition(".")
    spoken = read_small_int(int(integer)) + "元"
    if dot and frac:
        frac = (frac + "00")[:2]
        if frac[0] != "0":
            spoken += _DIGITS_ZH[frac[0]] + "角"
        if frac[1] != "0":
            spoken += _DIGITS_ZH[frac[1]] + "分"
    return spoken


def normalize_calendar_dates(text: str) -> str:
    """Normalize explicit Gregorian dates without touching versions."""

    if not text:
        return text

    def repl_date(match):
        year, month, day = match.groups()
        return f"{spell_digits(year)}年{read_small_int(int(month))}月{read_small_int(int(day))}日"

    normalized = re.sub(r"(?<!\d)(20\d{2}|19\d{2})[-/.](\d{1,2})[-/.](\d{1,2})(?:[日号])?(?!\d)", repl_date, text)
    return normalize_short_month_day(normalized)


def normalize_text_for_tts(text: str, model: str = "kokoro") -> str:
    """Normalize common Chinese TTS text patterns conservatively."""

    if not text:
        return text

    def repl_thousand_money(match):
        _prefix, sign, amount, _suffix = match.groups()
        spoken = _read_money_amount(amount)
        return ("负" if sign == "-" else "") + spoken

    text = re.sub(
        r"(?<![\dA-Za-z])(¥|￥)?([+-]?)(\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?)(元)?(?![\dA-Za-z])",
        lambda m: repl_thousand_money(m) if (m.group(1) or m.group(4)) else m.group(0),
        text,
    )

    def repl_thousand_number(match):
        raw = match.group(0)
        percent = raw.endswith("%")
        if percent:
            raw = raw[:-1]
        sign = ""
        if raw.startswith(("+", "-")):
            sign, raw = raw[0], raw[1:]
        try:
            spoken = _read_decimal_amount(raw)
        except ValueError:
            number = raw.replace(",", "")
            integer, dot, frac = number.partition(".")
            spoken = spell_digits(integer)
            if dot and frac:
                spoken += "点" + spell_digits(frac)
        negative = sign == "-"
        if percent:
            return ("负" if negative else "") + "百分之" + spoken
        if negative:
            spoken = "负" + spoken
        return spoken

    text = re.sub(r"(?<![\dA-Za-z¥￥])[-+]?\d{1,3}(?:,\d{3})+(?:\.\d+)?%?(?![\dA-Za-z])", repl_thousand_number, text)
    text = normalize_calendar_dates(text)

    def repl_time(match):
        hour = int(match.group(1))
        minute = int(match.group(2))
        return _read_clock_time(hour, minute)

    text = re.sub(r"(?<!\d)([01]?\d|2[0-3])[:：]([0-5]\d)(?!\d)", repl_time, text)

    def repl_money(match):
        prefix, amount, suffix = match.groups()
        if not prefix and not suffix:
            return match.group(0)
        return _read_money_amount(amount)

    text = re.sub(r"(?<![\dA-Za-z])(¥|￥)?(\d{1,16}(?:\.\d{1,2})?)(元)?(?![\dA-Za-z])", repl_money, text)

    def repl_percent(match):
        sign = match.group(1) or ""
        value = match.group(2)
        integer, dot, frac = value.partition(".")
        try:
            spoken = read_small_int(int(integer))
        except ValueError:
            spoken = spell_digits(integer)
        if dot and frac:
            spoken += "点" + spell_digits(frac)
        return ("负" if sign == "-" else "") + "百分之" + spoken

    text = re.sub(r"(?<![\dA-Za-z])([+-]?)(\d+(?:\.\d+)?)%(?!\d)", repl_percent, text)

    def repl_mobile(match):
        number = match.group(0)
        return "，".join([
            spell_digits(number[:3], use_yao=True),
            spell_digits(number[3:7], use_yao=True),
            spell_digits(number[7:], use_yao=True),
        ])

    text = re.sub(r"(?<!\d)1[3-9]\d{9}(?!\d)", repl_mobile, text)

    def repl_long_number(match):
        number = match.group(0)
        grouped = [number[i : i + 4] for i in range(0, len(number), 4)]
        return "，".join(spell_digits(group, use_yao=True) for group in grouped)

    text = re.sub(r"(?<!\d)\d{6,}(?!\d)", repl_long_number, text)

    def _signed_prefix(sign: str) -> str:
        return "负" if sign == "-" else ""

    def repl_plain_decimal(match):
        before = match.string[max(0, match.start() - 6):match.start()]
        after = match.string[match.end():match.end() + 6]
        if match.string.strip() != match.group(0):
            return match.group(0)
        if before.endswith(("版本", "版", "v", "V")) or after.startswith(("版", "版本")):
            return match.group(0)
        sign = match.group(1) or ""
        integer = match.group(2)
        frac = match.group(3)
        try:
            spoken = read_small_int(int(integer))
        except ValueError:
            spoken = spell_digits(integer)
        return _signed_prefix(sign) + spoken + "点" + spell_digits(frac)

    text = re.sub(r"(?<![\dA-Za-z./])([+-]?)([0-9]{1,8})\.([0-9]{1,8})(?![\dA-Za-z])", repl_plain_decimal, text)

    def repl_trailing_number_dot(match):
        sign = match.group(1) or ""
        return _signed_prefix(sign) + read_small_int(int(match.group(2)))

    text = re.sub(r"(?<![\dA-Za-z./])([+-]?)([0-9]{1,5})\.(?![\dA-Za-z])", repl_trailing_number_dot, text)

    def repl_plain_int(match):
        sign = match.group(1) or ""
        return _signed_prefix(sign) + read_small_int(int(match.group(2)))

    text = re.sub(r"(?<![\dA-Za-z./])([+-]?)([0-9]{1,5})(?![\dA-Za-z./])", repl_plain_int, text)
    return normalize_chinese_rules(text, model=model)
