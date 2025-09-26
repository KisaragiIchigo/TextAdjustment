import os, re, difflib, html
from pathlib import Path
from PySide6.QtCore import Qt, QEvent, QPoint, QRect, QEasingCurve, QPropertyAnimation
from PySide6.QtGui import QIcon, QColor, QFont, QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit, QFileDialog,
    QMessageBox, QDialog, QLabel, QGraphicsDropShadowEffect, QTextBrowser,
    QCheckBox, QGroupBox, QFormLayout, QComboBox, QSplitter, QProgressDialog
)
from processor import (
    process_text, process_directory, DEFAULT_TEXT_EXTS, enumerate_target_files
)
from utils import resource_path, is_text_like
from config import load_config, save_config

# ====== スタイル定数 ======
PRIMARY_COLOR    = "#4169e1"; HOVER_COLOR = "#7000e0"
TITLE_COLOR      = "#FFFFFF"; TEXT_COLOR  = "#FFFFFF"  
WINDOW_BG        = "rgba(255,255,255,0)"
GLASSROOT_BG     = "rgba(5,5,51,200)"
GLASSROOT_BORDER = "3px solid rgba(65,105,255,255)"

TEXTPANEL_BG     = "#ffffff"
RADIUS_WINDOW    = 18; RADIUS_CARD = 16; RADIUS_PANEL = 10; RADIUS_BUTTON = 8
PADDING_CARD     = 16; GAP_DEFAULT = 10; RESIZE_MARGIN = 8
MENU_WIDTH       = 300
UI_FONT_FAMILY   = "メイリオ"
MAX_HISTORY      = 10  # 各入力欄の履歴件数

def _build_qss(compact: bool = False) -> str:
    glass = "none" if compact else (
        "qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 rgba(255,255,255,50),"
        "stop:0.5 rgba(200,220,255,25),stop:1 rgba(255,255,255,8))"
    )
    return f"""
    QWidget#bgRoot {{ background-color:{WINDOW_BG}; border-radius:{RADIUS_WINDOW}px; }}
    QWidget#glassRoot {{
        background-color:{GLASSROOT_BG}; border:{GLASSROOT_BORDER};
        border-radius:{RADIUS_CARD}px; background-image:{glass}; background-repeat:no-repeat;
    }}
    QLabel#titleLabel {{ color:{TITLE_COLOR}; font-weight:bold; }}
    QTextEdit#textPanel {{
        background-color:{TEXTPANEL_BG}; border-radius:{RADIUS_PANEL}px;
        border:1px solid rgba(0,0,0,120); color:#000000;
    }}
    QTextBrowser#readmeText {{
        color:#ffe4e1; background:#333; border-radius:{RADIUS_PANEL}px; padding:8px;
    }}
    QGroupBox {{
        border:1px solid rgba(255,255,255,80); border-radius:{RADIUS_PANEL}px;
        margin-top:8px; padding:8px; color:{TEXT_COLOR};
    }}
    QGroupBox::title {{ subcontrol-origin: margin; left:10px; padding:0 4px; }}
    QLabel {{ color:{TEXT_COLOR}; }}
    QLineEdit, QComboBox {{ background:#fff; color:#000; border-radius:6px; padding:4px 6px; }}
    QCheckBox {{ color:{TEXT_COLOR}; }}
    QPushButton {{
        background-color:{PRIMARY_COLOR}; color:#fff; border:none;
        padding:6px 12px; border-radius:{RADIUS_BUTTON}px;
    }}
    QPushButton:hover {{ background-color:{HOVER_COLOR}; }}

    QWidget#menuPanel {{
        background:{GLASSROOT_BG}; border-left:{GLASSROOT_BORDER};
        border-top-right-radius:{RADIUS_CARD}px; border-bottom-right-radius:{RADIUS_CARD}px;
        background-image:{glass};
    }}
    QWidget#overlay {{ background: rgba(0,0,0,120); }}
    QLabel#menuTitle {{ color:{TITLE_COLOR}; font-weight:bold; }}
    """

def apply_drop_shadow(w: QWidget) -> QGraphicsDropShadowEffect:
    eff = QGraphicsDropShadowEffect(w)
    eff.setBlurRadius(28); eff.setOffset(0, 3)
    c = QColor(0,0,0); c.setAlphaF(0.18); eff.setColor(c)
    w.setGraphicsEffect(eff); return eff

# ===== README =====
README_MD = r"""
# TextAdjustment ©️2025 KisaragiIchigo

テキストを「読みやすく」「まとめて」整形するためのツールです。  
ドラッグ＆ドロップ対応、差分プレビュー、再帰バッチ処理、半角/全角変換などを備えています。

---

## クイックスタート

1. **ファイルをウィンドウへドラッグ＆ドロップ**（または「開く」）。  
   左に元テキスト、右に変換結果が表示されます。差分は **水色（#ccffff）** で強調されます。
2. 必要な設定を行い、**「Reプレビュー」** を押して結果を更新します。  
   左右のスクロールは自動で同期されます。**等幅フォント**をONにすると桁位置が揃って見やすくなります。
3. 仕上がりを確認したら **「保存」**。拡張子を未入力の場合、**元ファイルの拡張子**が自動付与されます。

> プレビュー下のボタン：**「Reプレビュー」「開く」「保存」**

---

## 主な機能

### 改行の制御
- **改行トークン**（`,`区切り）：ここに指定した語やパターンで改行します。  
  例）`。`, `！`, `?`, `END`, `\d{4}-\d{2}-\d{2}` など
- **改行の位置**：  
  「**直後に改行**」「**直前に改行**」「**前後に改行**」から選択。
- **除外トークン**（`,`区切り・リテラル）：一致箇所には改行を入れません。
- **行スキップ（正規表現）**：一致した行は処理対象から除外します。
- **正規表現として扱う**：改行トークンを正規表現解釈に切り替え可能（設定メニュー）。

### 文字幅（半角/全角）変換
- **モード**：`変更なし / 半角へ / 全角へ`
- **対象の指定**：  
  - 任意の**対象文字列**欄に含めた文字のみ  
  - または **英語 / カタカナ / 数字 / 記号 / スペース** のチェックで一括指定

### 行頭/行末の付加
- 各行の**先頭**または**末尾**に任意の文字列を追加できます。

### 履歴（最大10件）
- 改行トークン・除外トークン・行スキップ正規表現・対象文字列・行頭/行末付加・対象拡張子は、**最新10件を自動保存**。  
  重複入力は先頭に繰り上がり、11件目以降は古いものから自動で削除されます。

### 差分プレビュー
- **左右分割**で元/結果を表示。差分は **#ccffff** で強調。  
- **左右スクロール同期**（比率連動）により、同じ付近を並べて確認できます。  
- **等幅フォント**トグルで桁ズレを可視化しやすくできます。  
- プレビュー背景は白、文字は黒で視認性を重視しています。

---

## フォルダの一括処理（バッチ）

- 画面上部の **「入力フォルダ」** と **「出力フォルダ」** を指定し、**「一括実行」**。  
  または、**フォルダをそのままドラッグ＆ドロップ**しても実行できます。
- **再帰** をONにすると、サブフォルダも含めて処理します（**フォルダ階層は維持**して出力）。
- 実行中は **進捗バー** が表示され、**キャンセル**が可能です。

---

## 読み込み/保存とエンコーディング

- **単発読み込み時**は、設定の **エンコーディング自動判定（chardet）** を利用可能です。  
  失敗した場合はUTF-8で読み込みます。
- **保存**はUTF-8で出力します。  
- **拡張子未入力で保存**した場合、読み込んだ元ファイルの拡張子を**自動付与**します（例：`.txt`）。

---

## 設定メニュー（≡）

- **改行トークンを正規表現として扱う**（ON/OFF）  
- **再帰（サブフォルダも処理）**（ON/OFF）  
- **エンコーディング自動判定**（ON/OFF、単発読み込み時）  
- **対象拡張子**：`.txt,.md,.csv` のように`,`区切りで指定

---

## トラブルシューティング

- **文字化けする**：設定メニューの **エンコーディング自動判定** をONにして再読み込みしてください。  
- **想定外の位置で改行される**：  
  1) 改行トークンの **正規表現ON/OFF** を切り替えて確認  
  2) **除外トークン** によって抑止されていないか確認  
  3) **行スキップ**の正規表現にマッチしていないか確認
- **差分が見づらい**：**等幅フォント**をONにし、スクロール同期で位置を合わせて確認してください。

---

## 補足

- プレビュー下の操作は **「Reプレビュー」→「開く」→「保存」** の順で配置されています。  
- ウィンドウはフレームレスですが、ドラッグで移動・端ドラッグでリサイズ可能です。  
- 本ツールのUIは **メイリオ** フォントを使用しています。

"""


class ReadmeDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("README ©️2025 KisaragiIchigo")
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMinimumSize(850, 600)
        outer = QVBoxLayout(self); outer.setContentsMargins(0,0,0,0)
        bg = QWidget(); bg.setObjectName("bgRoot"); outer.addWidget(bg)
        bgLay = QVBoxLayout(bg); bgLay.setContentsMargins(GAP_DEFAULT, GAP_DEFAULT, GAP_DEFAULT, GAP_DEFAULT)
        card = QWidget(); card.setObjectName("glassRoot"); bgLay.addWidget(card); apply_drop_shadow(card)
        lay = QVBoxLayout(card); lay.setContentsMargins(PADDING_CARD, PADDING_CARD, PADDING_CARD, PADDING_CARD)
        title = QLabel("README"); title.setObjectName("titleLabel"); lay.addWidget(title)
        view = QTextBrowser(); view.setObjectName("readmeText"); view.setOpenExternalLinks(True)
        view.setMarkdown(README_MD); lay.addWidget(view, 1)
        row = QHBoxLayout(); close_btn = QPushButton("閉じる"); close_btn.clicked.connect(self.accept)
        row.addStretch(1); row.addWidget(close_btn); lay.addLayout(row)
        self.setStyleSheet(_build_qss(False))

# ===== 差分ハイライト =====
def _html_line(s: str) -> str:
    """空行も高さが出るように &nbsp; として埋め、HTMLエスケープも行う"""
    if s == "":
        return "&nbsp;"
    return html.escape(s)

def render_diff_html(src_text: str, dst_text: str) -> tuple[str, str]:
    src_lines = src_text.splitlines()
    dst_lines = dst_text.splitlines()
    sm = difflib.SequenceMatcher(a=src_lines, b=dst_lines)

    head = (
        "<html><head><meta charset='utf-8'><style>"
        "body{background:#ffffff;color:#000000;font-family:inherit;}"
        ".line{white-space:pre-wrap; min-height:1.2em;}"  # 空行可視化
        ".eq{} .chg{background:#ccffff;} .del{background:#ccffff;} .ins{background:#ccffff;}"
        "</style></head><body>"
    )
    left_html  = [head]
    right_html = [head]

    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for ln in src_lines[i1:i2]:
                left_html.append(f"<div class='line eq'>{_html_line(ln)}</div>")
            for ln in dst_lines[j1:j2]:
                right_html.append(f"<div class='line eq'>{_html_line(ln)}</div>")
        elif tag == "delete":
            for ln in src_lines[i1:i2]:
                left_html.append(f"<div class='line del'>{_html_line(ln)}</div>")
        elif tag == "insert":
            for ln in dst_lines[j1:j2]:
                right_html.append(f"<div class='line ins'>{_html_line(ln)}</div>")
        elif tag == "replace":
            for ln in src_lines[i1:i2]:
                left_html.append(f"<div class='line chg'>{_html_line(ln)}</div>")
            for ln in dst_lines[j1:j2]:
                right_html.append(f"<div class='line chg'>{_html_line(ln)}</div>")

    left_html.append("</body></html>")
    right_html.append("</body></html>")
    return "".join(left_html), "".join(right_html)

# ===== 履歴ヘルパ =====
def _new_history_combo(placeholder: str) -> QComboBox:
    cb = QComboBox()
    cb.setEditable(True)
    cb.lineEdit().setPlaceholderText(placeholder)
    return cb

def _push_history_list(lst, text: str) -> list:
    """履歴に text を前詰めで追加（重複は先頭へ移動）。最大 MAX_HISTORY 件。"""
    t = (text or "").strip()
    if not t:
        return lst or []
    lst = list(lst or [])
    if t in lst:
        lst.remove(t)
    lst.insert(0, t)
    return lst[:MAX_HISTORY]

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TextAdjustment ©️2025 KisaragiIchigo")
        self.resize(1100, 800); self.setMinimumSize(900, 620)
        self.setWindowFlags(Qt.FramelessWindowHint); self.setAttribute(Qt.WA_TranslucentBackground)

        ico = resource_path(os.path.join("assets","TextAdjustment.ico"))
        if os.path.exists(ico): self.setWindowIcon(QIcon(ico))

        outer = QVBoxLayout(self); outer.setContentsMargins(0,0,0,0)
        self.bg = QWidget(); self.bg.setObjectName("bgRoot"); outer.addWidget(self.bg)
        bgLay = QVBoxLayout(self.bg); bgLay.setContentsMargins(GAP_DEFAULT,GAP_DEFAULT,GAP_DEFAULT,GAP_DEFAULT)
        self.card = QWidget(); self.card.setObjectName("glassRoot"); bgLay.addWidget(self.card)
        self.shadow = apply_drop_shadow(self.card)

        main = QVBoxLayout(self.card)
        main.setContentsMargins(PADDING_CARD,PADDING_CARD,PADDING_CARD,PADDING_CARD)
        main.setSpacing(GAP_DEFAULT)

        # 内部保持
        self._src_plain = ""
        self._src_path: Path | None = None  # ★元ファイルパス（拡張子推定用）
        self._syncing_vert = False
        self._syncing_horz = False

        # ===== タイトルバー =====
        bar = QHBoxLayout()
        self.btn_menu = QPushButton("≡"); self.btn_menu.setFixedWidth(36); self.btn_menu.setToolTip("設定")
        ttl = QLabel("TextAdjustment"); ttl.setObjectName("titleLabel")
        bar.addWidget(self.btn_menu); bar.addWidget(ttl); bar.addStretch(1)
        self.btn_batch_in = QPushButton("入力フォルダ")
        self.btn_batch_out = QPushButton("出力フォルダ")
        self.btn_batch_run = QPushButton("一括実行")
        self.btn_readme = QPushButton("README")
        self.btn_close = QPushButton("×"); self.btn_close.setFixedWidth(36)
        for b in (self.btn_batch_in,self.btn_batch_out,self.btn_batch_run,self.btn_readme,self.btn_close):
            bar.addWidget(b)
        main.addLayout(bar)

        # ===== オプション（整形系） =====
        opt = QGroupBox("整形オプション"); f = QFormLayout(); f.setSpacing(6)
        self.cb_remove_blanks = QCheckBox("空白行を削除"); self.cb_remove_blanks.setChecked(True)

        # 履歴コンボ（編集可）
        self.cmb_break_tokens  = _new_history_combo("改行トークン例: 。,！,?,END,\\d{4}-\\d{2}-\\d{2}")
        self.cmb_break_exclude = _new_history_combo("改行除外トークン（,区切り／リテラル）例: http://,https://")
        self.cmb_skip_regex    = _new_history_combo(r"処理しない行の正規表現（例）^#")
        self.cmb_break_mode = QComboBox(); self.cmb_break_mode.addItems(["直後に改行","直前に改行","前後に改行"])
        self.cmb_prefix = _new_history_combo("各行の先頭に付与（任意）")
        self.cmb_suffix = _new_history_combo("各行の末尾に付与（任意）")

        # 文字幅変換（モード + 対象指定）
        self.cmb_width = QComboBox(); self.cmb_width.addItems(["変更なし","半角へ","全角へ"])
        self.cmb_width_targets = _new_history_combo("対象文字列（任意。ここに含む文字だけ変換）")
        self.cb_w_eng   = QCheckBox("英語")
        self.cb_w_kata  = QCheckBox("カタカナ")
        self.cb_w_num   = QCheckBox("数字")
        self.cb_w_sym   = QCheckBox("記号")
        self.cb_w_space = QCheckBox("スペース")

        # 等幅フォントトグル（プレビュー）
        self.cb_preview_mono = QCheckBox("等幅フォント（プレビュー）")

        f.addRow(self.cb_remove_blanks)
        f.addRow(QLabel("改行トークン（,区切り・正規表現は設定でON）:"), self.cmb_break_tokens)
        f.addRow(QLabel("改行除外トークン（,区切り・リテラル）:"), self.cmb_break_exclude)
        f.addRow(QLabel("改行位置:"), self.cmb_break_mode)
        f.addRow(QLabel("行スキップ（正規表現）:"), self.cmb_skip_regex)
        f.addRow(QLabel("文字幅変換:"), self.cmb_width)
        f.addRow(QLabel("対象文字列:"), self.cmb_width_targets)
        cat_row = QHBoxLayout()
        for w in (self.cb_w_eng, self.cb_w_kata, self.cb_w_num, self.cb_w_sym, self.cb_w_space): cat_row.addWidget(w)
        cat_row.addStretch(1)
        holder = QWidget(); holder.setLayout(cat_row)
        f.addRow(QLabel("対象カテゴリ:"), holder)
        f.addRow(self.cb_preview_mono)
        f.addRow(QLabel("行頭に追加:"), self.cmb_prefix)
        f.addRow(QLabel("行末に追加:"), self.cmb_suffix)
        opt.setLayout(f)
        main.addWidget(opt)

        # ===== プレビュー（左右） =====
        split = QSplitter(Qt.Horizontal)
        self.src_view = QTextEdit(); self.src_view.setReadOnly(True); self.src_view.setObjectName("textPanel")
        self.dst_view = QTextEdit(); self.dst_view.setReadOnly(True); self.dst_view.setObjectName("textPanel")
        self.src_view.setFont(QFont(UI_FONT_FAMILY, 11)); self.dst_view.setFont(QFont(UI_FONT_FAMILY, 11))
        split.addWidget(self.src_view); split.addWidget(self.dst_view)
        split.setSizes([600, 600])
        main.addWidget(split, 1)

        # ===== プレビュー下のボタン（Reプレビュー/開く/保存） =====
        filebar = QHBoxLayout()
        self.btn_repreview = QPushButton("Reプレビュー")
        self.btn_open = QPushButton("開く")
        self.btn_save = QPushButton("保存")
        filebar.addStretch(1); filebar.addWidget(self.btn_repreview); filebar.addWidget(self.btn_open); filebar.addWidget(self.btn_save)
        main.addLayout(filebar)

        # ===== イベント =====
        self.btn_repreview.clicked.connect(self.repreview)
        self.btn_open.clicked.connect(self.open_file)
        self.btn_save.clicked.connect(self.save_file)
        self.btn_readme.clicked.connect(self.show_readme)
        self.btn_close.clicked.connect(self.close)
        self.btn_batch_in.clicked.connect(self.choose_batch_in)
        self.btn_batch_out.clicked.connect(self.choose_batch_out)
        self.btn_batch_run.clicked.connect(self.run_batch)

        # 入力確定で履歴に積む
        for cb in (self.cmb_break_tokens, self.cmb_break_exclude, self.cmb_skip_regex,
                   self.cmb_prefix, self.cmb_suffix, self.cmb_width_targets):
            cb.lineEdit().editingFinished.connect(self._remember_histories)

        # スクロール同期（縦・横）
        self.src_view.verticalScrollBar().valueChanged.connect(self._on_src_vert_scroll)
        self.dst_view.verticalScrollBar().valueChanged.connect(self._on_dst_vert_scroll)
        self.src_view.horizontalScrollBar().valueChanged.connect(self._on_src_horz_scroll)
        self.dst_view.horizontalScrollBar().valueChanged.connect(self._on_dst_horz_scroll)

        # フォントトグル
        self.cb_preview_mono.toggled.connect(self._apply_preview_font)

        self.setAcceptDrops(True)  # D&D

        # フレームレス移動/リサイズ
        self._moving = False; self._drag_offset = QPoint()
        self._resizing = False; self._resize_edges=""; self._start_geo=None; self._start_mouse=None
        self.bg.setMouseTracking(True); self.bg.installEventFilter(self)

        self.setStyleSheet(_build_qss(False))

        # 設定ロード＋メニュー初期化
        self.cfg = load_config()
        self._init_settings_menu()
        self._apply_config()

    # ====== 設定メニュー（ハンバーガー） ======
    def _init_settings_menu(self):
        self.overlay = QWidget(self); self.overlay.setObjectName("overlay")
        self.overlay.setGeometry(0,0,self.width(),self.height()); self.overlay.hide()
        self.overlay.mousePressEvent = lambda e: self._toggle_menu(False)

        self.menuPanel = QWidget(self); self.menuPanel.setObjectName("menuPanel")
        self.menuPanel.setGeometry(-MENU_WIDTH, 0, MENU_WIDTH, self.height())
        v = QVBoxLayout(self.menuPanel); v.setContentsMargins(12,12,12,12); v.setSpacing(10)
        title = QLabel("設定"); title.setObjectName("menuTitle"); v.addWidget(title)

        gb = QGroupBox("バッチ/読込設定"); ff = QFormLayout(); ff.setSpacing(6)
        self.cb_break_regex = QCheckBox("改行トークンを正規表現として扱う")
        self.cb_recursive = QCheckBox("再帰（サブフォルダも処理）")
        self.cb_detect_encoding = QCheckBox("エンコーディング自動判定（chardet・単発のみ）")
        self.cmb_exts = _new_history_combo(",".join(sorted(DEFAULT_TEXT_EXTS)))
        ff.addRow(self.cb_break_regex)
        ff.addRow(self.cb_recursive)
        ff.addRow(self.cb_detect_encoding)
        ff.addRow(QLabel("対象拡張子（.txt,.md,...）:"), self.cmb_exts)
        gb.setLayout(ff); v.addWidget(gb)

        btnrow = QHBoxLayout()
        btn_close = QPushButton("閉じる"); btn_close.clicked.connect(lambda: self._toggle_menu(False))
        btnrow.addStretch(1); btnrow.addWidget(btn_close)
        v.addLayout(btnrow); v.addStretch(1)

        self.menu_anim = QPropertyAnimation(self.menuPanel, b"geometry", self)
        self.menu_anim.setDuration(220); self.menu_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._menu_visible = False; self._next_menu_visible = False
        self.menu_anim.finished.connect(self._after_menu)
        self.btn_menu.clicked.connect(lambda: self._toggle_menu(True))

    def _after_menu(self):
        self._menu_visible = self._next_menu_visible
        if not self._menu_visible:
            self.menuPanel.hide(); self.overlay.hide()

    def _toggle_menu(self, show: bool | None = None):
        if show is None: show = not self._menu_visible
        h = self.height()
        self.menuPanel.setFixedHeight(h); self.overlay.setGeometry(0,0,self.width(),h)
        self.overlay.setVisible(True); self.overlay.raise_()
        self.menuPanel.setVisible(True); self.menuPanel.raise_()
        if show:
            start = QRect(-MENU_WIDTH, 0, MENU_WIDTH, h); end = QRect(0,0,MENU_WIDTH,h)
        else:
            start = QRect(self.menuPanel.geometry()); end = QRect(-MENU_WIDTH,0,MENU_WIDTH,h)
        self._next_menu_visible = show
        self.menu_anim.stop(); self.menu_anim.setStartValue(start); self.menu_anim.setEndValue(end); self.menu_anim.start()

    # ===== 設定適用/収集/保存 =====
    def _apply_config(self):
        c = self.cfg
        # メイン
        self.cb_remove_blanks.setChecked(c.get("remove_blanks", True))
        self._fill_history_combo(self.cmb_break_tokens,  c.get("hist_break_tokens", []),  c.get("break_tokens",""))
        self._fill_history_combo(self.cmb_break_exclude, c.get("hist_break_exclude", []), c.get("break_exclude",""))
        self._fill_history_combo(self.cmb_skip_regex,    c.get("hist_skip_regex", []),    c.get("skip_regex",""))
        self._fill_history_combo(self.cmb_prefix,        c.get("hist_prefix", []),        c.get("prefix",""))
        self._fill_history_combo(self.cmb_suffix,        c.get("hist_suffix", []),        c.get("suffix",""))
        self.cmb_break_mode.setCurrentIndex(c.get("break_mode", 0))

        self.cmb_width.setCurrentIndex(c.get("width_mode", 0))
        self._fill_history_combo(self.cmb_width_targets, c.get("hist_width_targets", []), c.get("width_targets",""))
        self.cb_w_eng.setChecked(c.get("w_eng", False))
        self.cb_w_kata.setChecked(c.get("w_kata", False))
        self.cb_w_num.setChecked(c.get("w_num", False))
        self.cb_w_sym.setChecked(c.get("w_sym", False))
        self.cb_w_space.setChecked(c.get("w_space", False))

        # 等幅フォント
        self.cb_preview_mono.setChecked(c.get("preview_mono", False))
        self._apply_preview_font(self.cb_preview_mono.isChecked())

        # メニュー
        self.cb_break_regex.setChecked(c.get("break_is_regex", False))
        self.cb_recursive.setChecked(c.get("recursive", True))
        self.cb_detect_encoding.setChecked(c.get("detect_encoding", True))
        self._fill_history_combo(self.cmb_exts, c.get("hist_exts", []), c.get("exts_csv", ",".join(sorted(DEFAULT_TEXT_EXTS))))

        # 位置
        geo = c.get("window_geo")
        if isinstance(geo, dict):
            try: self.setGeometry(geo["x"],geo["y"],geo["w"],geo["h"])
            except Exception: pass

    def _fill_history_combo(self, combo: QComboBox, items: list, current: str):
        combo.blockSignals(True)
        combo.clear()
        for it in items or []:
            combo.addItem(it)
        combo.setCurrentText(current or "")
        combo.blockSignals(False)

    def _collect_settings(self) -> dict:
        token_text   = self.cmb_break_tokens.currentText()
        exclude_text = self.cmb_break_exclude.currentText()
        skip_text    = self.cmb_skip_regex.currentText()
        prefix_text  = self.cmb_prefix.currentText()
        suffix_text  = self.cmb_suffix.currentText()
        mode_map = {0:"after",1:"before",2:"around"}
        ext_items = [s.strip() for s in self.cmb_exts.currentText().split(",") if s.strip()]
        exts = {e if e.startswith(".") else f".{e}" for e in ext_items} or set(DEFAULT_TEXT_EXTS)
        return {
            "remove_blanks": self.cb_remove_blanks.isChecked(),
            "break_tokens": [s.strip() for s in token_text.split(",") if s.strip()],
            "break_tokens_are_regex": self.cb_break_regex.isChecked(),
            "break_exclude_tokens": [s.strip() for s in exclude_text.split(",") if s.strip()],
            "break_mode": mode_map.get(self.cmb_break_mode.currentIndex(), "after"),
            "skip_regex": skip_text.strip(),
            "prefix": prefix_text,
            "suffix": suffix_text,
            "width_mode": {0:"none",1:"to_half",2:"to_full"}[self.cmb_width.currentIndex()],
            "width_targets": self.cmb_width_targets.currentText(),
            "width_sets": {
                "eng": self.cb_w_eng.isChecked(),
                "kata": self.cb_w_kata.isChecked(),
                "num": self.cb_w_num.isChecked(),
                "sym": self.cb_w_sym.isChecked(),
                "space": self.cb_w_space.isChecked(),
            },
            "recursive": self.cb_recursive.isChecked(),
            "detect_encoding": self.cb_detect_encoding.isChecked(),
            "exts": exts,
        }

    def _remember_histories(self):
        c = self.cfg
        c["hist_break_tokens"]  = _push_history_list(c.get("hist_break_tokens", []),  self.cmb_break_tokens.currentText())
        c["hist_break_exclude"] = _push_history_list(c.get("hist_break_exclude", []), self.cmb_break_exclude.currentText())
        c["hist_skip_regex"]    = _push_history_list(c.get("hist_skip_regex", []),    self.cmb_skip_regex.currentText())
        c["hist_prefix"]        = _push_history_list(c.get("hist_prefix", []),        self.cmb_prefix.currentText())
        c["hist_suffix"]        = _push_history_list(c.get("hist_suffix", []),        self.cmb_suffix.currentText())
        c["hist_width_targets"] = _push_history_list(c.get("hist_width_targets", []), self.cmb_width_targets.currentText())
        c["hist_exts"]          = _push_history_list(c.get("hist_exts", []),          self.cmb_exts.currentText())
        c["preview_mono"]       = self.cb_preview_mono.isChecked()
        save_config(c)

    def _save_runtime_config(self):
        self._remember_histories()
        s = self._collect_settings(); c = self.cfg
        c.update({
            "remove_blanks": s["remove_blanks"],
            "break_tokens": ",".join(s["break_tokens"]),
            "break_is_regex": s["break_tokens_are_regex"],
            "break_exclude": ",".join(s["break_exclude_tokens"]),
            "break_mode": {"after":0,"before":1,"around":2}[s["break_mode"]],
            "skip_regex": s["skip_regex"],
            "prefix": s["prefix"], "suffix": s["suffix"],
            "width_mode": {"none":0,"to_half":1,"to_full":2}[s["width_mode"]],
            "width_targets": s["width_targets"],
            "w_eng": s["width_sets"]["eng"],
            "w_kata": s["width_sets"]["kata"],
            "w_num": s["width_sets"]["num"],
            "w_sym": s["width_sets"]["sym"],
            "w_space": s["width_sets"]["space"],
            "recursive": s["recursive"],
            "detect_encoding": s["detect_encoding"],
            "exts_csv": self.cmb_exts.currentText(),
            "preview_mono": self.cb_preview_mono.isChecked(),
        })
        g = self.geometry(); c["window_geo"] = {"x":g.x(),"y":g.y(),"w":g.width(),"h":g.height()}
        save_config(c)

    def closeEvent(self, e):
        self._save_runtime_config()
        super().closeEvent(e)

    # ===== Reプレビュー =====
    def repreview(self):
        if not self._src_plain:
            QMessageBox.information(self, "Reプレビュー", "左側（元テキスト）が空です。先にファイルを開くかD&Dしてください。")
            return
        try:
            self._remember_histories()
            dst = process_text(self._src_plain, self._collect_settings())
            left_html, right_html = render_diff_html(self._src_plain, dst)
            self.src_view.setHtml(left_html)
            self.dst_view.setHtml(right_html)
            # 先頭へ
            self.src_view.verticalScrollBar().setValue(self.src_view.verticalScrollBar().minimum())
            self.dst_view.verticalScrollBar().setValue(self.dst_view.verticalScrollBar().minimum())
        except Exception as ex:
            QMessageBox.critical(self, "エラー", f"Reプレビューで例外: {ex}")

    # ===== 等幅フォント適用 =====
    def _apply_preview_font(self, checked: bool):
        if checked:
            mono = QFont("Consolas", 11)
            mono.setStyleHint(QFont.Monospace)
            mono.setFixedPitch(True)
            self.src_view.setFont(mono)
            self.dst_view.setFont(mono)
        else:
            self.src_view.setFont(QFont(UI_FONT_FAMILY, 11))
            self.dst_view.setFont(QFont(UI_FONT_FAMILY, 11))

    # ===== 単発ファイル =====
    def open_file(self):
        start_dir = self.cfg.get("last_dir","")
        exts = self._collect_settings()["exts"]
        filt = "Text-like (" + " ".join(f"*{e}" for e in sorted(exts)) + ");;All Files (*.*)"
        path, _ = QFileDialog.getOpenFileName(self, "開く", start_dir, filt)
        if not path: return
        self._load_and_preview(Path(path))

    def _load_and_preview(self, p: Path):
        try:
            settings = self._collect_settings()
            src, used_enc = self._read_text(p, settings["detect_encoding"])
            self._src_plain = src
            self._src_path = p  
            dst = process_text(src, settings)
            left_html, right_html = render_diff_html(src, dst)
            self.src_view.setHtml(left_html)
            self.dst_view.setHtml(right_html)
            self.cfg["last_dir"] = str(p.parent); save_config(self.cfg)
            if used_enc and used_enc.lower() != "utf-8":
                QMessageBox.information(self, "エンコ検出", f"{p.name}: {used_enc} で読み込みました。")
            # 先頭へ
            self.src_view.verticalScrollBar().setValue(self.src_view.verticalScrollBar().minimum())
            self.dst_view.verticalScrollBar().setValue(self.dst_view.verticalScrollBar().minimum())
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"読み込み失敗: {p}\n{e}")

    def save_file(self):
        # ベースディレクトリと既定名（元ファイルがあれば同名を提案）
        if self._src_path:
            start_dir = str(self._src_path.parent)
            suggested = self._src_path.name
            default_ext = self._src_path.suffix  # 例: ".txt"
        else:
            start_dir = self.cfg.get("last_dir","")
            suggested = "output.txt"
            default_ext = ""  # 不明なら無理に付けない（ユーザーの入力を尊重）
        init_path = os.path.join(start_dir, suggested) if start_dir else suggested

        # ダイアログ
        path, _ = QFileDialog.getSaveFileName(self, "保存", init_path, "All Files (*.*)")
        if not path:
            return

        try:
            p = Path(path)
            # ★拡張子未入力なら元拡張子を自動付与（default_extがある場合のみ）
            if p.suffix == "" and default_ext:
                p = p.with_suffix(default_ext)

            dst_plain = process_text(self._src_plain, self._collect_settings())
            p.write_text(dst_plain, encoding="utf-8")

            # last_dir更新（保存先フォルダ）
            self.cfg["last_dir"] = str(p.parent); save_config(self.cfg)

            # 保存後に情報表示（拡張子補完が起きたかも含め）
            # （静かでOKなら下の行は削っても良いよ）
            # QMessageBox.information(self, "保存", f"保存しました: {p.name}")
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"保存失敗: {e}")

    # ===== バッチ =====
    def choose_batch_in(self):
        d = QFileDialog.getExistingDirectory(self, "入力フォルダ", self.cfg.get("batch_in",""))
        if d: self.cfg["batch_in"]=d; save_config(self.cfg); QMessageBox.information(self,"選択",f"入力: {d}")

    def choose_batch_out(self):
        d = QFileDialog.getExistingDirectory(self, "出力フォルダ", self.cfg.get("batch_out",""))
        if d: self.cfg["batch_out"]=d; save_config(self.cfg); QMessageBox.information(self,"選択",f"出力: {d}")

    def run_batch(self):
        s = self._collect_settings()
        inp = self.cfg.get("batch_in",""); out = self.cfg.get("batch_out","")
        if not inp or not out:
            QMessageBox.warning(self,"未指定","入力/出力フォルダを選んでください。"); return

        files = list(enumerate_target_files(inp, s["exts"], s["recursive"]))
        total = len(files)
        if total == 0:
            QMessageBox.information(self, "情報", "対象ファイルがありません。"); return

        dlg = QProgressDialog("バッチ処理中...", "キャンセル", 0, total, self)
        dlg.setWindowTitle("進捗 ")
        dlg.setWindowModality(Qt.WindowModal)
        dlg.setAutoClose(True); dlg.setAutoReset(True)
        dlg.show()

        processed = 0
        def progress_cb():
            nonlocal processed
            processed += 1
            dlg.setValue(processed)
            QApplication.processEvents()

        def cancel_cb():
            QApplication.processEvents()
            return dlg.wasCanceled()

        try:
            count = process_directory(inp, out, s, progress_callback=progress_cb, is_canceled=cancel_cb)
            if dlg.wasCanceled():
                QMessageBox.information(self, "中断", f"{processed} / {total} 件でキャンセルしました。")
            else:
                QMessageBox.information(self, "完了", f"{count} 件を処理しました。")
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"バッチ失敗: {e}")
        finally:
            dlg.close()

    # ===== README =====
    def show_readme(self):
        ReadmeDialog(self).exec()

    # ===== D&D =====
    def dragEnterEvent(self, e: QDragEnterEvent):
        if e.mimeData().hasUrls(): e.acceptProposedAction()

    def dropEvent(self, e: QDropEvent):
        try:
            urls = e.mimeData().urls()
            if not urls: return
            s = self._collect_settings(); exts = s["exts"]

            for u in urls:
                p = Path(u.toLocalFile())
                if p.is_file() and is_text_like(p, exts):
                    self._load_and_preview(p); break

            dirs = [Path(u.toLocalFile()) for u in urls if Path(u.toLocalFile()).is_dir()]
            if dirs:
                out = self.cfg.get("batch_out","")
                if not out:
                    d = QFileDialog.getExistingDirectory(self, "出力フォルダ", "")
                    if not d: return
                    self.cfg["batch_out"]=d; save_config(self.cfg)

                for d in dirs:
                    files = list(enumerate_target_files(str(d), s["exts"], s["recursive"]))
                    total = len(files)
                    if total == 0: continue
                    dlg = QProgressDialog(f"{d} を処理中...", "キャンセル", 0, total, self)
                    dlg.setWindowTitle("進捗 ")
                    dlg.setWindowModality(Qt.WindowModal); dlg.show()
                    processed = 0
                    def progress_cb():
                        nonlocal processed
                        processed += 1; dlg.setValue(processed); QApplication.processEvents()
                    def cancel_cb():
                        QApplication.processEvents(); return dlg.wasCanceled()
                    process_directory(str(d), self.cfg["batch_out"], s, progress_callback=progress_cb, is_canceled=cancel_cb)
                    dlg.close()

                QMessageBox.information(self,"完了", f"フォルダD&Dの処理が完了しました。")
        except Exception as ex:
            QMessageBox.critical(self, "エラー", f"D&D処理で例外: {ex}")

    # ===== 読み込み（エンコ検出） =====
    def _read_text(self, p: Path, detect: bool):
        enc = None
        if detect:
            try:
                import chardet
                raw = p.read_bytes()
                res = chardet.detect(raw)
                enc = res.get("encoding") or "utf-8"
                return raw.decode(enc, errors="replace"), enc
            except Exception:
                pass
        return p.read_text(encoding="utf-8", errors="replace"), "utf-8"

    # ===== フレームレス移動/リサイズ =====
    def eventFilter(self, obj, e):
        if obj is self.bg:
            if e.type()==QEvent.MouseButtonPress and e.button()==Qt.LeftButton:
                pos = self.mapFromGlobal(e.globalPosition().toPoint())
                edges = self._edge_at(pos)
                if edges:
                    self._resizing=True; self._resize_edges=edges
                    self._start_geo=self.geometry(); self._start_mouse=e.globalPosition().toPoint()
                else:
                    self._moving=True
                    self._drag_offset = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
                return True
            elif e.type()==QEvent.MouseMove:
                if self._resizing:
                    self._resize_to(e.globalPosition().toPoint()); return True
                if self._moving and (e.buttons()&Qt.LeftButton):
                    self.move(e.globalPosition().toPoint() - self._drag_offset); return True
                self._update_cursor(self._edge_at(self.mapFromGlobal(e.globalPosition().toPoint())))
            elif e.type()==QEvent.MouseButtonRelease:
                self._resizing=False; self._moving=False; return True
        return super().eventFilter(obj, e)

    def _edge_at(self, pos):
        m=RESIZE_MARGIN; r=self.bg.rect(); edges=""
        if pos.y()<=m: edges+="T"
        if pos.y()>=r.height()-m: edges+="B"
        if pos.x()<=m: edges+="L"
        if pos.x()>=r.width()-m: edges+="R"
        return edges

    def _update_cursor(self, edges):
        if edges in ("TL","BR"): self.setCursor(Qt.SizeFDiagCursor)
        elif edges in ("TR","BL"): self.setCursor(Qt.SizeBDiagCursor)
        elif edges in ("L","R"): self.setCursor(Qt.SizeHorCursor)
        elif edges in ("T","B"): self.setCursor(Qt.SizeVerCursor)
        else: self.setCursor(Qt.ArrowCursor)

    def _resize_to(self, gpos):
        dx = gpos.x()-self._start_mouse.x()
        dy = gpos.y()-self._start_mouse.y()
        geo = self._start_geo; x,y,w,h = geo.x(),geo.y(),geo.width(),geo.height()
        minw, minh = self.minimumSize().width(), self.minimumSize().height()
        if "L" in self._resize_edges: new_w=max(minw, w-dx); x+=(w-new_w); w=new_w
        if "R" in self._resize_edges: w=max(minw, w+dx)
        if "T" in self._resize_edges: new_h=max(minh, h-dy); y+=(h-new_h); h=new_h
        if "B" in self._resize_edges: h=max(minh, h+dy)
        self.setGeometry(x,y,w,h)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        h = self.height()
        if getattr(self, "_menu_visible", False):
            self.menuPanel.setGeometry(0, 0, MENU_WIDTH, h)
            self.overlay.setGeometry(0, 0, self.width(), h)
        else:
            self.menuPanel.setGeometry(-MENU_WIDTH, 0, MENU_WIDTH, h)
            self.overlay.setGeometry(0, 0, self.width(), h)

    # ===== スクロール同期（比率連動） =====
    def _sync_scroll_ratio(self, src_edit: QTextEdit, dst_edit: QTextEdit, vertical: bool):
        sbar = src_edit.verticalScrollBar() if vertical else src_edit.horizontalScrollBar()
        dbar = dst_edit.verticalScrollBar() if vertical else dst_edit.horizontalScrollBar()

        smin, smax = sbar.minimum(), sbar.maximum()
        dmin, dmax = dbar.minimum(), dbar.maximum()
        ratio = 0.0 if smax == smin else (sbar.value() - smin) / (smax - smin)
        target = int(round(dmin + ratio * (dmax - dmin)))

        if vertical:
            self._syncing_vert = True
            try: dbar.setValue(target)
            finally: self._syncing_vert = False
        else:
            self._syncing_horz = True
            try: dbar.setValue(target)
            finally: self._syncing_horz = False

    def _on_src_vert_scroll(self, _v):
        if self._syncing_vert: return
        self._sync_scroll_ratio(self.src_view, self.dst_view, vertical=True)

    def _on_dst_vert_scroll(self, _v):
        if self._syncing_vert: return
        self._sync_scroll_ratio(self.dst_view, self.src_view, vertical=True)

    def _on_src_horz_scroll(self, _v):
        if self._syncing_horz: return
        self._sync_scroll_ratio(self.src_view, self.dst_view, vertical=False)

    def _on_dst_horz_scroll(self, _v):
        if self._syncing_horz: return
        self._sync_scroll_ratio(self.dst_view, self.src_view, vertical=False)
