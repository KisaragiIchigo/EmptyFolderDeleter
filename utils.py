import os
import sys
import stat # ★追加
from datetime import datetime
from typing import Optional, Dict, Tuple, Sequence # ★Sequence 追加

APP_TITLE = "空フォルダ削除ツール"
LOG_PREFIX = "[ERRORLOG][空フォルダ削除]"

# processor.py から移動
IGNORABLE_FILES: Sequence[str] = ("Thumbs.db", "desktop.ini", ".DS_Store")

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

# === processor.py から移動・統合 ===

def _effective_count(dirpath: str, ignore_known_garbage: bool) -> int:
    """“実質空”評価での要素数（0なら空扱い）※キャッシュ用"""
    try:
        count = 0
        with os.scandir(dirpath) as it:
            for entry in it:
                if entry.is_dir(follow_symlinks=False):
                    return 1  # 子ディレクトリがある時点で空ではない
                if ignore_known_garbage and entry.name in IGNORABLE_FILES:
                    continue
                count += 1
                if count > 0:
                    return count # 1個でも見つかったら即終了
        return 0
    except Exception as e:
        save_error_log(dirpath, f"{type(e).__name__}: {e}")
        return 1  # 不明なら空ではない扱い

def is_dir_empty_cached(p: str, ignore_known_garbage: bool, fast_rescan: bool) -> bool:
    # 高速リスキャンが有効じゃないなら、キャッシュを使わず普通にカウント
    if not fast_rescan:
        return _effective_count(p, ignore_known_garbage) == 0
    
    # --- キャッシュ利用ロジック ---
    try:
        st = os.stat(p)
    except FileNotFoundError:
        return False # 既に消えてる
        
    cached = cache_get(p)
    if cached and cached[0] == st.st_mtime:
        # 更新日時が同じ＝変更なし とみなし、キャッシュ値を返す
        return cached[1] == 0
        
    # 変更あり or 新規 -> 再計測してキャッシュ更新
    cnt = _effective_count(p, ignore_known_garbage)
    cache_set(p, st.st_mtime, cnt)
    return cnt == 0

def _delete_known_garbage(dirpath: str) -> None:
    """既知ゴミファイルを削除（存在する場合のみ）。失敗はログに書いて続行。"""
    try:
        with os.scandir(dirpath) as it:
            for entry in it:
                if entry.is_file(follow_symlinks=False) and entry.name in IGNORABLE_FILES:
                    try:
                        # 読み取り専用属性を解除してから削除
                        os.chmod(entry.path, stat.S_IWUSR | stat.S_IRUSR)
                        os.remove(entry.path)
                    except Exception as e:
                        save_error_log(entry.path, f"{type(e).__name__}: {e}")
    except Exception as e:
        save_error_log(dirpath, f"{type(e).__name__}: {e}")
