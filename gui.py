import os
from typing import List

from PySide6.QtCore import Qt, QPoint, QEvent, QSize
from PySide6.QtGui import QIcon, QAction
from PySide6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QApplication,
    QListWidget, QListWidgetItem, QDialog, QProgressBar, QMessageBox, QTextBrowser,
    QSpacerItem, QSizePolicy, QCheckBox, QFileDialog
)

import processor
import utils

#  スタイル定数 
PRIMARY = "#4169e1"
ACCENT  = "#7000e0"
BG_GLASS = "rgba(5,5,51,200)"
BORDER  = "3px solid rgba(65,105,255,255)"

RADIUS_WINDOW = 18
RADIUS_CARD   = 16
RADIUS_PANEL  = 10
RADIUS_BTN    = 8
GAP           = 10
RESIZE_MARGIN = 8

TITLE = "空フォルダ削除ツール ©️2025 KisaragiIchigo"

def build_qss(compact: bool = False) -> str:
    grad = (
        "qlineargradient(x1:0, y1:0, x2:0, y2:1, "
        "stop:0 rgba(255,255,255,40), stop:0.5 rgba(200,220,255,20), stop:1 rgba(255,255,255,6))"
    )
    glass_bg_image = "none" if compact else grad
    return f"""
    QWidget#bgRoot {{ background-color: rgba(0,0,0,0); border-radius:{RADIUS_WINDOW}px; }}
    QWidget#glassRoot {{
        background-color:{BG_GLASS}; border:{BORDER}; border-radius:{RADIUS_CARD}px;
        background-image:{glass_bg_image}; background-repeat:no-repeat; background-position:0 0;
    }}
    QLabel#titleLabel {{ color:#fff; font-weight:bold; }}
    QLabel#dropArea {{
        border: 2px dashed {PRIMARY}; border-radius:12px;
        color:#b8dcff; background: rgba(25,25,112,0.45); font-weight:bold;
    }}
    QPushButton {{
        background:{PRIMARY}; color:white; border:none; border-radius:{RADIUS_BTN}px; padding:6px 10px;
    }}
    QPushButton:hover {{ background:{ACCENT}; }}
    QWidget.DarkPanel {{
        background:#2f2f2f; border-radius:{RADIUS_PANEL}px; border:1px solid #000; padding:8px;
    }}
    QListWidget {{ background:#ffe4e1; color:#191970; border:1px solid #777; }}
    QProgressBar {{ border:1px solid #555; border-radius:6px; background:#333; color:white; text-align:center; }}
    QProgressBar::chunk {{ background:{PRIMARY}; border-radius:6px; }}
    QTextBrowser#readmeView {{ color:#ffe4e1; background:#333; border-radius:{RADIUS_PANEL}px; padding:8px; }}
    QCheckBox {{ color:#fff; }}
    """

#  共通：フレームレス移動＆端リサイズのベース 
class FramelessCard(QWidget):
    def __init__(self, title: str):
        super().__init__()
        self.setWindowTitle(title)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(820, 560)
        self.setMinimumSize(QSize(660, 440))

        outer = QVBoxLayout(self); outer.setContentsMargins(0, 0, 0, 0)
        self.bgRoot = QWidget(); self.bgRoot.setObjectName("bgRoot")
        outer.addWidget(self.bgRoot)

        bgLay = QVBoxLayout(self.bgRoot)
        bgLay.setContentsMargins(GAP, GAP, GAP, GAP)
        bgLay.setSpacing(GAP)

        self.card = QWidget(); self.card.setObjectName("glassRoot")
        bgLay.addWidget(self.card)

        self.cardLay = QVBoxLayout(self.card)
        self.cardLay.setContentsMargins(14, 14, 14, 14)
        self.cardLay.setSpacing(GAP)

        # タイトルバー
        bar = QHBoxLayout()
        self.titleLabel = QLabel(title); self.titleLabel.setObjectName("titleLabel")
        bar.addWidget(self.titleLabel)
        bar.addStretch(1)

        self.btnMin = QPushButton("🗕"); self.btnMin.setFixedSize(28, 28); self.btnMin.setToolTip("最小化")
        self.btnMax = QPushButton("🗖"); self.btnMax.setFixedSize(28, 28); self.btnMax.setToolTip("最大化/復元")
        self.btnClose = QPushButton("ｘ"); self.btnClose.setFixedSize(28, 28); self.btnClose.setToolTip("閉じる")
        bar.addWidget(self.btnMin); bar.addWidget(self.btnMax); bar.addWidget(self.btnClose)
        self.cardLay.addLayout(bar)

        self.btnClose.clicked.connect(self.close)
        self.btnMin.clicked.connect(self.showMinimized)
        self.btnMax.clicked.connect(self._toggle_max)

        self._moving = False
        self._resizing = False
        self._drag_offset = QPoint()

        self.bgRoot.setMouseTracking(True)
        self.bgRoot.installEventFilter(self)

        self.setStyleSheet(build_qss(False))

    def _toggle_max(self):
        if self.isMaximized():
            self.showNormal()
            self.setStyleSheet(build_qss(False))
            self.btnMax.setText("🗖")
        else:
            self.showMaximized()
            self.setStyleSheet(build_qss(True))
            self.btnMax.setText("❏")

    def eventFilter(self, obj, e):
        if obj is self.bgRoot:
            if e.type() == QEvent.MouseButtonPress and e.button() == Qt.LeftButton:
                pos = self.mapFromGlobal(e.globalPosition().toPoint())
                if self._edge_at(pos):
                    self._resizing = True
                    self._resize_edges = self._edge_at(pos)
                    self._start_geo = self.geometry()
                    self._start_mouse = e.globalPosition().toPoint()
                else:
                    self._moving = True
                    self._drag_offset = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
                return True
            elif e.type() == QEvent.MouseMove:
                if self._resizing:
                    self._resize_to(e.globalPosition().toPoint()); return True
                if self._moving and (e.buttons() & Qt.LeftButton) and not self.isMaximized():
                    self.move(e.globalPosition().toPoint() - self._drag_offset); return True
                self._update_cursor(self._edge_at(self.mapFromGlobal(e.globalPosition().toPoint())))
            elif e.type() == QEvent.MouseButtonRelease:
                self._resizing = False; self._moving = False; return True
        return super().eventFilter(obj, e)

    def _edge_at(self, pos):
        m = RESIZE_MARGIN; r = self.bgRoot.rect(); edges = ""
        if pos.y() <= m: edges += "T"
        if pos.y() >= r.height()-m: edges += "B"
        if pos.x() <= m: edges += "L"
        if pos.x() >= r.width()-m: edges += "R"
        return edges

    def _update_cursor(self, edges):
        if edges in ("TL", "BR"): self.setCursor(Qt.SizeFDiagCursor)
        elif edges in ("TR", "BL"): self.setCursor(Qt.SizeBDiagCursor)
        elif edges in ("L", "R"): self.setCursor(Qt.SizeHorCursor)
        elif edges in ("T", "B"): self.setCursor(Qt.SizeVerCursor)
        else: self.setCursor(Qt.ArrowCursor)

    def _resize_to(self, gpos):
        dx = gpos.x() - self._start_mouse.x()
        dy = gpos.y() - self._start_mouse.y()
        geo = self._start_geo
        x, y, w, h = geo.x(), geo.y(), geo.width(), geo.height()
        minw, minh = self.minimumSize().width(), self.minimumSize().height()
        edges = self._resize_edges

        if "L" in edges:
            new_w = max(minw, w - dx); x += (w - new_w); w = new_w
        if "R" in edges:
            w = max(minw, w + dx)
        if "T" in edges:
            new_h = max(minh, h - dy); y += (h - new_h); h = new_h
        if "B" in edges:
            h = max(minh, h + dy)
        self.setGeometry(x, y, w, h)

#  D&Dラベル 
class DropArea(QLabel):
    def __init__(self):
        super().__init__("ここにフォルダをドラッグ＆ドロップ")
        self.setObjectName("dropArea")
        self.setAlignment(Qt.AlignCenter)
        self.setAcceptDrops(True)
        self.setMinimumHeight(120)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        files = [u.toLocalFile() for u in e.mimeData().urls()]
        self.parent().on_drop(files)  # MainWindowに通知

#  README 
README_MD = r"""
# 空フォルダ削除ツール ©️2025 KisaragiIchigo

## 概要
指定フォルダ配下の「空フォルダ」を検索し、選択して一括削除できます。

## 追加の安全・高速化オプション
- **Thumbs.db / desktop.ini / .DS_Store** を無視して“実質空”として判定  
- 上記ゴミファイルを先に削除してからフォルダ削除  
- **高速リスキャン**：同一セッション内で再検索が速くなります（同じフォルダを続けて解析する時に有効）

## 使い方
1. メインの枠内に対象フォルダをD&D（または［フォルダを選択して解析］）  
2. 検出結果ダイアログで削除したい項目を選択（既定：全選択）  
3. **「選択したフォルダを削除」** を押す

## 注意
- 削除は元に戻せません。必要に応じてバックアップを作成してください。  
- 削除に失敗した項目は、同フォルダにエラーログ（txt）が出力されます。  
"""

class ReadmeDialog(FramelessCard):
    def __init__(self, parent=None):
        super().__init__("README ©️2025 KisaragiIchigo")
        self.setParent(parent, Qt.Dialog)
        panel = QWidget(); panel.setProperty("class", "DarkPanel")
        v = QVBoxLayout(panel); v.setContentsMargins(8, 8, 8, 8); v.setSpacing(8)

        viewer = QTextBrowser(); viewer.setObjectName("readmeView")
        viewer.setOpenExternalLinks(True); viewer.setReadOnly(True)
        viewer.setMarkdown(README_MD); v.addWidget(viewer, 1)

        row = QHBoxLayout()
        row.addStretch(1)
        btn = QPushButton("閉じる"); btn.clicked.connect(self.close)
        row.addWidget(btn)
        v.addLayout(row)

        self.cardLay.addWidget(panel, 1)
        self.resize(700, 520)

#  削除確認ダイアログ 
class ConfirmDialog(FramelessCard):
    def __init__(self, folders: List[str], parent=None):
        super().__init__("削除するフォルダの確認 ©️2025 KisaragiIchigo")
        self.setParent(parent, Qt.Dialog)
        self.folders = folders

        panel = QWidget(); panel.setProperty("class", "DarkPanel")
        lay = QVBoxLayout(panel); lay.setContentsMargins(8,8,8,8); lay.setSpacing(8)

        self.listw = QListWidget()
        for p in folders:
            it = QListWidgetItem(p)
            it.setSelected(True)  # 既定で全選択
            self.listw.addItem(it)
        lay.addWidget(self.listw, 1)

        self.countLabel = QLabel(f"選択中: {len(folders)} 個")
        self.listw.itemSelectionChanged.connect(self._on_sel_changed)
        lay.addWidget(self.countLabel)

        btn_row = QHBoxLayout()
        self.btnDelete = QPushButton("選択したフォルダを削除")
        self.btnCancel = QPushButton("キャンセル")
        btn_row.addStretch(1)
        btn_row.addWidget(self.btnDelete)
        btn_row.addWidget(self.btnCancel)
        lay.addLayout(btn_row)

        self.cardLay.addWidget(panel, 1)
        self.resize(720, 520)

    def _on_sel_changed(self):
        self.countLabel.setText(f"選択中: {len(self.selected_paths())} 個")

    def selected_paths(self) -> List[str]:
        return [i.text() for i in self.listw.selectedItems()]

#  メインウィンドウ 
class MainWindow(FramelessCard):
    def __init__(self):
        super().__init__(TITLE)

        # アイコン（任意）
        icon_path = utils.resource_path("karafo.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # メインUI
        drop_panel = QWidget(); drop_panel.setProperty("class", "DarkPanel")
        v = QVBoxLayout(drop_panel); v.setContentsMargins(10,10,10,10); v.setSpacing(GAP)

        self.dropArea = DropArea(); v.addWidget(self.dropArea)
        hint = QLabel("※ 複数フォルダOK / ネットワークドライブ可")
        hint.setStyleSheet("color:#e0ffff;")
        v.addWidget(hint)

        # オプション
        opt_row = QHBoxLayout()
        self.cb_remove_garbage = QCheckBox("Thumbs/desktop.ini なども削除")
        self.cb_remove_garbage.setChecked(True)
        self.cb_fast_rescan = QCheckBox("高速リスキャン")
        self.cb_fast_rescan.setChecked(True)
        opt_row.addWidget(self.cb_remove_garbage)
        opt_row.addStretch(1)
        opt_row.addWidget(self.cb_fast_rescan)
        v.addLayout(opt_row)

        # 操作ボタン行
        row = QHBoxLayout()
        self.btnReadme = QPushButton("README")
        self.btnOpen = QPushButton("フォルダを選択して解析")
        row.addWidget(self.btnReadme); row.addStretch(1); row.addWidget(self.btnOpen)
        v.addLayout(row)

        # 進捗
        self.progress = QProgressBar()
        v.addWidget(self.progress)

        self.cardLay.addWidget(drop_panel, 1)

        # 動作
        self.btnReadme.clicked.connect(self._show_readme)
        self.btnOpen.clicked.connect(self._select_and_process)

        # メニュー
        self.setContextMenuPolicy(Qt.ActionsContextMenu)
        act = QAction("READMEを開く", self); act.triggered.connect(self._show_readme)
        self.addAction(act)


    def on_drop(self, paths: List[str]):
        dirs = [p for p in paths if os.path.isdir(p)]
        if not dirs:
            QMessageBox.warning(self, "エラー", "フォルダをドロップしてね。")
            return
        self._process(dirs)

    # --- 手動選択 ---
    def _select_and_process(self):
        path = QFileDialog.getExistingDirectory(self, "フォルダを選択", os.getcwd(),
                                                QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks)
        if not path:
            return
        self._process([path])

    # --- 共通：解析～確認～削除 ---
    def _process(self, dirs: List[str]):
        self.progress.setValue(0)
        QApplication.processEvents()

        empty = processor.find_empty_folders(
            dirs,
            ignore_known_garbage=True,                    # “実質空”判定（Thumbs等は無視）
            fast_rescan=self.cb_fast_rescan.isChecked(),  # 高速リスキャン
        )
        if not empty:
            QMessageBox.information(self, "結果", "空フォルダは見つかりませんでした。")
            return

        dlg = ConfirmDialog(empty, self)
        dlg.btnCancel.clicked.connect(dlg.close)
        dlg.btnDelete.clicked.connect(lambda: self._delete_selected(dlg))
        dlg.show()

    def _delete_selected(self, dlg: ConfirmDialog):
        targets = dlg.selected_paths()
        if not targets:
            QMessageBox.information(self, "情報", "削除対象が選択されていません。")
            return

        # 進捗更新関数
        def update_progress(curr: int, total: int, name: str):
            self.progress.setMaximum(total)
            self.progress.setValue(curr)
            self.titleLabel.setText(f"{TITLE}  削除中: {name} ({curr}/{total})")
            QApplication.processEvents()

        removed = processor.delete_empty_folders(
            targets,
            progress_cb=update_progress,
            remove_known_garbage_files=self.cb_remove_garbage.isChecked(),
            ignore_known_garbage_for_empty=True,
            max_pass=3, 
        )
        self.titleLabel.setText(TITLE)
        self.progress.setValue(0)
        dlg.close()

        QMessageBox.information(self, "完了", f"{removed} 個の空フォルダを削除しました。")
        # 削除後はキャッシュを掃除
        for t in targets:
            utils.cache_clear_under(t)

    def _show_readme(self):
        r = ReadmeDialog(self)
        r.show()
