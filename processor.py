import os, re, unicodedata
from pathlib import Path
from typing import Iterable, Callable, Iterator, Optional

DEFAULT_TEXT_EXTS = {
    ".txt",".md",".csv",".tsv",".log",".json",".jsonl",".xml",".yml",".yaml",
    ".ini",".cfg",".conf",".py",".pyw",".js",".ts",".tsx",".jsx",".html",".htm",
    ".css",".scss",".less",".bat",".cmd",".sh",".ps1",".rs",".go",".java",".kt",
    ".c",".h",".cpp",".hpp",".cs",".rb",".php",".pl",".r",".jl",".lua"
}

# ===== カナ全角→半角 完全対応用テーブル =====
# 参考：一般的なUnicode互換マッピングを元に、濁点/半濁点を合成して半角に落とし込む
_DAKU = "\uFF9E"   # 半角濁点
_HANDA = "\uFF9F"  # 半角半濁点
_KANA_MAP = {
    "。":"｡","、":"､","・":"･","「":"｢","」":"｣","ー":"ｰ","〜":"~","：":":","；":";","！":"!","？":"?",
    "ァ":"ｧ","ア":"ｱ","ィ":"ｨ","イ":"ｲ","ゥ":"ｩ","ウ":"ｳ","ェ":"ｪ","エ":"ｴ","ォ":"ｫ","オ":"ｵ",
    "カ":"ｶ","キ":"ｷ","ク":"ｸ","ケ":"ｹ","コ":"ｺ",
    "サ":"ｻ","シ":"ｼ","ス":"ｽ","セ":"ｾ","ソ":"ｿ",
    "タ":"ﾀ","チ":"ﾁ","ツ":"ﾂ","テ":"ﾃ","ト":"ﾄ",
    "ナ":"ﾅ","ニ":"ﾆ","ヌ":"ﾇ","ネ":"ﾈ","ノ":"ﾉ",
    "ハ":"ﾊ","ヒ":"ﾋ","フ":"ﾌ","ヘ":"ﾍ","ホ":"ﾎ",
    "マ":"ﾏ","ミ":"ﾐ","ム":"ﾑ","メ":"ﾒ","モ":"ﾓ",
    "ヤ":"ﾔ","ャ":"ｬ","ユ":"ﾕ","ュ":"ｭ","ヨ":"ﾖ","ョ":"ｮ",
    "ラ":"ﾗ","リ":"ﾘ","ル":"ﾙ","レ":"ﾚ","ロ":"ﾛ",
    "ワ":"ﾜ","ヲ":"ｦ","ン":"ﾝ",
    "ヴ":"ｳ" + _DAKU,
    "ガ":"ｶ" + _DAKU, "ギ":"ｷ" + _DAKU, "グ":"ｸ" + _DAKU, "ゲ":"ｹ" + _DAKU, "ゴ":"ｺ" + _DAKU,
    "ザ":"ｻ" + _DAKU, "ジ":"ｼ" + _DAKU, "ズ":"ｽ" + _DAKU, "ゼ":"ｾ" + _DAKU, "ゾ":"ｿ" + _DAKU,
    "ダ":"ﾀ" + _DAKU, "ヂ":"ﾁ" + _DAKU, "ヅ":"ﾂ" + _DAKU, "デ":"ﾃ" + _DAKU, "ド":"ﾄ" + _DAKU,
    "バ":"ﾊ" + _DAKU, "ビ":"ﾋ" + _DAKU, "ブ":"ﾌ" + _DAKU, "ベ":"ﾍ" + _DAKU, "ボ":"ﾎ" + _DAKU,
    "パ":"ﾊ" + _HANDA,"ピ":"ﾋ" + _HANDA,"プ":"ﾌ" + _HANDA,"ペ":"ﾍ" + _HANDA,"ポ":"ﾎ" + _HANDA,
    "ヵ":"ｶ","ヶ":"ｹ","ヮ":"ﾜ","ヰ":"ｲ","ヱ":"ｴ",
    "ッ":"ｯ",
}

# ===== 文字カテゴリ =====
def is_ascii_eng(ch: str) -> bool:
    return ("A" <= ch <= "Z") or ("a" <= ch <= "z") or ("Ａ" <= ch <= "Ｚ") or ("ａ" <= ch <= "ｚ")

def is_digit(ch: str) -> bool:
    return ("0" <= ch <= "9") or ("０" <= ch <= "９")

def is_space(ch: str) -> bool:
    return ch == " " or ch == "\u3000"

def is_symbol(ch: str) -> bool:
    code = ord(ch)
    if 0x21 <= code <= 0x7E and not ch.isalnum() and ch != " ":
        return True
    if 0xFF01 <= code <= 0xFF5E:
        full = chr(code)
        if not ("Ａ" <= full <= "Ｚ" or "ａ" <= full <= "ｚ" or "０" <= full <= "９") and full != "　":
            return True
    return ch in "。、・「」『』（）［］｛｝〈〉《》【】—―…‥ー：；？！＝＋－×÷％〜＾￥｜"

def is_katakana(ch: str) -> bool:
    code = ord(ch)
    return (0x30A0 <= code <= 0x30FF)  # 全角カタカナ領域

def is_halfwidth_kana(ch: str) -> bool:
    code = ord(ch)
    return 0xFF61 <= code <= 0xFF9F

def convert_kana_fw_to_hw(ch: str) -> str:
    return _KANA_MAP.get(ch, ch)

def convert_ascii_to_fullwidth(ch: str) -> str:
    if ch == " ":
        return "\u3000"
    code = ord(ch)
    if 0x21 <= code <= 0x7E:
        return chr(code + 0xFEE0)
    return ch

def convert_fullwidth_ascii_to_half(ch: str) -> str:
    if ch == "\u3000":  # 全角スペース
        return " "
    code = ord(ch)
    if 0xFF01 <= code <= 0xFF5E:
        return chr(code - 0xFEE0)
    return ch

# ===== 幅変換（対象限定） =====
def convert_char(ch: str, mode: str, sets: dict, targets_set: set[str]) -> str:
    if mode == "none":
        return ch

    eligible = False
    if targets_set and ch in targets_set:
        eligible = True
    else:
        if sets.get("eng") and is_ascii_eng(ch): eligible = True
        if sets.get("num") and is_digit(ch): eligible = True
        if sets.get("space") and is_space(ch): eligible = True
        if sets.get("sym") and is_symbol(ch): eligible = True
        if sets.get("kata") and is_katakana(ch): eligible = True
    if not eligible:
        return ch

    if mode == "to_full":
        # 半角英数/記号/スペース → 全角、半角カナはNFKCで全角化
        if is_halfwidth_kana(ch):
            return unicodedata.normalize("NFKC", ch)
        return convert_ascii_to_fullwidth(ch)

    # to_half
    # 全角ASCII/スペースは普通に半角へ
    ch = convert_fullwidth_ascii_to_half(ch)
    # 全角カナ → 半角カナ（濁点合成）
    if is_katakana(ch) or ch in _KANA_MAP:
        return convert_kana_fw_to_hw(ch)
    return ch

def apply_width_transform(text: str, mode: str, targets: str, sets: dict) -> str:
    if mode == "none":
        return text
    targets_set = set(targets) if targets else set()
    out_chars = []
    for ch in text:
        out_chars.append(convert_char(ch, mode, sets, targets_set))
    return "".join(out_chars)

# ===== 改行挿入 =====
def _insert_breaks_literal(text: str, tokens: list[str], exclude_tokens: list[str], mode: str) -> str:
    if not tokens:
        return text
    placeholders = {}
    for ex in sorted(set(exclude_tokens), key=len, reverse=True):
        if not ex: continue
        ph = f"__EXCL_{hash(ex)}__"
        text = text.replace(ex, ph)
        placeholders[ph] = ex

    for t in sorted(set(tokens), key=len, reverse=True):
        if not t: continue
        if mode == "after":  text = text.replace(t, t + "\n")
        elif mode == "before": text = text.replace(t, "\n" + t)
        else:                text = text.replace(t, "\n" + t + "\n")

    for ph, ex in placeholders.items():
        text = text.replace(ph, ex)
    return text

def _insert_breaks_regex(text: str, tokens_regex: list[str], mode: str) -> str:
    if not tokens_regex:
        return text
    repl = {"after": r"\g<0>\n", "before": r"\n\g<0>", "around": r"\n\g<0>\n"}[mode]
    for pat in sorted(set(tokens_regex), key=len, reverse=True):
        if not pat: continue
        try:
            text = re.sub(pat, repl, text, flags=re.MULTILINE)
        except re.error:
            pass
    return text

# ===== 行頭/行末・空白行 =====
def _add_prefix_suffix(text: str, prefix: str, suffix: str) -> str:
    if not prefix and not suffix: return text
    return "\n".join(f"{prefix}{ln}{suffix}" for ln in text.splitlines())

def _remove_blank_lines(text: str) -> str:
    return "\n".join(line for line in text.splitlines() if line.strip())

# ===== 行スキップ保護 =====
def _protect_skipped_lines_for_break(text: str, pattern: str):
    if not pattern: return text, {}
    try: reg = re.compile(pattern, re.MULTILINE)
    except re.error: return text, {}
    lines = text.splitlines(False); protected = {}; kept=[]
    for i, ln in enumerate(lines):
        if reg.search(ln):
            tag = f"__SKIPLINE_{i}__"; protected[tag] = ln; kept.append(tag)
        else:
            kept.append(ln)
    return "\n".join(kept), protected

def _restore_protected_lines(text: str, protected: dict) -> str:
    for tag, ln in protected.items():
        text = text.replace(tag, ln)
    return text

# ===== メイン処理 =====
def process_text(text: str, settings: dict) -> str:
    # 0) 文字幅（対象限定）
    text = apply_width_transform(text,
                                 settings.get("width_mode","none"),
                                 settings.get("width_targets",""),
                                 settings.get("width_sets", {}))

    # 1) 行スキップ保護
    text, protected = _protect_skipped_lines_for_break(text, settings.get("skip_regex",""))

    # 2) 改行挿入
    mode = settings.get("break_mode","after")
    if settings.get("break_tokens_are_regex", False):
        text = _insert_breaks_regex(text, settings.get("break_tokens", []), mode)
    else:
        text = _insert_breaks_literal(text, settings.get("break_tokens", []),
                                      settings.get("break_exclude_tokens", []), mode)

    # 3) 行頭/行末
    text = _add_prefix_suffix(text, settings.get("prefix",""), settings.get("suffix",""))

    # 4) 空白行削除
    if settings.get("remove_blanks", False):
        text = _remove_blank_lines(text)

    # 5) 保護解除
    return _restore_protected_lines(text, protected)

# ====== 進捗対応：対象列挙 → ディレクトリ処理 ======
def enumerate_target_files(in_dir: str, exts: Iterable[str], recursive: bool) -> Iterator[Path]:
    src_root = Path(in_dir)
    exts_low = {e.lower() for e in exts}
    if recursive:
        for root, _, files in os.walk(src_root):
            rp = Path(root)
            for name in files:
                p = rp / name
                if p.suffix.lower() in exts_low:
                    yield p
    else:
        for p in src_root.iterdir():
            if p.is_file() and p.suffix.lower() in exts_low:
                yield p

def process_directory(
    in_dir: str, out_dir: str, settings: dict,
    progress_callback: Optional[Callable[[], None]] = None,
    is_canceled: Optional[Callable[[], bool]] = None
) -> int:
    src_root = Path(in_dir); dst_root = Path(out_dir)
    recursive = settings.get("recursive", True)
    exts = settings.get("exts") or DEFAULT_TEXT_EXTS
    count = 0

    for p in enumerate_target_files(in_dir, exts, recursive):
        if is_canceled and is_canceled():
            break
        try:
            rel = p.relative_to(src_root)
        except Exception:
            rel = p.name
        try:
            data = p.read_text(encoding="utf-8", errors="replace")
            out = process_text(data, settings)
            out_path = dst_root / rel
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(out, encoding="utf-8")
            count += 1
        except Exception:
            # 1件失敗しても続行
            pass
        finally:
            if progress_callback:
                progress_callback()
    return count
