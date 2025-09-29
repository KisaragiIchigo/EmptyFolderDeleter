import os
import sys
from datetime import datetime
from typing import Optional, Dict, Tuple

APP_TITLE = "空フォルダ削除ツール"
LOG_PREFIX = "[ERRORLOG][空フォルダ削除]"


SCAN_CACHE: Dict[str, Tuple[float, int]] = {}

def app_dir() -> str:
    """実行ファイルと同階層（exe時）/スクリプトのあるディレクトリ（通常時）"""
    if hasattr(sys, "_MEIPASS"):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(sys.argv[0]))

def resource_path(name: str) -> str:
    """PyInstaller --onefile 同梱リソースの参照（存在しなくてもそのまま返す）"""
    if hasattr(sys, "_MEIPASS"):
        p = os.path.join(sys._MEIPASS, name)
        if os.path.exists(p):
            return p
    local = os.path.join(os.getcwd(), name)
    if os.path.exists(local):
        return local
    script_side = os.path.join(app_dir(), name)
    return script_side

def save_error_log(target_path: str, error_message: str, file_name: Optional[str] = None) -> str:
    """エラー内容をログテキストで保存し、そのファイルパスを返す"""
    now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    base = file_name or f"{LOG_PREFIX}{now}.txt"
    out_path = os.path.join(app_dir(), base)
    lines = [
        f"エラー発生時刻: {now}",
        f"対象パス: {target_path}",
        f"エラー内容: {error_message}",
        "",
    ]
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return out_path

def cache_get(path: str) -> Optional[Tuple[float, int]]:
    """キャッシュ値を返す（なければNone）"""
    return SCAN_CACHE.get(path)

def cache_set(path: str, mtime: float, effective_count: int) -> None:
    """キャッシュを更新"""
    SCAN_CACHE[path] = (mtime, effective_count)

def cache_clear_under(root: str) -> None:
    """指定ルート配下のキャッシュをざっくり掃除（削除後などに呼ぶと安全）"""
    to_del = [k for k in SCAN_CACHE.keys() if k.startswith(root)]
    for k in to_del:
        SCAN_CACHE.pop(k, None)
