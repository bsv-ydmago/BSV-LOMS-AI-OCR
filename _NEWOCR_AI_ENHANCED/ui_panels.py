"""
ui_panels.py — DocExtract Pro
================================
UI building methods attached to DocExtractorApp.

REDESIGN (FinSet-inspired, v2.1):
  - Sidebar: deep navy background, richer active pill with icon chip,
    pulsing status dot, version badge on logo, grouped nav divider,
    subtle left-edge glow line, and a clean footer.
  - Right panel: clean content card, no tab row, extract toolbar injected
    inside the Extracted content frame.
  - Color palette: deep navy sidebar (#0B1622), white card content area,
    lime/green accent (#5BBF3E / #7DD65C) for active state.
"""

import re
import tkinter as tk
import customtkinter as ctk
from pathlib import Path
from widgets import GradientCanvas, Spinner
from app_constants import *
from doc_classifier_tab import (
    classify_document, extract_fields, extract_financial_figures, DOC_TYPES
)
from lookup_tab import attach as _attach_lookup
from summary_tab import attach as _attach_summary, _refresh_summary
from lu_analysis_tab import attach as _attach_lu_analysis
from dashboard_tab import attach as _attach_dashboard
import admin_logs as _admin_logs_mod
import admin_account as _admin_account_mod
import approval_tab as _approval_tab_mod


# ─────────────────────────────────────────────────────────────────────
#  DESIGN TOKENS
# ─────────────────────────────────────────────────────────────────────
_SB_BG         = "#0B1622"   # sidebar background — deepest navy
_SB_BG2        = "#111E2E"   # slightly lighter surface (unused but kept)
_SB_ACTIVE_BG  = "#162438"   # active nav pill background
_SB_HOVER_BG   = "#131D2D"   # hover background
_SB_ACCENT     = "#5BBF3E"   # lime-green accent (active indicator / glow)
_SB_ACCENT2    = "#7DD65C"   # lighter lime for text on active
_SB_TXT        = "#7A94B0"   # inactive label colour
_SB_TXT_DIM    = "#4A6480"   # very dim — section labels, footer
_SB_TXT_ACT    = "#EEF3FA"   # active label colour
_SB_BORDER     = "#1A2F47"   # subtle divider
_SB_WIDTH      = 220         # sidebar width in pixels

_ICON_CHIP_ACTIVE_BG = "#1A3D1A"   # greenish chip bg when active
_ICON_CHIP_ACTIVE_FG = _SB_ACCENT2

_CARD_BG      = "#FFFFFF"
_PAGE_BG      = "#F4F6FA"
_HDR_BG       = "#FFFFFF"
_HDR_BORDER   = "#E8ECF2"

_PILL_R       = 8            # nav-pill corner radius


# ─────────────────────────────────────────────────────────────────────
#  TOP BAR
# ─────────────────────────────────────────────────────────────────────
def _build_topbar(self):
    bar = tk.Frame(self, bg=_SB_BG, height=52)
    bar.pack(fill="x")
    bar.pack_propagate(False)
    bar.bind("<ButtonPress-1>", self._drag_start)
    bar.bind("<B1-Motion>",     self._drag_move)

    # Window controls
    ctrl = tk.Frame(bar, bg=_SB_BG)
    ctrl.pack(side="right", fill="y", padx=8)

    close_btn = tk.Label(ctrl, text="✕", font=F(10, "bold"),
                         fg="#7A94B0", bg=_SB_BG, cursor="hand2",
                         width=3, anchor="center")
    close_btn.bind("<Enter>",    lambda e: close_btn.config(fg=WHITE, bg=ACCENT_RED))
    close_btn.bind("<Leave>",    lambda e: close_btn.config(fg="#7A94B0", bg=_SB_BG))
    close_btn.bind("<Button-1>", lambda e: self._confirm_close())
    close_btn.pack(side="right", padx=(4, 2), fill="y")

    min_btn = tk.Label(ctrl, text="─", font=F(10, "bold"),
                       fg="#7A94B0", bg=_SB_BG, cursor="hand2",
                       width=3, anchor="center")
    min_btn.bind("<Enter>",    lambda e: min_btn.config(fg=WHITE, bg=_SB_HOVER_BG))
    min_btn.bind("<Leave>",    lambda e: min_btn.config(fg="#7A94B0", bg=_SB_BG))
    min_btn.bind("<Button-1>", lambda e: self._do_minimize())
    min_btn.pack(side="right", padx=(4, 2), fill="y")

    # Branding
    brand = tk.Frame(bar, bg=_SB_BG)
    brand.pack(side="left", fill="y", padx=(16, 0))

    mark = tk.Canvas(brand, width=28, height=28, bg=_SB_BG, highlightthickness=0)
    mark.pack(side="left", padx=(0, 10), pady=12)
    mark.create_rectangle(0, 9, 16, 28, fill=NAVY_LIGHT,   outline="")
    mark.create_rectangle(10, 0, 28, 19, fill=_SB_ACCENT,  outline="")
    mark.create_rectangle(13, 10, 15, 12, fill=_SB_BG,     outline="")

    tk.Label(brand, text="DocExtract Pro",
             font=F(13, "bold"), fg=WHITE, bg=_SB_BG).pack(side="left")
    tk.Label(brand, text=" — Banco San Vicente",
             font=F(10), fg=_SB_TXT, bg=_SB_BG).pack(side="left")

    self._topbar_status = tk.Label(
        bar, text="● Ready",
        font=F(8, "bold"), fg=_SB_ACCENT,
        bg="#1A2F47", padx=12, pady=4, relief="flat"
    )
    self._topbar_status.pack(side="right", padx=(0, 20), pady=14)

    # Zoom controls removed (feature no longer used).


# ─────────────────────────────────────────────────────────────────────
#  LEFT SIDEBAR — redesigned nav
# ─────────────────────────────────────────────────────────────────────

# (tab_key, icon, label, badge_text_or_None)
_NAV_ITEMS = [
    ("dashboard",      "🏠",  "Dashboard",    None),
    ("cibi",           "📋",  "CIBI Mode",    None),
    ("extract",        "📄",  "Extracted",    None),
    ("analysis",       "🏦",  "CIBI Analysis",None),
    ("summary",        "📊",  "Summary",      None),
]

_NAV_ITEMS_2 = [
    ("lookup",         "🔎",  "Look-Up",      None),
    ("lookup_summary", "📋",  "LU Summary",   None),
    ("lu_analysis",    "📈",  "LU Analysis",  None),
    ("logs",           "🗒",  "Logs",         "ADMIN"),
    ("accounts",       "👤",  "Accounts",     "ADMIN"),
    ("approvals", "✅", "Approvals", "ADMIN"),
]


def _build_nav_pill(self, parent, tab_key, icon, label, badge=None):
    """Build one nav pill row and register it in self._nav_btns."""

    PILL_H = 46

    outer = tk.Frame(parent, bg=_SB_BG, height=PILL_H, cursor="hand2")
    outer.pack(fill="x", pady=1)
    outer.pack_propagate(False)

    # Left accent stripe (3 px, revealed when active)
    accent_bar = tk.Frame(outer, bg=_SB_ACCENT, width=3)

    # Icon chip — small rounded container (simulated with a Label + relief)
    chip_frame = tk.Frame(outer, bg=_SB_BG, width=30, height=30)
    chip_frame.pack(side="left", padx=(10, 6), pady=8)
    chip_frame.pack_propagate(False)

    icon_lbl = tk.Label(chip_frame,
                        text=icon,
                        font=("Segoe UI Emoji", 12),
                        fg=_SB_TXT, bg=_SB_BG,
                        anchor="center")
    icon_lbl.place(relx=0.5, rely=0.5, anchor="center")

    text_lbl = tk.Label(outer, text=label,
                        font=F(10), fg=_SB_TXT, bg=_SB_BG,
                        anchor="w")
    text_lbl.pack(side="left", fill="x", expand=True)

    badge_lbl = None
    if badge:
        badge_lbl = tk.Label(outer, text=badge,
                             font=F(7, "bold"),
                             fg=_SB_ACCENT2, bg="#0F2610",
                             padx=5, pady=1,
                             relief="flat")
        badge_lbl.pack(side="right", padx=(0, 10))

    self._nav_btns[tab_key] = (outer, accent_bar, chip_frame, icon_lbl, text_lbl, badge_lbl)

    def _click(e=None, k=tab_key): self._switch_tab(k)

    def _enter(e=None, pill=outer, chip=chip_frame, icon=icon_lbl, txt=text_lbl, key=tab_key):
        if self._active_tab_key.get() != key:
            for w in (pill, chip, icon, txt):
                w.config(bg=_SB_HOVER_BG)

    def _leave(e=None, pill=outer, chip=chip_frame, icon=icon_lbl, txt=text_lbl, key=tab_key):
        if self._active_tab_key.get() != key:
            for w in (pill, chip, icon, txt):
                w.config(bg=_SB_BG)

    for w in (outer, chip_frame, icon_lbl, text_lbl):
        w.bind("<Button-1>", _click)
        w.bind("<Enter>",    _enter)
        w.bind("<Leave>",    _leave)
    if badge_lbl:
        badge_lbl.bind("<Button-1>", _click)
        badge_lbl.bind("<Enter>",    _enter)
        badge_lbl.bind("<Leave>",    _leave)


def _build_left(self, p):
    p.configure(bg=_SB_BG)
    sidebar = p

    # ── Thin left-edge glow line ──────────────────────────────────────
    glow = tk.Canvas(sidebar, width=1, bg=_SB_BG, highlightthickness=0)
    glow.place(x=0, y=0, relheight=1.0, width=1)
    # We'll draw it after the window maps; schedule it
    def _draw_glow(e=None):
        h = glow.winfo_height()
        if h < 10:
            sidebar.after(100, _draw_glow)
            return
        glow.delete("all")
        steps = 30
        for i in range(steps):
            t    = i / steps
            mid  = abs(t - 0.5) * 2        # 0 at center, 1 at edges
            alpha = max(0, 1 - mid)
            r, g, b = 91, 191, 62
            hex_c = "#{:02x}{:02x}{:02x}".format(
                int(r * alpha * 0.5),
                int(g * alpha * 0.5),
                int(b * alpha * 0.5)
            )
            y0 = int(h * i / steps)
            y1 = int(h * (i + 1) / steps) + 1
            glow.create_rectangle(0, y0, 1, y1, fill=hex_c, outline="")
    sidebar.bind("<Map>",       _draw_glow)
    sidebar.bind("<Configure>", _draw_glow)

    # ── Logo / branding block ─────────────────────────────────────────
    logo_block = tk.Frame(sidebar, bg=_SB_BG, height=72)
    logo_block.pack(fill="x")
    logo_block.pack_propagate(False)

    logo_loaded = False
    if LOGO_PATH.exists():
        try:
            from PIL import Image
            img    = Image.open(LOGO_PATH).convert("RGBA")
            bg_pil = Image.new(
                "RGBA", img.size,
                tuple(int(_SB_BG[i:i+2], 16) for i in (1, 3, 5)) + (255,)
            )
            bg_pil.paste(img, mask=img.split()[3])
            bg_pil = bg_pil.convert("RGB")
            bg_pil.thumbnail((150, 36), Image.LANCZOS)
            self._logo_img = ctk.CTkImage(
                light_image=bg_pil, dark_image=bg_pil,
                size=(bg_pil.width, bg_pil.height)
            )
            lf = ctk.CTkFrame(logo_block, fg_color="transparent")
            lf.place(relx=0.08, rely=0.5, anchor="w")
            ctk.CTkLabel(lf, image=self._logo_img, text="",
                         fg_color="transparent").pack()
            logo_loaded = True
        except Exception:
            pass

    if not logo_loaded:
        inner = tk.Frame(logo_block, bg=_SB_BG)
        inner.place(relx=0.5, rely=0.5, anchor="center")

        mark = tk.Canvas(inner, width=26, height=26,
                         bg=_SB_BG, highlightthickness=0)
        mark.pack(side="left", padx=(0, 8))
        mark.create_rectangle(0, 8, 15, 26, fill=NAVY_LIGHT,  outline="")
        mark.create_rectangle(11, 0, 26, 18, fill=_SB_ACCENT, outline="")
        mark.create_rectangle(13, 9, 15, 11, fill=_SB_BG,     outline="")

        lbl_col = tk.Frame(inner, bg=_SB_BG)
        lbl_col.pack(side="left")
        tk.Label(lbl_col, text="BSV AI-OCR",
                 font=F(11, "bold"), fg=WHITE, bg=_SB_BG).pack(anchor="w")
        tk.Label(lbl_col, text="Banco San Vicente",
                 font=F(7), fg=_SB_TXT_DIM, bg=_SB_BG).pack(anchor="w")

    # Version badge (top-right of logo block)
    ver_badge = tk.Label(logo_block, text="v2.0",
                         font=F(7, "bold"),
                         fg=_SB_ACCENT2, bg="#0F2610",
                         padx=6, pady=2)
    ver_badge.place(relx=1.0, x=-10, rely=0.5, anchor="e")

    # Border under logo
    tk.Frame(sidebar, bg=_SB_BORDER, height=1).pack(fill="x")

    # ── Status dot row ────────────────────────────────────────────────
    # ── Status / welcome block ────────────────────────────────────────
    status_row = tk.Frame(sidebar, bg=_SB_BG)
    status_row.pack(fill="x", padx=18, pady=(10, 6))

    # Dot aligned to the "Welcome" line
    dot_col = tk.Frame(status_row, bg=_SB_BG)
    dot_col.pack(side="left", anchor="n", pady=(3, 0))

    self._status_dot = tk.Canvas(dot_col, width=8, height=8,
                                 bg=_SB_BG, highlightthickness=0)
    self._status_dot.pack(padx=(0, 8))
    self._status_dot.create_oval(1, 1, 7, 7, fill=_SB_ACCENT, outline="")

    # Two-line text block: "Welcome" + username on separate lines
    text_col = tk.Frame(status_row, bg=_SB_BG)
    text_col.pack(side="left", fill="x", expand=True)

    _username = getattr(self, "_current_username", None) or "User"
    if len(_username) > 20:
        _username = _username[:18] + "…"
    self._display_username = _username   # store for loader restore

    # Fetch position from DB
    # Fetch position and role from DB
    _position = ""
    _user_role = "user"  # safe default — least privilege
    try:
        _conn = self.get_conn()
        if _conn:
            _cur = _conn.cursor()
            _cur.execute(
                "SELECT position, role FROM users WHERE id = %s",
                (getattr(self, '_current_user_id', None),)
            )
            _row = _cur.fetchone()
            _cur.close()
            if _row:
                if _row[0]:
                    _position = _row[0]
                if _row[1]:
                    _user_role = _row[1].strip().lower()
    except Exception:
        pass

    # Store role on self so other parts of the app can reference it
    self._current_user_role = _user_role

    tk.Label(text_col, text="WELCOME",
             font=F(8), fg=_SB_TXT, bg=_SB_BG,
             anchor="w").pack(anchor="w")

    self._status_sidebar_lbl = tk.Label(
        text_col, text=_username,
        font=F(10, "bold"), fg=_SB_ACCENT2, bg=_SB_BG,
        anchor="w"
    )
    self._status_sidebar_lbl.pack(anchor="w")

    # Position label — only shown if position exists in DB
    self._position_sidebar_lbl = tk.Label(
        text_col, text=_position,
        font=F(7), fg=_SB_TXT_DIM, bg=_SB_BG,
        anchor="w",
        wraplength=170,
        justify="left"
    )
    self._position_sidebar_lbl.pack(anchor="w")

    # ── Section label ─────────────────────────────────────────────────
    tk.Label(sidebar, text="NAVIGATION",
             font=F(7, "bold"), fg=_SB_TXT_DIM, bg=_SB_BG,
             anchor="w").pack(fill="x", padx=18, pady=(10, 4))

    # ── Nav pills ─────────────────────────────────────────────────────
    self._nav_btns       = {}
    self._active_tab_key = tk.StringVar(value="dashboard")

    # ── Role-based nav visibility ─────────────────────────────────────
    _ROLE_TABS_FALLBACK = {
        "super admin":         {"dashboard","lookup_summary","lu_analysis","logs","accounts","approvals"},
        "account officer":     {"cibi","extract","analysis","summary"},
        "credit risk officer": {"lookup","lookup_summary","lu_analysis"},
        "user":                {"cibi"},
    }
    # For unknown/new roles fall back to minimal access, not "user" preset
    _allowed = _ROLE_TABS_FALLBACK.get(_user_role, {"cibi"})

    try:
        _rtc_conn = self.get_conn()
        if _rtc_conn:
            _rtc_cur = _rtc_conn.cursor()
            _rtc_cur.execute(
                "SELECT tab_access FROM role_tab_config WHERE role = %s",
                (_user_role,)
            )
            _rtc_row = _rtc_cur.fetchone()
            _rtc_cur.close()
            if _rtc_row and _rtc_row[0]:
                _allowed = set(_rtc_row[0])
            # If role exists in DB but has no role_tab_config row yet,
            # keep the fallback (cibi only) — safe minimum access
    except Exception:
        pass   # silently keep the fallback

    nav_container = tk.Frame(sidebar, bg=_SB_BG)
    nav_container.pack(fill="x", padx=8)

    _HIDDEN_TABS = {"cibi", "extract", "analysis", "summary"}
    for tab_key, icon, label, badge in _NAV_ITEMS:
        if tab_key in _allowed and tab_key not in _HIDDEN_TABS:
            _build_nav_pill(self, nav_container, tab_key, icon, label, badge)

    # Only show the second group + divider if the user can see any of those tabs
    _nav2_visible = [x for x in _NAV_ITEMS_2 if x[0] in _allowed]
    if _nav2_visible:
        div_row = tk.Frame(sidebar, bg=_SB_BG)
        div_row.pack(fill="x", padx=16, pady=(6, 4))
        tk.Frame(div_row, bg=_SB_BORDER, height=1).pack(fill="x")

        nav_container2 = tk.Frame(sidebar, bg=_SB_BG)
        nav_container2.pack(fill="x", padx=8)

        for tab_key, icon, label, badge in _nav2_visible:
            _build_nav_pill(self, nav_container2, tab_key, icon, label, badge)

    # ── Spacer ────────────────────────────────────────────────────────
    tk.Frame(sidebar, bg=_SB_BG).pack(fill="both", expand=True)

    # ── Utility links ─────────────────────────────────────────────────
    tk.Frame(sidebar, bg=_SB_BORDER, height=1).pack(fill="x", padx=10, pady=(0, 4))

    # ── Log Out button ────────────────────────────────────────────────
    util_frame = tk.Frame(sidebar, bg=_SB_BG)
    util_frame.pack(fill="x", padx=8, pady=(0, 6))

    logout_row = tk.Frame(util_frame, bg=_SB_BG, cursor="hand2", height=38)
    logout_row.pack(fill="x", pady=1)
    logout_row.pack_propagate(False)

    logout_icon = tk.Label(logout_row, text="⏻", font=("Segoe UI Emoji", 11),
                           fg="#E05555", bg=_SB_BG, width=3, anchor="center")
    logout_icon.pack(side="left", padx=(10, 4))

    logout_lbl = tk.Label(logout_row, text="Log Out", font=F(10),
                          fg="#E05555", bg=_SB_BG, anchor="w")
    logout_lbl.pack(side="left", fill="x", expand=True)

    def _do_logout(e=None):
        import tkinter.messagebox as mb
        confirmed = mb.askyesno(
            "Log Out",
            "Are you sure you want to log out?",
            icon="warning"
        )
        if not confirmed:
            return

        # Close DB connection cleanly
        if getattr(self, "db_conn", None) and not self.db_conn.closed:
            try:
                self.db_conn.close()
            except Exception:
                pass

        try:
            from admin_logs import insert_log
            insert_log(self, "LOGGED OUT", f"User '{getattr(self, '_current_username', '')}' logged out")
        except Exception:
            pass

        # ── Clear active session flag ──────────────────────────────────
        try:
            _conn = self.get_conn()
            if _conn:
                _cur = _conn.cursor()
                _cur.execute(
                    "UPDATE public.users SET is_logged_in = FALSE WHERE id = %s",
                    (getattr(self, '_current_user_id', None),)
                )
                _conn.commit()
                _cur.close()
        except Exception as ex:
            print(f"Logout session clear error: {ex}")
        # ──────────────────────────────────────────────────────────────

        self._is_closing = True

        self._is_closing = True

        # Cancel any pending jobs
        for attr in ("_sim_build_job", "_sum_search_after",
                    "_gen_sum_search_after", "_job"):
            job = getattr(self, attr, None)
            if job:
                try:
                    self.after_cancel(job)
                except Exception:
                    pass

        def _relaunch_login():
            import importlib, sys

            if "login" in sys.modules:
                importlib.reload(sys.modules["login"])
            from login import LoginWindow

            # In ui_panels.py _relaunch_app
            def _relaunch_app(user_id, username):
                if "app" in sys.modules:
                    importlib.reload(sys.modules["app"])
                from app import DocExtractorApp
                app = DocExtractorApp(user_id=user_id, username=username)
                app.mainloop()

            login = LoginWindow(on_success=_relaunch_app)

            # Force accurate centering after window is fully ready
            login.update_idletasks()
            sw = login.winfo_screenwidth()
            sh = login.winfo_screenheight()
            x  = (sw - login.W) // 2
            y  = (sh - login.H) // 2
            login.geometry(f"{login.W}x{login.H}+{x}+{y}")
            login.lift()
            login.focus_force()
            login.mainloop()

        self.after(0, lambda: [self.destroy(), _relaunch_login()])

    def _logout_enter(e=None):
        for w in (logout_row, logout_icon, logout_lbl):
            w.config(bg="#1A0F0F")

    def _logout_leave(e=None):
        for w in (logout_row, logout_icon, logout_lbl):
            w.config(bg=_SB_BG)

    for w in (logout_row, logout_icon, logout_lbl):
        w.bind("<Button-1>", _do_logout)
        w.bind("<Enter>",    _logout_enter)
        w.bind("<Leave>",    _logout_leave)

    # ── Version footer ────────────────────────────────────────────────
    tk.Frame(sidebar, bg=_SB_BORDER, height=1).pack(fill="x", padx=16)
    ver = tk.Frame(sidebar, bg=_SB_BG)
    ver.pack(fill="x", pady=(6, 12), padx=18)
    tk.Label(ver, text="Gemini 2.5 Flash · PaddleOCR",
             font=F(7), fg="#2D4F7A", bg=_SB_BG, anchor="w").pack(anchor="w")
    tk.Label(ver, text="BSV AI-OCR v2.0",
             font=F(7), fg="#2D4F7A", bg=_SB_BG, anchor="w").pack(anchor="w")


def _apply_nav_active(self, active_key):
    """Update sidebar nav pill styles to reflect the active tab."""
    self._active_tab_key.set(active_key)

    for key, widgets in self._nav_btns.items():
        pill, accent_bar, chip_frame, icon_lbl, text_lbl, badge_lbl = widgets
        if key == active_key:
            pill.config(bg=_SB_ACTIVE_BG)
            chip_frame.config(bg=_ICON_CHIP_ACTIVE_BG)
            icon_lbl.config(fg=_ICON_CHIP_ACTIVE_FG, bg=_ICON_CHIP_ACTIVE_BG)
            text_lbl.config(fg=_SB_TXT_ACT, bg=_SB_ACTIVE_BG, font=F(10, "bold"))
            if badge_lbl:
                badge_lbl.config(bg=_SB_ACTIVE_BG)
            # Show accent stripe
            accent_bar.place(x=0, y=0, width=3, relheight=1.0)
            accent_bar.lift()
        else:
            pill.config(bg=_SB_BG)
            chip_frame.config(bg=_SB_BG)
            icon_lbl.config(fg=_SB_TXT, bg=_SB_BG)
            text_lbl.config(fg=_SB_TXT, bg=_SB_BG, font=F(10))
            if badge_lbl:
                badge_lbl.config(bg=_SB_BG)
            accent_bar.place_forget()


# ─────────────────────────────────────────────────────────────────────
#  RIGHT PANEL
# ─────────────────────────────────────────────────────────────────────
def _build_right(self, p):
    p.configure(bg=_PAGE_BG)
    page = p

    # ── Top header bar ────────────────────────────────────────────────
    hdr = tk.Frame(page, bg=_HDR_BG, height=64)
    hdr.pack(fill="x")
    hdr.pack_propagate(False)
    tk.Frame(page, bg=_HDR_BORDER, height=1).pack(fill="x")

    hdr_inner = tk.Frame(hdr, bg=_HDR_BG)
    hdr_inner.pack(side="left", fill="y", padx=(24, 0))

    self._page_title_lbl = tk.Label(
        hdr_inner, text="CIBI Mode",
        font=F(17, "bold"), fg=NAVY_DEEP, bg=_HDR_BG
    )
    self._page_title_lbl.pack(side="left", anchor="center")

    status_pill = tk.Frame(hdr, bg=LIME_MIST,
                           highlightbackground=LIME_MID, highlightthickness=1)
    status_pill.pack(side="left", padx=(14, 0), pady=18)
    self._status_lbl = tk.Label(
        status_pill, text="●  Ready",
        font=F(8, "bold"), fg=LIME_DARK,
        bg=LIME_MIST, padx=12, pady=4
    )
    self._status_lbl.pack()

    self._copy_btn = ctk.CTkButton(
        hdr, text="⎘  Copy", command=self._copy,
        width=100, height=32, corner_radius=6,
        fg_color=NAVY_MIST, hover_color=NAVY_GHOST, text_color=NAVY_MID,
        font=FF(9, "bold"),
        border_width=1, border_color=BORDER_MID
    )
    self._copy_btn.pack(side="right", padx=(0, 20))

    # ── Pipeline caption ──────────────────────────────────────────────
    pipe_row = tk.Frame(page, bg=_PAGE_BG)
    pipe_row.pack(fill="x", padx=24, pady=(8, 0))
    tk.Label(
        pipe_row,
        text="Pipeline:  PaddleOCR  →  Gemini 2.5 Flash VLM  →  Confidence Scoring  →  CIBI Credit Analysis",
        font=F(8), fg=TXT_MUTED, bg=_PAGE_BG
    ).pack(anchor="w")

    # ── Search bar ────────────────────────────────────────────────────
    search_row = tk.Frame(page, bg=_PAGE_BG)
    search_row.pack(fill="x", padx=24, pady=(6, 8))

    search_wrap = tk.Frame(search_row, bg=WHITE,
                           highlightbackground=BORDER_MID,
                           highlightthickness=1)
    search_wrap.pack(side="left", fill="x", expand=True)

    tk.Label(search_wrap, text="🔍", font=("Segoe UI Emoji", 10),
             bg=WHITE, fg=NAVY_PALE).pack(side="left", padx=(10, 2))

    self._search_var   = tk.StringVar()
    self._search_entry = tk.Entry(
        search_wrap, textvariable=self._search_var,
        font=F(10), fg=TXT_NAVY, bg=WHITE,
        relief="flat", bd=0, insertbackground=NAVY_MID, width=28
    )
    self._search_entry.pack(side="left", fill="x", expand=True, pady=6)
    self._search_entry.bind("<Return>",   lambda e: self._do_search())
    self._search_entry.bind("<KP_Enter>", lambda e: self._do_search())
    self._search_entry.bind("<Escape>",   lambda e: self._clear_search())
    self._search_var.trace_add("write",   lambda *a: self._do_search())

    self._match_lbl = tk.Label(search_wrap, text="",
                               font=F(8), fg=TXT_SOFT, bg=WHITE, padx=8)
    self._match_lbl.pack(side="left")

    nav_frame = tk.Frame(search_row, bg=_PAGE_BG)
    nav_frame.pack(side="left", padx=(6, 0))

    for symbol, cmd in [("▲", self._search_prev), ("▼", self._search_next)]:
        ctk.CTkButton(
            nav_frame, text=symbol, width=30, height=30, corner_radius=6,
            fg_color=WHITE, hover_color=NAVY_MIST, text_color=NAVY_MID,
            font=FF(9, "bold"),
            border_width=1, border_color=BORDER_MID,
            command=cmd
        ).pack(side="left", padx=(0, 4))

    ctk.CTkButton(
        nav_frame, text="✕", width=30, height=30, corner_radius=6,
        fg_color=WHITE, hover_color="#FFE8E8", text_color=ACCENT_RED,
        font=FF(9, "bold"),
        border_width=1, border_color=BORDER_MID,
        command=self._clear_search
    ).pack(side="left")

    self._prev_btn = nav_frame.winfo_children()[0]
    self._next_btn = nav_frame.winfo_children()[1]

    # ── Content card ──────────────────────────────────────────────────
    card_outer = tk.Frame(page, bg=_HDR_BORDER, padx=1, pady=1)
    card_outer.pack(fill="both", expand=True, padx=24, pady=(0, 16))
    card = tk.Frame(card_outer, bg=_CARD_BG)
    card.pack(fill="both", expand=True)

    top_acc = tk.Canvas(card, height=4, bg=_CARD_BG, highlightthickness=0)
    top_acc.pack(fill="x")
    top_acc.bind("<Configure>",
                 lambda e, c=top_acc: self._hbar(c, NAVY_DEEP, _SB_ACCENT, 80))

    # ── Loader frame ──────────────────────────────────────────────────
    self._loader_frame = tk.Frame(card, bg=_CARD_BG)
    tk.Frame(self._loader_frame, bg=_CARD_BG).pack(expand=True, fill="both")
    center = tk.Frame(self._loader_frame, bg=_CARD_BG)
    center.pack()
    self._spinner = Spinner(center, size=96, bg=_CARD_BG)
    self._spinner.pack(pady=(0, 20))
    tk.Label(center, text="Processing…",
             font=F(15, "bold"), fg=NAVY_DEEP, bg=_CARD_BG).pack()
    self._stage_lbl = tk.Label(center, text="Initialising…",
                               font=F(10), fg=TXT_SOFT, bg=_CARD_BG)
    self._stage_lbl.pack(pady=(6, 2))
    self._pct_lbl = tk.Label(center, text="0%",
                             font=F(13, "bold"), fg=LIME_DARK, bg=_CARD_BG)
    self._pct_lbl.pack(pady=(0, 16))
    self._prog_bar = ctk.CTkProgressBar(
        center, width=300, height=8, corner_radius=4,
        fg_color=NAVY_MIST, progress_color=LIME_MID, border_width=0
    )
    self._prog_bar.set(0)
    self._prog_bar.pack()
    tk.Frame(self._loader_frame, bg=_CARD_BG).pack(expand=True, fill="both")

    # Content panels
    self._build_classifier_panel(card)

    self._analysis_frame = tk.Frame(card, bg=_CARD_BG)
    sb2 = tk.Scrollbar(self._analysis_frame, relief="flat",
                       troughcolor=OFF_WHITE,
                       bg=BORDER_LIGHT, width=8, bd=0)
    sb2.pack(side="right", fill="y")
    self._analysis_box = tk.Text(
        self._analysis_frame, wrap="word", font=FMONO(11),
        fg=TXT_NAVY, bg=_CARD_BG, relief="flat", bd=0,
        padx=32, pady=24, spacing1=6, spacing2=3, spacing3=8,
        insertbackground=LIME_DARK, yscrollcommand=sb2.set,
        state="disabled", cursor="arrow",
        selectbackground=NAVY_GHOST, selectforeground=TXT_NAVY
    )
    self._analysis_box.pack(side="left", fill="both", expand=True)
    sb2.config(command=self._analysis_box.yview)
    self._configure_analysis_tags(self._analysis_box)

    self._build_summary_panel(card)
    self._build_dashboard_panel(card)
    self._build_cibi_output_panel(card)
    self._build_lookup_panel(card)
    self._build_lookup_summary_panel(card)
    self._build_lu_analysis_panel(card)
    self._build_logs_panel(card)
    self._build_accounts_panel(card)
    self._build_approval_panel(card)

    self._put_placeholder()
    self._current_tab = "dashboard"
    self._switch_tab("dashboard")


# ─────────────────────────────────────────────────────────────────────
#  EXTRACT TOOLBAR
# ─────────────────────────────────────────────────────────────────────
def _build_extract_toolbar(self, parent):
    BG = _CARD_BG

    hdr_row = tk.Frame(parent, bg=BG)
    hdr_row.pack(fill="x", padx=20, pady=(14, 6))

    lbl_block = tk.Frame(hdr_row, bg=BG)
    lbl_block.pack(side="left", fill="y")
    tk.Frame(lbl_block, bg=_SB_ACCENT, width=3, height=14).pack(
        side="left", padx=(0, 8), pady=3)
    tk.Label(lbl_block, text="FILES & ACTIONS",
             font=F(7, "bold"), fg=TXT_SOFT, bg=BG).pack(side="left")

    self._toolbar_count_lbl = tk.Label(
        hdr_row, text="No files selected",
        font=F(8), fg=TXT_MUTED, bg=BG
    )
    self._toolbar_count_lbl.pack(side="right")

    middle_row = tk.Frame(parent, bg=BG)
    middle_row.pack(fill="x", padx=20, pady=(0, 6))

    drop_chip = tk.Frame(
        middle_row, bg=SIDEBAR_ITEM,
        highlightbackground=_SB_ACCENT, highlightthickness=1,
        width=110, height=52
    )
    drop_chip.pack(side="left", padx=(0, 10))
    drop_chip.pack_propagate(False)
    inner_drop = tk.Frame(drop_chip, bg=SIDEBAR_ITEM)
    inner_drop.place(relx=0.5, rely=0.5, anchor="center")
    self._icon_lbl = tk.Label(
        inner_drop, text="📁",
        font=("Segoe UI Emoji", 15), fg=_SB_ACCENT, bg=SIDEBAR_ITEM
    )
    self._icon_lbl.pack()
    self._filename_lbl = tk.Label(
        inner_drop, text="Drop / Browse",
        font=F(7), fg=TXT_SOFT, bg=SIDEBAR_ITEM,
        wraplength=96, justify="center"
    )
    self._filename_lbl.pack(pady=(1, 0))

    list_outer = tk.Frame(
        middle_row, bg=SIDEBAR_ITEM,
        highlightbackground="#1E3A5F", highlightthickness=1
    )
    list_outer.pack(side="left", fill="x", expand=True, ipady=2)

    list_hdr = tk.Frame(list_outer, bg=SIDEBAR_ITEM)
    list_hdr.pack(fill="x", padx=8, pady=(3, 1))
    tk.Label(list_hdr, text="SELECTED FILES",
             font=F(7, "bold"), fg=TXT_SOFT, bg=SIDEBAR_ITEM).pack(side="left")
    self._clear_btn = tk.Label(
        list_hdr, text="✕ Clear",
        font=F(7, "bold"), fg=ACCENT_RED, bg=SIDEBAR_ITEM, cursor="hand2"
    )
    self._clear_btn.pack(side="right")
    self._clear_btn.bind("<Button-1>", lambda e: self._clear_files())

    list_body = tk.Frame(list_outer, bg=SIDEBAR_ITEM, height=36)
    list_body.pack(fill="x", padx=4, pady=(0, 3))
    list_body.pack_propagate(False)

    list_sb = tk.Scrollbar(list_body, relief="flat",
                           troughcolor=SIDEBAR_ITEM, bg=SIDEBAR_HVR,
                           width=5, bd=0)
    list_sb.pack(side="right", fill="y")

    self._file_listbox = tk.Listbox(
        list_body,
        font=F(8), fg="#C5D8F5", bg=SIDEBAR_ITEM,
        relief="flat", bd=0,
        selectbackground=SIDEBAR_HVR, selectforeground=WHITE,
        activestyle="none",
        yscrollcommand=list_sb.set,
        height=2,
    )
    self._file_listbox.pack(side="left", fill="both", expand=True)
    list_sb.config(command=self._file_listbox.yview)
    self._file_listbox.bind("<Button-3>", self._remove_selected_file)

    btn_row = tk.Frame(parent, bg=BG)
    btn_row.pack(fill="x", padx=20, pady=(0, 10))

    self._browse_btn = ctk.CTkButton(
        btn_row, text="📁  Browse",
        command=self._browse,
        height=34, corner_radius=7,
        fg_color=_SB_ACCENT, hover_color=LIME_BRIGHT,
        text_color="#0B1622",
        font=FF(9, "bold"),
        border_width=0, width=110
    )
    self._browse_btn.pack(side="left", padx=(0, 5))

    self._add_btn = ctk.CTkButton(
        btn_row, text="➕  Add More",
        command=self._browse_add,
        height=34, corner_radius=7,
        fg_color=SIDEBAR_ITEM, hover_color=SIDEBAR_HVR,
        text_color="#C5D8F5",
        font=FF(9),
        border_width=1, border_color="#1E3A5F",
        state="disabled", width=110
    )
    self._add_btn.pack(side="left", padx=(0, 5))

    tk.Frame(btn_row, bg=BORDER_LIGHT, width=1, height=28).pack(
        side="left", padx=(4, 9), pady=3)

    self._ext_btn = ctk.CTkButton(
        btn_row, text="⚡  Extract Text",
        command=self._start_extraction,
        height=34, corner_radius=7,
        fg_color=NAVY_LIGHT, hover_color=NAVY_PALE,
        text_color=WHITE,
        font=FF(9, "bold"),
        state="disabled", border_width=0, width=130
    )
    self._ext_btn.pack(side="left", padx=(0, 5))

    self._analyze_btn = ctk.CTkButton(
        btn_row, text="🏦  Analyze CIBI",
        command=self._start_analysis,
        height=34, corner_radius=7,
        fg_color=SIDEBAR_ITEM, hover_color=SIDEBAR_HVR,
        text_color=_SB_ACCENT,
        font=FF(9, "bold"),
        state="disabled",
        border_width=1, border_color=LIME_DARK, width=140
    )
    self._analyze_btn.pack(side="left", padx=(0, 5))

    self._analyze_excel_btn = ctk.CTkButton(
        btn_row, text="📊  Analyze from Excel",
        command=self._start_cibi_analysis_from_excel,
        height=34, corner_radius=7,
        fg_color=SIDEBAR_ITEM, hover_color=SIDEBAR_HVR,
        text_color=LIME_PALE,
        font=FF(9, "bold"),
        border_width=1, border_color=LIME_DARK, width=175
    )
    self._analyze_excel_btn.pack(side="left")

    tk.Label(
        btn_row,
        text="Right-click a file in the list to remove it",
        font=F(7), fg=TXT_MUTED, bg=BG
    ).pack(side="right")

    tk.Frame(parent, bg=BORDER_LIGHT, height=1).pack(fill="x", padx=20, pady=(0, 4))

    def _update_toolbar_count(event=None):
        n = self._file_listbox.size()
        if n == 0:
            self._toolbar_count_lbl.config(text="No files selected", fg=TXT_MUTED)
            self._filename_lbl.config(text="Drop / Browse")
        elif n == 1:
            name  = self._file_listbox.get(0)
            short = (name[:22] + "…") if len(name) > 24 else name
            self._toolbar_count_lbl.config(text=short, fg=TXT_NAVY)
            self._filename_lbl.config(text="1 file")
        else:
            self._toolbar_count_lbl.config(text=f"{n} files selected", fg=_SB_ACCENT)
            self._filename_lbl.config(text=f"{n} files")

    self._file_listbox.bind("<<ListboxSelect>>", _update_toolbar_count)
    self._update_toolbar_count = _update_toolbar_count


# ─────────────────────────────────────────────────────────────────────
#  TAG CONFIGURATION
# ─────────────────────────────────────────────────────────────────────
def _configure_analysis_tags(self, box):
    sz = 11
    ff = FMONO(11)[0]
    box.tag_configure("search_match",    background=LIME_PALE,    foreground=TXT_NAVY)
    box.tag_configure("search_current",  background=LIME_BRIGHT,  foreground=NAVY_DEEP)
    box.tag_configure("sec_header",      font=(ff, sz+2, "bold"), foreground=NAVY_DEEP,
                      spacing1=18, spacing3=6,  lmargin1=0,  lmargin2=0)
    box.tag_configure("sub_header",      font=(ff, sz,   "bold"), foreground=NAVY_MID,
                      spacing1=10, spacing3=4,  lmargin1=10, lmargin2=10)
    box.tag_configure("bullet",          font=(ff, sz),           foreground=TXT_NAVY,
                      lmargin1=24, lmargin2=36, spacing1=3,  spacing3=3)
    box.tag_configure("body",            font=(ff, sz),           foreground=TXT_NAVY,
                      lmargin1=10, lmargin2=10, spacing1=3,  spacing3=3)
    box.tag_configure("verdict_approve", font=(ff, sz, "bold"),   foreground=ACCENT_SUCCESS)
    box.tag_configure("verdict_cond",    font=(ff, sz, "bold"),   foreground=ACCENT_GOLD)
    box.tag_configure("verdict_decline", font=(ff, sz, "bold"),   foreground=ACCENT_RED)
    box.tag_configure("sym_ok",          font=(ff, sz),           foreground=ACCENT_SUCCESS)
    box.tag_configure("sym_warn",        font=(ff, sz),           foreground=ACCENT_GOLD)
    box.tag_configure("sym_bad",         font=(ff, sz),           foreground=ACCENT_RED)
    box.tag_configure("peso",            font=(ff, sz, "bold"),   foreground=LIME_DARK)
    box.tag_configure("risk_low",        font=(ff, sz, "bold"),   foreground=ACCENT_SUCCESS)
    box.tag_configure("risk_mod",        font=(ff, sz, "bold"),   foreground=ACCENT_GOLD)
    box.tag_configure("risk_high",       font=(ff, sz, "bold"),   foreground=ACCENT_RED)
    box.tag_configure("divider",         font=(ff, sz-2),         foreground=BORDER_MID)


# ─────────────────────────────────────────────────────────────────────
#  WRITE HELPERS
# ─────────────────────────────────────────────────────────────────────
def _write(self, txt, color=TXT_NAVY):
    box = self._textbox
    box.config(state="normal", fg=color)
    box.delete("1.0", "end")
    box.insert("end", txt)
    box.config(state="disabled")
    if self._search_var.get().strip() and self._current_tab == "extract":
        self._do_search()

def _write_analysis(self, txt, color=TXT_NAVY):
    box = self._analysis_box
    box.config(state="normal")
    box.delete("1.0", "end")

    if color != TXT_NAVY:
        box.insert("end", txt)
        box.config(state="disabled")
        return

    for line in txt.splitlines(keepends=True):
        s = line.rstrip("\n")
        if re.match(r'^#{1,4}\s+', s):
            clean = re.sub(r'^#{1,4}\s+', '', s)
            box.insert("end", clean + "\n", "sec_header")
        elif re.match(r'^\d{1,2}\.\s+[A-Z]', s):
            box.insert("end", "\n" + s + "\n", "sec_header")
        elif re.match(r'^[A-C]\)\s', s):
            box.insert("end", s + "\n", "sub_header")
        elif re.search(r'\bAPPROVE\b', s) and not re.search(r'CONDITIONALLY', s):
            self._insert_with_peso(box, s + "\n", "verdict_approve")
        elif re.search(r'CONDITIONALLY APPROVE', s):
            self._insert_with_peso(box, s + "\n", "verdict_cond")
        elif re.search(r'\bDECLINE\b', s):
            self._insert_with_peso(box, s + "\n", "verdict_decline")
        elif re.search(r'\b(Low Risk|LOW RISK|Low)\b', s) and "risk" in s.lower():
            self._insert_with_peso(box, s + "\n", "risk_low")
        elif re.search(r'\b(Moderate Risk|MODERATE|Moderate)\b', s) and "risk" in s.lower():
            self._insert_with_peso(box, s + "\n", "risk_mod")
        elif re.search(r'\b(High Risk|HIGH RISK|High)\b', s) and "risk" in s.lower():
            self._insert_with_peso(box, s + "\n", "risk_high")
        elif set(s.strip()).issubset({"─","—","-","=","_","*"}) and len(s.strip()) > 4:
            box.insert("end", s + "\n", "divider")
        elif s.strip().startswith(("•", "-", "*", "–")) or re.match(r'^\s+[•\-\*]', s):
            self._insert_with_peso(box, s + "\n", "bullet")
        elif "✅" in s:
            self._insert_sym_line(box, s + "\n", "sym_ok")
        elif "⚠" in s:
            self._insert_sym_line(box, s + "\n", "sym_warn")
        elif "❌" in s:
            self._insert_sym_line(box, s + "\n", "sym_bad")
        else:
            self._insert_with_peso(box, s + "\n", "body")

    box.config(state="disabled")
    if self._search_var.get().strip() and self._current_tab == "analysis":
        self._do_search()

def _insert_with_peso(self, box, text, base_tag):
    for part in re.split(r'(₱[\d,]+(?:\.\d+)?)', text):
        box.insert("end", part, "peso" if re.match(r'₱[\d,]+', part) else base_tag)

def _insert_sym_line(self, box, text, sym_tag):
    m = re.match(r'^(\s*[✅⚠❌]\s*)', text)
    if m:
        box.insert("end", m.group(1), sym_tag)
        self._insert_with_peso(box, text[m.end():], "body")
    else:
        self._insert_with_peso(box, text, "body")

def _put_placeholder(self):
    self._write(
        "Results will appear here after extraction.\n\n"
        "↑  Use the toolbar above to browse a file, then click  Extract Text  to begin.\n\n"
        "Engine:  PaddleOCR  →  Gemini 2.5 Flash VLM  →  Confidence Check",
        color=TXT_MUTED
    )
    self._write_analysis(
        "CIBI Analysis will appear here.\n\n"
        "Option A:  Extract a document, then click  Analyze CIBI.\n"
        "Option B:  After populating a CIBI Excel in CIBI Mode,\n"
        "           use  Analyze from Excel  to read cash-flow\n"
        "           and CIBI data directly from the workbook.\n\n"
        "The AI will assess:\n"
        "  • Cash-flow adequacy & DSR\n"
        "  • CIBI credit background\n"
        "  • Risk flags & final recommendation",
        color=TXT_MUTED
    )
    self._summary_placeholder()


# ─────────────────────────────────────────────────────────────────────
#  TAB SWITCHING
# ─────────────────────────────────────────────────────────────────────
_TAB_TITLES = {
    "dashboard":       "Dashboard",
    "cibi":            "CIBI Mode",
    "extract":         "Extracted Content",
    "analysis":        "CIBI Analysis",
    "summary":         "Summary",
    "lookup":          "Look-Up",
    "lookup_summary":  "LU Summary",
    "lu_analysis":     "LU Analysis",
    "logs":            "System Logs",
    "accounts":        "Accounts",
    "approvals": "Edit Approvals",
}

def _switch_tab(self, tab):
    prev_tab = getattr(self, "_current_tab", None)
    self._current_tab = tab

    if hasattr(self, '_nav_btns'):
        self._apply_nav_active(tab)

    if hasattr(self, '_page_title_lbl'):
        self._page_title_lbl.config(text=_TAB_TITLES.get(tab, tab.title()))

    self._loader_frame.pack_forget()
    self._dashboard_frame.pack_forget()
    self._txt_frame.pack_forget()
    self._analysis_frame.pack_forget()
    self._summary_frame.pack_forget()
    self._cibi_output_frame.pack_forget()
    self._lookup_frame.pack_forget()
    self._lookup_summary_frame.pack_forget()
    self._lu_analysis_frame.pack_forget()
    self._logs_frame.pack_forget()
    self._accounts_frame.pack_forget()
    self._approval_frame.pack_forget()

    if tab == "dashboard":
        self._refresh_dashboard_from_lu()
        self._dashboard_frame.pack(fill="both", expand=True)
    elif tab == "extract":
        self._txt_frame.pack(fill="both", expand=True)
    elif tab == "analysis":
        self._analysis_frame.pack(fill="both", expand=True)
    elif tab == "summary":
        self._summary_frame.pack(fill="both", expand=True)
    elif tab == "cibi":
        self._cibi_output_frame.pack(fill="both", expand=True)
    elif tab == "lookup":
        self._lookup_frame.pack(fill="both", expand=True)
    elif tab == "lookup_summary":
        self._lookup_summary_frame.pack(fill="both", expand=True)
        _refresh_summary(self)
    elif tab == "lu_analysis":
        self._lu_analysis_frame.pack(fill="both", expand=True)
    elif tab == "logs":                                       
        self._logs_frame.pack(fill="both", expand=True)
    elif tab == "accounts":                                    
        self._accounts_frame.pack(fill="both", expand=True)
    elif tab == "approvals":                               
        self._approval_frame.pack(fill="both", expand=True)
    else:
        # Default/fallback: return to CIBI Mode if an unknown tab key is requested.
        self._cibi_output_frame.pack(fill="both", expand=True)

    if self._search_var.get().strip() and tab in ("extract", "analysis"):
        self._do_search()



# ─────────────────────────────────────────────────────────────────────
#  LOADER
# ─────────────────────────────────────────────────────────────────────
def _show_loader(self, show, stage_text="Processing…"):
    if getattr(self, '_is_closing', False):
        return
    if show:
        self._dashboard_frame.pack_forget()
        self._txt_frame.pack_forget()
        self._analysis_frame.pack_forget()
        self._summary_frame.pack_forget()
        self._cibi_output_frame.pack_forget()
        self._lookup_frame.pack_forget()
        self._lookup_summary_frame.pack_forget()
        self._lu_analysis_frame.pack_forget()
        self._logs_frame.pack_forget()
        self._loader_frame.pack(fill="both", expand=True)
        self._stage_lbl.config(text=stage_text)
        self._spinner.start()
        self._status_lbl.config(text="●  Processing…", fg=ACCENT_GOLD)
        self._topbar_status.config(text="● Processing…", fg=ACCENT_GOLD, bg="#1A2F47")
        # Update sidebar status dot/label
        # Update sidebar status dot/label
        if hasattr(self, '_status_sidebar_lbl') and not getattr(self, '_is_closing', False):
            try:
                if self._status_sidebar_lbl.winfo_exists():
                    self._status_sidebar_lbl.config(text="Processing…", fg=ACCENT_GOLD)
            except Exception:
                pass
    else:
        self._spinner.stop()
        self._loader_frame.pack_forget()
        if self._current_tab == "extract":
            self._txt_frame.pack(fill="both", expand=True)
        elif self._current_tab == "dashboard":
            self._dashboard_frame.pack(fill="both", expand=True)
        elif self._current_tab == "analysis":
            self._analysis_frame.pack(fill="both", expand=True)
        elif self._current_tab == "summary":
            self._summary_frame.pack(fill="both", expand=True)
        elif self._current_tab == "cibi":
            self._cibi_output_frame.pack(fill="both", expand=True)
        elif self._current_tab == "lookup":
            self._lookup_frame.pack(fill="both", expand=True)
        elif self._current_tab == "lookup_summary":
            self._lookup_summary_frame.pack(fill="both", expand=True)
        elif self._current_tab == "lu_analysis":
            self._lu_analysis_frame.pack(fill="both", expand=True)
        elif self._current_tab == "logs":                      
            self._logs_frame.pack(fill="both", expand=True)
        elif self._current_tab == "accounts":                      
            self._accounts_frame.pack(fill="both", expand=True)
        elif self._current_tab == "approvals":                               
            self._approval_frame.pack(fill="both", expand=True)
        else:
            self._cibi_output_frame.pack(fill="both", expand=True)
        self._status_lbl.config(text="●  Ready", fg=LIME_DARK)
        self._topbar_status.config(text="● Ready", fg=_SB_ACCENT, bg="#1A2F47")
        if hasattr(self, '_status_sidebar_lbl') and not getattr(self, '_is_closing', False):
            try:
                if self._status_sidebar_lbl.winfo_exists():
                    _name = getattr(self, "_display_username", None) or "User"
                    self._status_sidebar_lbl.config(text=_name, fg=_SB_ACCENT2)
            except Exception:
                pass

def _set_progress(self, pct, stage=""):
    self._pct_lbl.config(text=f"{pct}%")
    if stage:
        self._stage_lbl.config(text=stage)
    self._prog_bar.set(pct / 100)


# ─────────────────────────────────────────────────────────────────────
#  GRADIENT / LAYOUT HELPERS
# ─────────────────────────────────────────────────────────────────────
def _hbar(self, canvas, c1, c2, steps=40):
    canvas.delete("all")
    w = canvas.winfo_width()
    h = canvas.winfo_height()
    if w < 2: return
    for i in range(steps):
        c = hex_blend(c1, c2, i / steps)
        canvas.create_rectangle(
            int(w*i/steps), 0, int(w*(i+1)/steps)+1, h,
            fill=c, outline=""
        )

def _vbar(self, canvas, c1, c2, steps=20):
    canvas.delete("all")
    h = canvas.winfo_height()
    if h < 2: return
    for i in range(steps):
        c = hex_blend(c1, c2, i / steps)
        canvas.create_rectangle(
            0, int(h*i/steps), 5, int(h*(i+1)/steps)+1,
            fill=c, outline=""
        )

def _vbar_full(self, canvas, c1, c2, steps=30):
    canvas.delete("all")
    h = canvas.winfo_height()
    w = canvas.winfo_width()
    if h < 2: return
    for i in range(steps):
        c = hex_blend(c1, c2, i / steps)
        canvas.create_rectangle(
            0, int(h*i/steps), w, int(h*(i+1)/steps)+1,
            fill=c, outline=""
        )

def _div(self, parent, pady=(14, 10)):
    tk.Frame(parent, bg=BORDER_LIGHT, height=1).pack(fill="x", pady=pady)

def _sec(self, parent, text, pady=(0, 6)):
    tk.Label(parent, text=text, font=F(8, "bold"),
             fg=NAVY_PALE, bg=PANEL_LEFT).pack(anchor="w", pady=pady)

def _sidebar_sec(self, parent, text, pady=(0, 6)):
    row = tk.Frame(parent, bg=_SB_BG)
    row.pack(fill="x", pady=pady)
    tk.Frame(row, bg=_SB_ACCENT, width=3, height=14).pack(side="left", padx=(0, 8))
    tk.Label(row, text=text, font=F(7, "bold"),
             fg=_SB_TXT, bg=_SB_BG).pack(side="left")

def _file_icon_for(self, name):
    ext = Path(name).suffix.lower()
    if ext == ".pdf":              return "📄"
    if ext in (".docx", ".doc"):   return "📝"
    if ext in (".xlsx", ".xls"):   return "📊"
    if ext in IMAGE_EXTS:          return "🖼"
    return "📃"


# ─────────────────────────────────────────────────────────────────────
#  SEARCH
# ─────────────────────────────────────────────────────────────────────
def _active_textbox(self):
    return self._textbox if self._current_tab == "extract" else self._analysis_box

def _do_search(self, *_):
    if self._current_tab not in ("extract", "analysis"):
        return
    query = self._search_var.get().strip()
    box   = self._active_textbox()
    box.tag_remove("search_match",   "1.0", "end")
    box.tag_remove("search_current", "1.0", "end")
    self._search_matches = []
    self._search_cursor  = -1
    if not query:
        self._match_lbl.config(text="", fg=TXT_SOFT)
        return
    start = "1.0"
    while True:
        pos = box.search(query, start, stopindex="end", nocase=True)
        if not pos: break
        end = f"{pos}+{len(query)}c"
        self._search_matches.append((pos, end))
        box.tag_add("search_match", pos, end)
        start = end
    count = len(self._search_matches)
    if count == 0:
        self._match_lbl.config(text="No results", fg=ACCENT_RED)
        return
    self._search_cursor = 0
    self._highlight_current()
    self._match_lbl.config(text=f"1 / {count}", fg=LIME_DARK)

def _highlight_current(self):
    if not self._search_matches: return
    box = self._active_textbox()
    box.tag_remove("search_current", "1.0", "end")
    pos, end = self._search_matches[self._search_cursor]
    box.tag_add("search_current", pos, end)
    box.see(pos)
    self._match_lbl.config(
        text=f"{self._search_cursor + 1} / {len(self._search_matches)}",
        fg=LIME_DARK
    )

def _search_next(self):
    if not self._search_matches: return
    self._search_cursor = (self._search_cursor + 1) % len(self._search_matches)
    self._highlight_current()

def _search_prev(self):
    if not self._search_matches: return
    self._search_cursor = (self._search_cursor - 1) % len(self._search_matches)
    self._highlight_current()

def _clear_search(self):
    self._search_var.set("")
    if self._current_tab in ("extract", "analysis"):
        box = self._active_textbox()
        box.tag_remove("search_match",   "1.0", "end")
        box.tag_remove("search_current", "1.0", "end")
    self._search_matches = []
    self._search_cursor  = -1
    self._match_lbl.config(text="", fg=TXT_SOFT)
    self._search_entry.focus_set()


# ─────────────────────────────────────────────────────────────────────
#  COPY
# ─────────────────────────────────────────────────────────────────────
def _copy(self):
    if self._current_tab == "dashboard":
        return
    if self._current_tab == "extract":
        content = self._textbox.get("1.0", "end").strip()
    else:
        content = self._analysis_box.get("1.0", "end").strip()
    skip = ("Results will appear here", "Loan analysis will appear here")
    if content and not any(s in content for s in skip):
        self.clipboard_clear()
        self.clipboard_append(content)
        self._copy_btn.configure(text="✓  Copied!")
        self.after(2200, lambda: self._copy_btn.configure(text="⎘  Copy"))

def _confirm_close(self):
    import tkinter.messagebox as mb
    confirmed = mb.askyesno(
        "Close System",
        "Are you sure you want to close the system?",
        icon="warning"
    )
    if not confirmed:
        return

    # ── Clear active session flag ──────────────────────────────────
    try:
        _conn = self.get_conn()
        if _conn:
            _cur = _conn.cursor()
            _cur.execute(
                "UPDATE public.users SET is_logged_in = FALSE WHERE id = %s",
                (getattr(self, '_current_user_id', None),)
            )
            _conn.commit()
            _cur.close()
    except Exception as ex:
        print(f"Close session clear error: {ex}")
    # ──────────────────────────────────────────────────────────────

    try:
        from admin_logs import insert_log
        insert_log(self, "CLOSED APP", f"User '{getattr(self, '_current_username', '')}' closed the system")
    except Exception:
        pass

    if hasattr(self, "_safe_close"):
        self._safe_close()
    else:
        self.destroy()


# ═════════════════════════════════════════════════════════════════════
#  ATTACH ALL METHODS TO DocExtractorApp
# ═════════════════════════════════════════════════════════════════════
def attach(cls):
    # Core UI panels
    cls._build_topbar            = _build_topbar
    cls._build_left              = _build_left
    cls._build_right             = _build_right

    # Sidebar nav helpers
    cls._apply_nav_active        = _apply_nav_active
    cls._build_nav_pill          = _build_nav_pill

    # Extract-tab toolbar
    cls._build_extract_toolbar   = _build_extract_toolbar

    # Text / analysis tag config
    cls._configure_analysis_tags = _configure_analysis_tags

    # Write helpers
    cls._write                   = _write
    cls._write_analysis          = _write_analysis
    cls._insert_with_peso        = _insert_with_peso
    cls._insert_sym_line         = _insert_sym_line
    cls._put_placeholder         = _put_placeholder

    # Tab switching & loader
    cls._switch_tab              = _switch_tab
    cls._show_loader             = _show_loader
    cls._set_progress            = _set_progress

    # Gradient / layout helpers
    cls._hbar                    = _hbar
    cls._vbar                    = _vbar
    cls._vbar_full               = _vbar_full
    cls._div                     = _div
    cls._sec                     = _sec
    cls._sidebar_sec             = _sidebar_sec
    cls._file_icon_for           = _file_icon_for

    # Search
    cls._active_textbox          = _active_textbox
    cls._do_search               = _do_search
    cls._highlight_current       = _highlight_current
    cls._search_next             = _search_next
    cls._search_prev             = _search_prev
    cls._clear_search            = _clear_search

    # Copy
    cls._copy                    = _copy
    # Close confirmation
    cls._confirm_close           = _confirm_close

    # External tab modules
    _attach_lookup(cls)
    _attach_summary(cls)
    _attach_lu_analysis(cls)
    _attach_dashboard(cls)
    _admin_logs_mod.attach(cls)
    _admin_account_mod.attach(cls)
    _approval_tab_mod.attach(cls)