import json, os, sys
from pathlib import Path

APP_NAME = "TextAdjustment"
CFG_FILENAME = "[config]TextAdjustment_config.json"


def _resolve_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    else:
        return Path(__file__).resolve().parent


# ===== 実体パス =====
BASE_DIR: Path = _resolve_base_dir()
CFG_DIR: Path = BASE_DIR / "config"
CFG_PATH: Path = CFG_DIR / CFG_FILENAME

# フォルダを必ず作成
CFG_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> dict:
    """設定をJSONから読み込み"""
    try:
        if CFG_PATH.exists():
            with CFG_PATH.open("r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def save_config(cfg: dict) -> None:
    """設定をJSONへ保存"""
    try:
        with CFG_PATH.open("w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def get_config_path() -> str:
    """現在の設定ファイルのフルパスを返す（デバッグ用）"""
    return str(CFG_PATH)
