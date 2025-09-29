import os
import stat
from typing import Iterable, List, Callable, Sequence
import utils


IGNORABLE_FILES: Sequence[str] = ("Thumbs.db", "desktop.ini", ".DS_Store")

def _is_effectively_empty(dirpath: str, ignore_known_garbage: bool) -> bool:
    """フォルダが“実質空”か判定（ignore_known_garbage=True の場合は既知ゴミを無視）"""
    try:
        with os.scandir(dirpath) as it:
            for entry in it:
                if entry.is_dir(follow_symlinks=False):
                    return False
                if ignore_known_garbage and entry.name in IGNORABLE_FILES:
                    continue
                return False
        return True
    except Exception as e:
        utils.save_error_log(dirpath, f"{type(e).__name__}: {e}")
        return False

def _effective_count(dirpath: str, ignore_known_garbage: bool) -> int:
    """“実質空”評価での要素数（0なら空扱い）"""
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
                    return count
        return 0
    except Exception as e:
        utils.save_error_log(dirpath, f"{type(e).__name__}: {e}")
        return 1  # 不明なら空ではない扱い

def _delete_known_garbage(dirpath: str) -> None:
    """既知ゴミファイルを削除（存在する場合のみ）。失敗はログに書いて続行。"""
    try:
        with os.scandir(dirpath) as it:
            for entry in it:
                if entry.is_file(follow_symlinks=False) and entry.name in IGNORABLE_FILES:
                    try:
                        os.chmod(entry.path, stat.S_IWUSR | stat.S_IRUSR)
                        os.remove(entry.path)
                    except Exception as e:
                        utils.save_error_log(entry.path, f"{type(e).__name__}: {e}")
    except Exception as e:
        utils.save_error_log(dirpath, f"{type(e).__name__}: {e}")

def find_empty_folders(
    root_paths: Iterable[str],
    ignore_known_garbage: bool = True,
    fast_rescan: bool = False,
) -> List[str]:
    """
    渡された複数ルート配下の“空フォルダ”を再帰列挙（重複除去/ソート済み）。
    - ignore_known_garbage: 既知ゴミファイル(Thumbs等)は無視して空扱い。
    - fast_rescan: 同一セッション内の再検索で、mtimeと“実質要素数”キャッシュを使って高速化。
    """
    found = []

    def is_dir_empty_cached(p: str) -> bool:
        if not fast_rescan:
            return _effective_count(p, ignore_known_garbage) == 0
        try:
            st = os.stat(p)
        except FileNotFoundError:
            return False
        cached = utils.cache_get(p)
        if cached and cached[0] == st.st_mtime:
            # 変更なし→キャッシュ値で判定
            return cached[1] == 0
        # 再計測してキャッシュ更新
        cnt = _effective_count(p, ignore_known_garbage)
        utils.cache_set(p, st.st_mtime, cnt)
        return cnt == 0

    for root in root_paths:
        if not os.path.isdir(root):
            continue
        for dirpath, dirnames, filenames in os.walk(root, topdown=False):
            if is_dir_empty_cached(dirpath):
                found.append(dirpath)

    # 重複除去＆パスでソート
    return sorted(list(set(found)))

def delete_empty_folders(
    folders: List[str],
    progress_cb: Callable[[int, int, str], None] | None = None,
    remove_known_garbage_files: bool = True,
    ignore_known_garbage_for_empty: bool = True,
    max_pass: int = 3,
) -> int:
    """
    空フォルダを深い階層から削除。安定化のため最大 max_pass 回まで全体を再試行。
    - remove_known_garbage_files: 既知ゴミファイルを先に消してから判定/削除
    - ignore_known_garbage_for_empty: “実質空”判定で既知ゴミを無視
    戻り値: 削除できた件数（合計）
    """
    if not folders:
        return 0

    # 常に深い順で処理
    folders = sorted(list(set(folders)), key=len, reverse=True)
    total_target = len(folders)
    deleted_total = 0
    curr = 0

    for attempt in range(1, max_pass + 1):
        deleted_in_pass = 0

        for folder in list(folders):  # 動的に縮めるのでコピーを回す
            curr += 1
            basename = os.path.basename(folder) or folder

            try:
                if not os.path.isdir(folder):
                    # 既に無ければ成功扱いでリストから除外
                    deleted_in_pass += 1
                    folders.remove(folder)
                    continue

                if remove_known_garbage_files:
                    _delete_known_garbage(folder)

                # “実質空”なら削除
                if _is_effectively_empty(folder, ignore_known_garbage_for_empty):
                    try:
                        os.chmod(folder, stat.S_IWUSR | stat.S_IXUSR | stat.S_IRUSR)
                    except Exception:
                        pass
                    os.rmdir(folder)
                    deleted_in_pass += 1
                    folders.remove(folder)

            except Exception as e:
                utils.save_error_log(folder, f"{type(e).__name__}: {e}")

            finally:
                if progress_cb:
                    progress_cb(min(curr, total_target), total_target, basename)

        deleted_total += deleted_in_pass
        if deleted_in_pass == 0:
            break  
    for f in folders:
        utils.cache_clear_under(f)
    return deleted_total
