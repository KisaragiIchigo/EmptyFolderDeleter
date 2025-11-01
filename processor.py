import os
import stat # ★ chmod の権限付与に使うので import は残す
from typing import Iterable, List, Callable, Sequence
import utils


# ★ utils.py に移動した関数群を削除
# IGNORABLE_FILES
# _is_effectively_empty
# _effective_count
# _delete_known_garbage


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

    # ★ローカル関数 is_dir_empty_cached は削除

    for root in root_paths:
        if not os.path.isdir(root):
            continue
        # topdown=False で、深い階層から順に評価
        for dirpath, dirnames, filenames in os.walk(root, topdown=False):
            # ★ utils.is_dir_empty_cached を呼ぶように変更
            if utils.is_dir_empty_cached(dirpath, ignore_known_garbage, fast_rescan):
                found.append(dirpath)

    # 重複除去＆パスでソート
    return sorted(list(set(found)))

def delete_empty_folders(
    folders: List[str],
    progress_cb: Callable[[int, int, str], None] | None = None,
    remove_known_garbage_files: bool = True,
    ignore_known_garbage_for_empty: bool = True,
    max_pass: int = 3,
    fast_rescan: bool = False, # ★ fast_rescan 引数を追加
) -> int:
    """
    空フォルダを深い階層から削除。削除成功時に親フォルダも対象に加え、
    max_pass 回まで全体を再試行することでネストした空フォルダに対応する。
    - remove_known_garbage_files: 既知ゴミファイルを先に消してから判定/削除
    - ignore_known_garbage_for_empty: “実質空”判定で既知ゴミを無視
    - fast_rescan: 判定時にキャッシュを利用するか
    戻り値: 削除できた件数（合計）
    """
    if not folders:
        return 0

    # 処理対象をセットで管理 (重複除去と動的な追加のため)
    target_set = set(folders)
    deleted_total = 0
    
    # 進捗の母数は、最初に見つかったフォルダ数
    total_target_initial = len(target_set)
    # 実際に処理した（進捗にカウントした）フォルダのセット
    progress_counted_set = set()

    # max_pass 回、削除を試行
    for attempt in range(1, max_pass + 1):
        if not target_set:
            break # 対象がなくなれば終了

        deleted_in_pass = 0
        
        # 常に深い順で処理するために、毎回ソート
        current_targets_sorted = sorted(list(target_set), key=len, reverse=True)

        for folder in current_targets_sorted:
            
            # このフォルダを進捗としてカウントしたか？ (初回のみカウント)
            if folder not in progress_counted_set:
                 progress_counted_set.add(folder)
                 if progress_cb:
                    progress_val = min(len(progress_counted_set), total_target_initial)
                    basename = os.path.basename(folder) or folder
                    progress_cb(progress_val, total_target_initial, basename)

            try:
                if not os.path.isdir(folder):
                    # 既に無ければ（親が先に消えたなどで）リストから除外
                    target_set.discard(folder)
                    continue

                if remove_known_garbage_files:
                    utils._delete_known_garbage(folder) # ★ utils. 経由に変更

                # ★ _is_effectively_empty を utils.is_dir_empty_cached に変更
                # ★ fast_rescan を渡す
                if utils.is_dir_empty_cached(folder, ignore_known_garbage_for_empty, fast_rescan):
                    try:
                        # 既存の権限に書き込み・実行権限を追加
                        current_mode = os.stat(folder).st_mode
                        os.chmod(folder, current_mode | stat.S_IWUSR | stat.S_IXUSR | stat.S_IRUSR)
                    except Exception:
                        pass # 失敗しても rmdir は試行
                        
                    os.rmdir(folder) # フォルダ削除
                    
                    deleted_in_pass += 1
                    deleted_total += 1
                    target_set.discard(folder) # 削除成功
                    utils.cache_clear_under(folder) # 削除したのでキャッシュクリア

                    # --- ★重要：親フォルダを次のパスの処理対象に追加 ---
                    parent = os.path.dirname(folder)
                    if parent and parent != folder:
                        # 親を次のチェック対象に追加する
                        target_set.add(parent)

            except Exception as e:
                # 権限エラーなどで削除失敗した場合、target_set に残るので
                # 次のパスでリトライされる
                utils.save_error_log(folder, f"{type(e).__name__}: {e}")
        
        # このパスで何も削除できなかったら、もう空になるフォルダはない
        if deleted_in_pass == 0:
            break  

    # 最後に残った（エラーなどで削除できなかった）フォルダのキャッシュもクリア
    for f in target_set:
        utils.cache_clear_under(f)
        
    # 進捗を100%にする
    if progress_cb:
        progress_cb(total_target_initial, total_target_initial, "完了")
        
    return deleted_total
