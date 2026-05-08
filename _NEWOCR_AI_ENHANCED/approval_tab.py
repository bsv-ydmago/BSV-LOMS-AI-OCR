"""
approval_tab.py — DocExtract Pro (Banco San Vicente)
=====================================================
Approval tab — displays all rows from the `edit_requests` table in PostgreSQL.
Allows Super Admin to approve or reject pending edit requests via a popup dialog.

Only visible to users with role = 'super admin'.

Attach via:
    import approval_tab as _approval_tab_mod
    _approval_tab_mod.attach(DocExtractorApp)   # inside ui_panels.attach()
"""

import tkinter as tk
import customtkinter as ctk
from datetime import datetime

# ── Design tokens (mirrors existing app palette) ──────────────────────────────
_SB_BG         = "#0B1622"
_SB_ACCENT     = "#5BBF3E"
_SB_ACCENT2    = "#7DD65C"
_CARD_BG       = "#FFFFFF"

NAVY_DEEP      = "#0B1F3A"
NAVY_LIGHT     = "#1E3A5F"
NAVY_MID       = "#2E5C8A"
NAVY_MIST      = "#EAF0F8"
NAVY_GHOST     = "#D6E4F0"
TXT_NAVY       = "#1A2E42"
TXT_SOFT       = "#7A94B0"
TXT_MUTED      = "#A8BCCE"
WHITE          = "#FFFFFF"
OFF_WHITE      = "#F8FAFC"
ACCENT_RED     = "#D94040"
ACCENT_GOLD    = "#C89A2E"
ACCENT_SUCCESS = "#2E7D4F"
BORDER_LIGHT   = "#E2EAF4"
BORDER_MID     = "#C8D8EC"
LIME_DARK      = "#3D8F26"

# Status badge colours  {status_keyword: (bg, fg)}
_STATUS_COLORS = {
    "pending":  ("#FFF4E0", "#8A5A00"),
    "approved": ("#E3F5E8", "#1A6B35"),
    "rejected": ("#FFE8E8", "#8A1A1A"),
}
_STATUS_DEFAULT = ("#EDF1F7", "#3A4A5E")

_PAGE_SIZE = 20

# Column config: (key, header, pixel_width, anchor)
# pixel_width = 0 means "expand to fill remaining space"
_COLUMNS = [
    ("id",           "ID",           50,  "center"),
    ("requested_by", "Requested By", 160, "w"),
    ("record_type",  "Record Type",  120, "center"),
    ("record_id",    "Record ID",    80,  "center"),
    ("field_name",   "Field",        130, "w"),
    ("old_value",    "Old Value",    0,   "w"),
    ("new_value",    "New Value",    0,   "w"),
    ("status",       "Status",       90,  "center"),
    ("requested_at", "Requested At", 155, "center"),
    ("action",       "Action",       90,  "center"),
]


# ─────────────────────────────────────────────────────────────────────────────
#  PANEL BUILDER
# ─────────────────────────────────────────────────────────────────────────────

def _build_approval_panel(self, parent):
    BG = _CARD_BG
    frame = tk.Frame(parent, bg=BG)
    self._approval_frame = frame

    # ── Internal state ─────────────────────────────────────────────────
    self._approval_all_rows  = []
    self._approval_filtered  = []
    self._approval_page      = 0
    self._approval_sort_col  = "id"
    self._approval_sort_asc  = False   # newest first by default

    # ── TOP HEADER ────────────────────────────────────────────────────
    top = tk.Frame(frame, bg=BG)
    top.pack(fill="x", padx=28, pady=(20, 0))

    left_hdr = tk.Frame(top, bg=BG)
    left_hdr.pack(side="left", fill="y")

    tk.Frame(left_hdr, bg=_SB_ACCENT, width=4).pack(side="left", fill="y", padx=(0, 14))

    title_col = tk.Frame(left_hdr, bg=BG)
    title_col.pack(side="left")
    tk.Label(title_col, text="Edit Approvals",
             font=_F(self, 18, "bold"), fg=NAVY_DEEP, bg=BG).pack(anchor="w")
    tk.Label(title_col, text="Pending edit requests from users  •  Super Admin only",
             font=_F(self, 8), fg=TXT_SOFT, bg=BG).pack(anchor="w", pady=(1, 0))

    right_hdr = tk.Frame(top, bg=BG)
    right_hdr.pack(side="right", fill="y", pady=4)

    self._approval_count_lbl = tk.Label(
        right_hdr, text="— records",
        font=_F(self, 8, "bold"),
        fg=_SB_ACCENT2, bg="#0A1E0A",
        padx=14, pady=5
    )
    self._approval_count_lbl.pack(side="right", padx=(8, 0))

    ctk.CTkButton(
        right_hdr, text="↻  Refresh",
        command=lambda: _load_approvals(self),
        width=100, height=32, corner_radius=6,
        fg_color=NAVY_LIGHT, hover_color=NAVY_MID,
        text_color=WHITE, font=_F(self, 9, "bold"),
        border_width=0
    ).pack(side="right")

    ctk.CTkButton(
        right_hdr, text="✔✔  Approve All",
        command=lambda: _approve_all(self),
        width=130, height=32, corner_radius=6,
        fg_color=ACCENT_SUCCESS, hover_color=LIME_DARK,
        text_color=WHITE, font=_F(self, 9, "bold"),
        border_width=0
    ).pack(side="right", padx=(0, 8))

    # ── STATS CARDS ───────────────────────────────────────────────────
    stats_row = tk.Frame(frame, bg=BG)
    stats_row.pack(fill="x", padx=28, pady=(16, 0))

    self._approval_stat_lbls = {}
    _stats_cfg = [
        ("total",    "Total Requests", "📋", "#2E5C8A"),
        ("pending",  "Pending",        "⏳", "#8A5A00"),
        ("approved", "Approved",       "✅", "#3D8F26"),
        ("rejected", "Rejected",       "❌", "#8A1A1A"),
    ]
    for key, label, icon, accent_col in _stats_cfg:
        card = tk.Frame(stats_row, bg=NAVY_DEEP,
                        highlightbackground="#1E3A5F", highlightthickness=1)
        card.pack(side="left", fill="x", expand=True, padx=(0, 10))

        tk.Frame(card, bg=accent_col, height=3).pack(fill="x")

        inner = tk.Frame(card, bg=NAVY_DEEP)
        inner.pack(fill="x", padx=14, pady=10)

        tk.Label(inner, text=f"{icon}  {label}",
                 font=_F(self, 7), fg="#4A6E9A", bg=NAVY_DEEP).pack(anchor="w")

        val_lbl = tk.Label(inner, text="—",
                           font=_F(self, 16, "bold"), fg=WHITE, bg=NAVY_DEEP)
        val_lbl.pack(anchor="w")
        self._approval_stat_lbls[key] = val_lbl

    # ── FILTER BAR ────────────────────────────────────────────────────
    fbar = tk.Frame(frame, bg=BG)
    fbar.pack(fill="x", padx=28, pady=(16, 0))

    search_wrap = tk.Frame(fbar, bg=WHITE,
                           highlightbackground=BORDER_MID, highlightthickness=1)
    search_wrap.pack(side="left", fill="x", expand=True, padx=(0, 10))

    tk.Label(search_wrap, text="🔍", font=("Segoe UI Emoji", 10),
             bg=WHITE, fg=TXT_SOFT).pack(side="left", padx=(10, 4))

    self._approval_search_var = tk.StringVar()
    _PLACEHOLDER = "Search by requester, record type, field, value…"
    se = tk.Entry(search_wrap, textvariable=self._approval_search_var,
                  font=_F(self, 10), fg=TXT_MUTED, bg=WHITE,
                  relief="flat", bd=0, width=36, insertbackground=NAVY_MID)
    se.pack(side="left", fill="x", expand=True, pady=7)
    se.insert(0, _PLACEHOLDER)

    def _fi(e):
        if se.get() == _PLACEHOLDER:
            se.delete(0, "end")
            se.config(fg=TXT_NAVY)

    def _fo(e):
        if not se.get().strip():
            se.delete(0, "end")
            se.insert(0, _PLACEHOLDER)
            se.config(fg=TXT_MUTED)

    se.bind("<FocusIn>",  _fi)
    se.bind("<FocusOut>", _fo)
    self._approval_search_var.trace_add("write", lambda *a: _apply_filter(self))

    clr = tk.Label(search_wrap, text="✕", font=_F(self, 9, "bold"),
                   fg=ACCENT_RED, bg=WHITE, cursor="hand2", padx=10)
    clr.pack(side="right")

    def _clr_search():
        self._approval_search_var.set("")
        se.delete(0, "end")
        se.insert(0, _PLACEHOLDER)
        se.config(fg=TXT_MUTED)

    clr.bind("<Button-1>", lambda e: _clr_search())

    # Status filter dropdown
    self._approval_status_var = tk.StringVar(value="All Statuses")
    self._approval_status_menu = ctk.CTkOptionMenu(
        fbar,
        variable=self._approval_status_var,
        values=["All Statuses", "pending", "approved", "rejected"],
        command=lambda v: _apply_filter(self),
        width=150, height=34, corner_radius=6,
        fg_color=NAVY_DEEP, button_color=NAVY_LIGHT,
        button_hover_color=NAVY_MID,
        dropdown_fg_color=NAVY_DEEP,
        dropdown_hover_color="#162438",
        text_color=WHITE, dropdown_text_color=WHITE,
        font=_F(self, 9),
    )
    self._approval_status_menu.pack(side="left", padx=(0, 10))

    self._approval_page_info = tk.Label(fbar, text="",
                                        font=_F(self, 8), fg=TXT_MUTED, bg=BG)
    self._approval_page_info.pack(side="right")

    # ── TABLE ─────────────────────────────────────────────────────────
    tbl_wrap = tk.Frame(frame, bg=BORDER_LIGHT, padx=1, pady=1)
    tbl_wrap.pack(fill="both", expand=True, padx=28, pady=(12, 0))

    tbl_card = tk.Frame(tbl_wrap, bg=WHITE)
    tbl_card.pack(fill="both", expand=True)

    # Header — spacer is added inside _build_header_row (not here) because
    # that function destroys all children before rebuilding on every sort.
    _SCROLLBAR_W = 8   # must match vsb width below
    self._approval_scrollbar_w = _SCROLLBAR_W  # read by _build_header_row
    self._approval_hdr_row = tk.Frame(tbl_card, bg=NAVY_DEEP, height=40)
    self._approval_hdr_row.pack(fill="x")
    self._approval_hdr_row.pack_propagate(False)
    _build_header_row(self)

    # Scrollable body
    body_outer = tk.Frame(tbl_card, bg=WHITE)
    body_outer.pack(fill="both", expand=True)

    vsb = tk.Scrollbar(body_outer, orient="vertical", relief="flat",
                       troughcolor=OFF_WHITE, bg=BORDER_LIGHT,
                       width=_SCROLLBAR_W, bd=0)
    vsb.pack(side="right", fill="y")

    self._approval_canvas = tk.Canvas(body_outer, bg=WHITE,
                                      highlightthickness=0, yscrollcommand=vsb.set)
    self._approval_canvas.pack(side="left", fill="both", expand=True)
    vsb.config(command=self._approval_canvas.yview)

    self._approval_body = tk.Frame(self._approval_canvas, bg=WHITE)
    _cw = self._approval_canvas.create_window((0, 0), window=self._approval_body, anchor="nw")

    def _body_cfg(e):
        self._approval_canvas.configure(scrollregion=self._approval_canvas.bbox("all"))

    def _canvas_cfg(e):
        self._approval_canvas.itemconfig(_cw, width=e.width)

    self._approval_body.bind("<Configure>", _body_cfg)
    self._approval_canvas.bind("<Configure>", _canvas_cfg)

    def _mw(e):
        self._approval_canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")

    self._approval_canvas.bind("<MouseWheel>", _mw)
    self._approval_body.bind("<MouseWheel>", _mw)

    # ── PAGINATION FOOTER ─────────────────────────────────────────────
    footer = tk.Frame(frame, bg=BG)
    footer.pack(fill="x", padx=28, pady=(10, 16))

    self._approval_prev_btn = ctk.CTkButton(
        footer, text="◀  Prev",
        command=lambda: _page_approvals(self, -1),
        width=88, height=32, corner_radius=6,
        fg_color=NAVY_MIST, hover_color=NAVY_GHOST,
        text_color=NAVY_MID, font=_F(self, 9, "bold"),
        border_width=1, border_color=BORDER_MID
    )
    self._approval_prev_btn.pack(side="left", padx=(0, 6))

    self._approval_next_btn = ctk.CTkButton(
        footer, text="Next  ▶",
        command=lambda: _page_approvals(self, 1),
        width=88, height=32, corner_radius=6,
        fg_color=NAVY_MIST, hover_color=NAVY_GHOST,
        text_color=NAVY_MID, font=_F(self, 9, "bold"),
        border_width=1, border_color=BORDER_MID
    )
    self._approval_next_btn.pack(side="left")

    self._approval_status_lbl = tk.Label(
        footer, text="", font=_F(self, 8), fg=TXT_SOFT, bg=BG)
    self._approval_status_lbl.pack(side="left", padx=(14, 0))

    # Auto-load on first render
    self.after(500, lambda: _load_approvals(self))


# ─────────────────────────────────────────────────────────────────────────────
#  HEADER ROW  (rebuilt on every sort so the indicator updates)
# ─────────────────────────────────────────────────────────────────────────────

def _build_header_row(self):
    for w in self._approval_hdr_row.winfo_children():
        w.destroy()

    for col_key, col_label, col_w, _ in _COLUMNS:
        is_expand = (col_w == 0)
        is_action = (col_key == "action")

        cell = tk.Frame(self._approval_hdr_row, bg=NAVY_DEEP,
                        width=col_w if not is_expand else 1)
        cell.pack(side="left", fill="both", expand=is_expand)
        cell.pack_propagate(False)

        indicator = ""
        if not is_action and self._approval_sort_col == col_key:
            indicator = "  ▲" if self._approval_sort_asc else "  ▼"

        is_active = (self._approval_sort_col == col_key)
        lbl = tk.Label(
            cell,
            text=col_label + indicator,
            font=_F(self, 8, "bold"),
            fg=WHITE if is_active else "#A8C8E8",
            bg=NAVY_DEEP,
            anchor="center", cursor="hand2" if not is_action else "arrow",
            padx=8
        )
        lbl.pack(fill="both", expand=True)

        if not is_action:
            def _sort(e=None, k=col_key):
                _sort_approvals(self, k)
            lbl.bind("<Button-1>", _sort)
            cell.bind("<Button-1>", _sort)

            def _he(e, l=lbl): l.config(fg=WHITE)
            def _hl(e, l=lbl, k=col_key):
                l.config(fg=WHITE if self._approval_sort_col == k else "#A8C8E8")
            lbl.bind("<Enter>", _he)
            lbl.bind("<Leave>", _hl)

        tk.Frame(self._approval_hdr_row, bg="#1E3A5F", width=1).pack(
            side="left", fill="y", pady=8)

    # Right-side spacer equal to the scrollbar width so every header column
    # stays pixel-perfectly aligned with its body column beneath it.
    # This is placed at the END (after all side="left" columns) so it
    # occupies exactly the space the scrollbar takes in the body.
    _sb_w = getattr(self, "_approval_scrollbar_w", 8)
    tk.Frame(self._approval_hdr_row, bg=NAVY_DEEP,
             width=_sb_w).pack(side="right", fill="y")


# ─────────────────────────────────────────────────────────────────────────────
#  DATA LOADING
# ─────────────────────────────────────────────────────────────────────────────

def _load_approvals(self, preserve_page=False):
    _saved_page = self._approval_page if preserve_page else 0
    _set_status(self, "Loading…", ACCENT_GOLD)
    try:
        conn = self.get_conn()
        if conn is None:
            _set_status(self, "✘ No database connection", ACCENT_RED)
            return
        cur = conn.cursor()
        cur.execute(
        "SELECT id, requested_by, applicant_id, applicant_name, "
        "       col_name, old_value, new_value, reason, status, requested_at "
        "FROM edit_requests ORDER BY id DESC"
        )
        rows = cur.fetchall()
        cur.close()
    except Exception as e:
        _set_status(self, f"✘ {e}", ACCENT_RED)
        return

    self._approval_all_rows = []
    for r in rows:
        self._approval_all_rows.append({
            "id":           str(r[0]),
            "requested_by": str(r[1]) if r[1] is not None else "—",
            "record_type":  str(r[3]) if r[3] is not None else "—",
            "record_id":    str(r[2]) if r[2] is not None else "—",
            "field_name":   r[4] or "—",
            "old_value":    str(r[5]) if r[5] is not None else "—",
            "new_value":    str(r[6]) if r[6] is not None else "—",
            "reason":       str(r[7]) if r[7] is not None else "—",
            "status":       (r[8] or "pending").lower(),
            "requested_at": _fmt_time(r[9]),
        })

    total    = len(self._approval_all_rows)
    pending  = sum(1 for r in self._approval_all_rows if r["status"] == "pending")
    approved = sum(1 for r in self._approval_all_rows if r["status"] == "approved")
    rejected = sum(1 for r in self._approval_all_rows if r["status"] == "rejected")

    self._approval_stat_lbls["total"].config(text=f"{total:,}")
    self._approval_stat_lbls["pending"].config(text=f"{pending:,}")
    self._approval_stat_lbls["approved"].config(text=f"{approved:,}")
    self._approval_stat_lbls["rejected"].config(text=f"{rejected:,}")
    self._approval_count_lbl.config(text=f"{total:,} records")

    # Restore the saved page (clamped so it stays in valid range after data changes)
    total_pages = max(1, (len(self._approval_all_rows) + _PAGE_SIZE - 1) // _PAGE_SIZE)
    self._approval_page = min(_saved_page, total_pages - 1)
    _apply_filter(self, reset_page=False)
    _set_status(self, f"✔  Loaded {total:,} rows", ACCENT_SUCCESS)


def _fmt_time(val):
    if val is None:
        return "—"
    try:
        if isinstance(val, str):
            val = datetime.fromisoformat(val)
        return val.strftime("%Y-%m-%d  %H:%M:%S")
    except Exception:
        return str(val)


# ─────────────────────────────────────────────────────────────────────────────
#  FILTER & SORT
# ─────────────────────────────────────────────────────────────────────────────

def _apply_filter(self, reset_page=True):
    raw   = self._approval_search_var.get().strip().lower()
    query = "" if "search by" in raw else raw
    status_filter = self._approval_status_var.get()

    rows = self._approval_all_rows
    if status_filter and status_filter != "All Statuses":
        rows = [r for r in rows if r["status"].lower() == status_filter.lower()]
    if query:
        rows = [r for r in rows if any(query in str(v).lower() for v in r.values())]

    self._approval_filtered = list(rows)
    if reset_page:
        self._approval_page = 0
    _render_page(self)


def _sort_approvals(self, col_key):
    if self._approval_sort_col == col_key:
        self._approval_sort_asc = not self._approval_sort_asc
    else:
        self._approval_sort_col = col_key
        self._approval_sort_asc = True

    def _key(r):
        v = r.get(col_key, "")
        if col_key in ("id", "record_id"):
            try: return int(v)
            except: return 0
        return str(v).lower()

    self._approval_filtered.sort(key=_key, reverse=not self._approval_sort_asc)
    self._approval_page = 0
    _build_header_row(self)
    _render_page(self)


# ─────────────────────────────────────────────────────────────────────────────
#  PAGINATION
# ─────────────────────────────────────────────────────────────────────────────

def _page_approvals(self, direction):
    total_pages = max(1, (len(self._approval_filtered) + _PAGE_SIZE - 1) // _PAGE_SIZE)
    new_page = self._approval_page + direction
    if 0 <= new_page < total_pages:
        self._approval_page = new_page
        _render_page(self)


# ─────────────────────────────────────────────────────────────────────────────
#  TABLE RENDER
# ─────────────────────────────────────────────────────────────────────────────

def _render_page(self):
    for w in self._approval_body.winfo_children():
        w.destroy()

    rows        = self._approval_filtered
    total       = len(rows)
    total_pages = max(1, (total + _PAGE_SIZE - 1) // _PAGE_SIZE)
    start       = self._approval_page * _PAGE_SIZE
    end         = min(start + _PAGE_SIZE, total)
    page_rows   = rows[start:end]

    s = start + 1 if total else 0
    self._approval_page_info.config(
        text=f"Page {self._approval_page + 1} / {total_pages}  ·  "
             f"{s}–{end} of {total:,} rows"
    )
    self._approval_prev_btn.configure(
        state="normal" if self._approval_page > 0 else "disabled")
    self._approval_next_btn.configure(
        state="normal" if self._approval_page < total_pages - 1 else "disabled")

    if not page_rows:
        holder = tk.Frame(self._approval_body, bg=WHITE, height=160)
        holder.pack(fill="x")
        tk.Label(holder, text="No records match your filter",
                 font=_F(self, 11), fg=TXT_MUTED, bg=WHITE
                 ).place(relx=0.5, rely=0.5, anchor="center")
        self._approval_canvas.after(
            30, lambda: self._approval_canvas.configure(
                scrollregion=self._approval_canvas.bbox("all")))
        return

    for i, row in enumerate(page_rows):
        row_bg = WHITE if i % 2 == 0 else "#F6F9FF"

        rf = tk.Frame(self._approval_body, bg=row_bg, height=38)
        rf.pack(fill="x")
        rf.pack_propagate(False)

        hover_widgets = []   # (widget, normal_bg)

        for col_key, _, col_w, col_anchor in _COLUMNS:
            is_expand = (col_w == 0)
            is_action = (col_key == "action")

            cell = tk.Frame(rf, bg=row_bg, width=col_w if not is_expand else 1)
            cell.pack(side="left", fill="both", expand=is_expand)
            cell.pack_propagate(False)
            hover_widgets.append((cell, row_bg))

            if is_action:
                # ── Action button — only enabled for pending rows ───────
                is_pending = (row.get("status", "") == "pending")

                btn_frame = tk.Frame(cell, bg=row_bg)
                btn_frame.place(relx=0.5, rely=0.5, anchor="center")
                hover_widgets.append((btn_frame, row_bg))

                if is_pending:
                    act_btn = tk.Label(
                        btn_frame, text="Review",
                        font=_F(self, 8, "bold"),
                        fg=WHITE, bg=NAVY_LIGHT,
                        padx=10, pady=3,
                        cursor="hand2"
                    )
                    act_btn.pack()

                    def _on_enter_btn(e, b=act_btn):
                        b.config(bg=NAVY_MID)
                    def _on_leave_btn(e, b=act_btn):
                        b.config(bg=NAVY_LIGHT)

                    act_btn.bind("<Enter>", _on_enter_btn)
                    act_btn.bind("<Leave>", _on_leave_btn)
                    act_btn.bind(
                        "<Button-1>",
                        lambda e, r=row: _open_review_popup(self, r)
                    )
                    # NOTE: act_btn is intentionally NOT added to hover_widgets.
                    # Adding it caused the row-hover logic to overwrite the button's
                    # NAVY_LIGHT background with the row highlight colour on enter,
                    # and then restore it to row_bg (white) on leave — making the
                    # button appear to vanish. The button manages its own bg via
                    # _on_enter_btn / _on_leave_btn independently.
                else:
                    # Non-pending rows show a dim "—" instead
                    dash_lbl = tk.Label(
                        btn_frame, text="—",
                        font=_F(self, 9),
                        fg=TXT_MUTED, bg=row_bg
                    )
                    dash_lbl.pack()
                    hover_widgets.append((dash_lbl, row_bg))

            elif col_key == "status":
                bbg, bfg = _status_color(row.get("status", ""))
                badge_frame = tk.Frame(cell, bg=row_bg)
                badge_frame.place(relx=0.5, rely=0.5, anchor="center")
                tk.Label(badge_frame, text=row.get("status", "—").capitalize(),
                         font=_F(self, 8, "bold"),
                         fg=bfg, bg=bbg,
                         padx=9, pady=2).pack()
                hover_widgets.append((badge_frame, row_bg))

            else:
                val   = row.get(col_key, "")
                short = _trunc(val, col_w if not is_expand else 500)
                lbl = tk.Label(
                    cell, text=short,
                    font=_F(self, 9),
                    fg=NAVY_MID if col_key == "id" else TXT_NAVY,
                    bg=row_bg, anchor=col_anchor, padx=8
                )
                lbl.pack(fill="both", expand=True)
                hover_widgets.append((lbl, row_bg))

            # Column separator
            tk.Frame(rf, bg=BORDER_LIGHT, width=1).pack(
                side="left", fill="y", pady=6)

        # Bottom hairline
        tk.Frame(self._approval_body, bg=BORDER_LIGHT, height=1).pack(fill="x")

        # Hover highlight
        def _enter(e, rf=rf, hw=hover_widgets):
            rf.config(bg=NAVY_MIST)
            for w, _ in hw:
                try:
                    w.config(bg=NAVY_MIST)
                except Exception:
                    pass

        def _leave(e, rf=rf, hw=hover_widgets):
            rf.config(bg=hw[0][1])
            for w, orig in hw:
                try:
                    w.config(bg=orig)
                except Exception:
                    pass

        rf.bind("<Enter>", _enter)
        rf.bind("<Leave>", _leave)
        for w, _ in hover_widgets:
            w.bind("<Enter>", _enter)
            w.bind("<Leave>", _leave)

        # Propagate mouse-wheel from every child widget up to the canvas.
        # Tkinter doesn't bubble events automatically, so without this the
        # scroll only works when the cursor is over the canvas background —
        # not over any label, button or frame inside a row.
        def _row_scroll(e, cvs=self._approval_canvas):
            cvs.yview_scroll(int(-1 * (e.delta / 120)), "units")

        rf.bind("<MouseWheel>", _row_scroll)
        for w, _ in hover_widgets:
            try:
                w.bind("<MouseWheel>", _row_scroll)
            except Exception:
                pass

    self._approval_canvas.yview_moveto(0)
    self._approval_canvas.after(
        30, lambda: self._approval_canvas.configure(
            scrollregion=self._approval_canvas.bbox("all")))


# ─────────────────────────────────────────────────────────────────────────────
#  REVIEW POPUP
# ─────────────────────────────────────────────────────────────────────────────

def _open_review_popup(self, row: dict):
    """Open a modal dialog showing the edit request details with Approve / Reject."""

    popup = tk.Toplevel(self)
    popup.title("Review Edit Request")
    popup.configure(bg="#F4F6F8")
    popup.resizable(False, True)
    popup.grab_set()

    PW, PH = 800, 640
    self.update_idletasks()
    rx = self.winfo_rootx() + (self.winfo_width()  - PW) // 2
    ry = self.winfo_rooty() + (self.winfo_height() - PH) // 2
    popup.geometry(f"{PW}x{PH}+{rx}+{ry}")

    # ── Scrollable main area ──────────────────────────────────────────
    root_frame = tk.Frame(popup, bg="#F4F6F8",
                  highlightbackground="#5BBF3E",
                  highlightthickness=2)
    root_frame.pack(fill="both", expand=True)

    scroll_area = tk.Frame(root_frame, bg="#F4F6F8")
    scroll_area.pack(fill="both", expand=True)
    popup_vsb = tk.Scrollbar(scroll_area, orient="vertical", relief="flat",
                             troughcolor="#E2EAF4", bg="#C8D8EC", width=8, bd=0)
    popup_vsb.pack(side="right", fill="y")
    main_canvas = tk.Canvas(scroll_area, bg="#F4F6F8", highlightthickness=0,
                            yscrollcommand=popup_vsb.set)
    main_canvas.pack(side="left", fill="both", expand=True)
    popup_vsb.config(command=main_canvas.yview)

    scroll_frame = tk.Frame(main_canvas, bg="#F4F6F8")
    _sc_win = main_canvas.create_window((0, 0), window=scroll_frame, anchor="nw")

    def _on_frame_configure(e):
        main_canvas.configure(scrollregion=main_canvas.bbox("all"))
    def _on_canvas_configure(e):
        main_canvas.itemconfig(_sc_win, width=e.width)

    scroll_frame.bind("<Configure>", _on_frame_configure)
    main_canvas.bind("<Configure>", _on_canvas_configure)

    def _popup_scroll(e):
        main_canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
    main_canvas.bind("<MouseWheel>", _popup_scroll)
    scroll_frame.bind("<MouseWheel>", _popup_scroll)
    popup.bind("<MouseWheel>", _popup_scroll)

    # ── Header strip ──────────────────────────────────────────────────
    hdr = tk.Frame(scroll_frame, bg="#F4F6F8")
    hdr.pack(fill="x", padx=16, pady=(18, 4))

    sb_hdr = tk.Frame(hdr, bg="#F4F6F8")
    sb_hdr.pack(fill="x")
    tk.Label(sb_hdr, text="⚙", font=("Segoe UI Emoji", 16),
            fg="#5BBF3E", bg="#F4F6F8").pack(side="left", padx=(0, 8))

    sb_tc = tk.Frame(sb_hdr, bg="#F4F6F8")
    sb_tc.pack(side="left")
    tk.Label(sb_tc, text="REVIEW",
            font=("Segoe UI", 8, "bold"), fg="#7A94B0",
            bg="#F4F6F8", anchor="w").pack(anchor="w")
    tk.Label(sb_tc, text=f"Edit Request  #{ row.get('id','—') }",
            font=("Segoe UI", 11, "bold"), fg="#0B1F3A",
            bg="#F4F6F8", anchor="w").pack(anchor="w")

    tk.Label(hdr,
        text=f"Submitted {row.get('requested_at','—')}",
        font=("Segoe UI", 8), fg="#7A94B0", bg="#F4F6F8",
        justify="left", anchor="w").pack(anchor="w", pady=(4, 0))

    tk.Frame(scroll_frame, bg="#C8D8EC", height=1).pack(fill="x", padx=12, pady=(0, 6))

    # Status badge in header
    bbg, bfg = _status_color(row.get("status", ""))
    status_pill = tk.Frame(scroll_frame, bg="#F4F6F8")
    status_pill.pack(anchor="w", padx=20, pady=(0, 8))
    tk.Label(status_pill, text=row.get("status","—").capitalize(),
            font=("Segoe UI", 8, "bold"), fg=bfg, bg=bbg,
            padx=10, pady=3).pack()

    # ── Section: Request Info ─────────────────────────────────────────
    def _section_label(parent, text):
        sec = tk.Frame(parent, bg="#F4F6F8")
        sec.pack(fill="x", padx=20, pady=(16, 6))
        tk.Label(sec, text=text, font=("Segoe UI", 7, "bold"),
                fg="#2E5C8A", bg="#F4F6F8").pack(side="left")
        tk.Frame(sec, bg="#C8D8EC", height=1).pack(
            side="left", fill="x", expand=True, padx=(10, 0), pady=1)

    _section_label(scroll_frame, "REQUEST DETAILS")

    info_card = tk.Frame(scroll_frame, bg=WHITE,
                 highlightbackground="#5BBF3E", highlightthickness=1)
    info_card.pack(fill="x", padx=20)

    _info = [
        ("👤 Requested By", row.get("requested_by", "—")),
        ("🏷️ Applicant",   row.get("record_type",  "—")),
        ("🔢 Applicant ID", row.get("record_id",    "—")),
        ("📋 Field",        row.get("field_name",   "—")),
        ("💬 Reason",       row.get("reason",       "—")),
    ]

    for idx, (label, value) in enumerate(_info):
        row_bg = WHITE if idx % 2 == 0 else "#F0F6FF"
        rf = tk.Frame(info_card, bg=row_bg)
        rf.pack(fill="x")
        if idx > 0:
            tk.Frame(info_card, bg="#E2EAF4", height=1).pack(fill="x")

        # Green left accent bar like Image 2
        tk.Frame(rf, bg="#5BBF3E", width=3).pack(side="left", fill="y")

        tk.Label(rf, text=label, font=_F(self, 8, "bold"),
                fg="#2E5C8A", bg=row_bg,
                width=16, anchor="w", padx=8, pady=8).pack(side="left")
        tk.Label(rf, text=str(value), font=_F(self, 9),
                fg="#0B1F3A", bg=row_bg, anchor="w",
                wraplength=340, justify="left").pack(
                    side="left", fill="x", expand=True, padx=(0, 14))

    # ── Section: Value Comparison ─────────────────────────────────────
    _section_label(scroll_frame, "VALUE COMPARISON")

    cmp_row = tk.Frame(scroll_frame, bg="#F4F6F8")
    cmp_row.pack(fill="x", padx=20, pady=(0, 4))

    for side_label, val_key, accent, card_bg, txt_col in [
        ("OLD VALUE", "old_value", "#C0392B", "#1A0A0A", "#FF9999"),
        ("NEW VALUE", "new_value", "#27AE60", "#0A1A0D", "#88EEA8"),
    ]:
        col = tk.Frame(cmp_row, bg="#F4F6F8")
        col.pack(side="left", fill="both", expand=True, padx=(0, 8))

        top_bar = tk.Frame(col, bg=accent, height=3)
        top_bar.pack(fill="x")

        lbl_row = tk.Frame(col, bg=card_bg)
        lbl_row.pack(fill="x")
        tk.Label(lbl_row, text=side_label,
                 font=_F(self, 7, "bold"), fg=accent,
                 bg=card_bg, anchor="w",
                 padx=12, pady=6).pack(fill="x")

        tk.Frame(col, bg=accent, height=1).pack(fill="x")

        val_box = tk.Frame(col, bg=card_bg,
                           highlightbackground=accent, highlightthickness=1)
        val_box.pack(fill="x")
        display_val = row.get(val_key, "—")
        if val_key == "new_value" and display_val == "__DROP_COLUMN__":
            display_val = "⚠  DROP COLUMN (permanent schema change)"
        tk.Label(val_box, text=display_val,
                 font=_F(self, 10, "bold"), fg=txt_col, bg=card_bg,
                 wraplength=230, justify="left",
                 padx=12, pady=12, anchor="w").pack(fill="x")

    # ── Rejection reason (always created, shown/hidden via pack) ──────
    reason_frame = tk.Frame(scroll_frame, bg="#F4F6F8")
    reason_var   = tk.StringVar()
    reason_widgets_built = [False]

    def _show_reason_field():
        if reason_widgets_built[0]:
            reason_frame.pack(fill="x", padx=20, pady=(14, 0))
            return
        reason_widgets_built[0] = True
        reason_frame.pack(fill="x", padx=20, pady=(14, 0))

        _section_label(reason_frame, "REJECTION REASON")

        wrap = tk.Frame(reason_frame, bg="#0F2030",
                        highlightbackground=ACCENT_RED, highlightthickness=1)
        wrap.pack(fill="x")

        inner = tk.Frame(wrap, bg="#0F2030")
        inner.pack(fill="x", padx=10, pady=8)

        tk.Label(inner, text="📝", font=("Segoe UI Emoji", 10),
                 bg="#0F2030", fg=TXT_SOFT).pack(side="left", padx=(0, 6))

        entry = tk.Entry(inner, textvariable=reason_var,
                         font=_F(self, 10), fg=WHITE, bg="#0F2030",
                         relief="flat", bd=0,
                         insertbackground=WHITE,
                         highlightthickness=0)
        entry.pack(side="left", fill="x", expand=True, ipady=4)
        entry.focus_set()

        tk.Label(reason_frame,
            text="Optional — leave blank to reject without a reason",
            font=_F(self, 7), fg=TXT_SOFT, bg="#F4F6F8").pack(
                     anchor="w", pady=(4, 0))

        # Force scroll area to update
        scroll_frame.update_idletasks()
        main_canvas.configure(scrollregion=main_canvas.bbox("all"))
        main_canvas.yview_moveto(1.0)

    # ── Buttons (fixed at bottom, outside scroll) ─────────────────────
    tk.Frame(root_frame, bg="#C8D8EC", height=1).pack(fill="x", side="bottom")
    btn_outer = tk.Frame(root_frame, bg="#F4F6F8")
    btn_outer.pack(fill="x", side="bottom")

    btn_row = tk.Frame(btn_outer, bg="#F4F6F8")
    btn_row.pack(fill="x", padx=20, pady=12)

    # Keep references so we can swap them
    approve_btn_ref = [None]
    reject_btn_ref  = [None]
    confirm_btn_ref = [None]

    def _do_approve():
        _process_request(self, row, "approved", reason="", popup=popup)

    def _show_reject():
        _show_reason_field()
        # Hide Approve & Reject, show Confirm Reject + Cancel
        if approve_btn_ref[0]:
            approve_btn_ref[0].pack_forget()
        if reject_btn_ref[0]:
            reject_btn_ref[0].pack_forget()

        confirm_btn = ctk.CTkButton(
            btn_row, text="✕  Confirm Reject",
            command=lambda: _process_request(
                self, row, "rejected",
                reason=reason_var.get().strip(),
                popup=popup),
            height=36, corner_radius=7,
            fg_color=ACCENT_RED, hover_color="#B03030",
            text_color=WHITE, font=_F(self, 10, "bold"),
            border_width=0
        )
        confirm_btn.pack(side="left", padx=(0, 8))
        confirm_btn_ref[0] = confirm_btn

        back_btn = ctk.CTkButton(
            btn_row, text="← Back",
            command=lambda: _cancel_reject(),
            height=36, corner_radius=7,
            fg_color="#DDE6F0", hover_color="#C8D8EC",
            text_color="#1A2E42", font=_F(self, 9),
            border_width=1, border_color="#B0C4D8"
        )
        back_btn.pack(side="left")

    def _cancel_reject():
        # Hide reason frame and restore original buttons
        reason_frame.pack_forget()
        if confirm_btn_ref[0]:
            confirm_btn_ref[0].destroy()
            confirm_btn_ref[0] = None
        # Remove the Back button (last packed)
        for w in btn_row.winfo_children():
            w.destroy()
        _rebuild_buttons()

    def _rebuild_buttons():
        # Cancel on far left; Reject + Approve grouped on far right
        ctk.CTkButton(
            btn_row, text="Cancel",
            command=popup.destroy,
            height=36, corner_radius=7,
            fg_color="#DDE6F0", hover_color="#C8D8EC",
            text_color="#1A2E42", font=_F(self, 9),
            border_width=1, border_color="#B0C4D8"
        ).pack(side="left")

        # Pack right-side buttons in reverse order (last packed = far right)
        ab = ctk.CTkButton(
            btn_row, text="✔  Approve",
            command=_do_approve,
            height=36, corner_radius=7,
            fg_color=ACCENT_SUCCESS, hover_color="#236B3E",
            text_color=WHITE, font=_F(self, 10, "bold"),
            border_width=0
        )
        ab.pack(side="right")
        approve_btn_ref[0] = ab

        rb = ctk.CTkButton(
            btn_row, text="✕  Reject",
            command=_show_reject,
            height=36, corner_radius=7,
            fg_color=ACCENT_RED, hover_color="#B03030",
            text_color=WHITE, font=_F(self, 10, "bold"),
            border_width=0
        )
        rb.pack(side="right", padx=(0, 8))
        reject_btn_ref[0] = rb

    _rebuild_buttons()


# ─────────────────────────────────────────────────────────────────────────────
#  APPROVE ALL
# ─────────────────────────────────────────────────────────────────────────────

def _approve_all(self):
    """Two-step confirmation dialog then bulk-approve all pending edit requests."""

    pending_rows = [r for r in self._approval_all_rows if r.get("status") == "pending"]
    pending_count = len(pending_rows)

    if pending_count == 0:
        _set_status(self, "✘ No pending requests to approve", ACCENT_RED)
        return

    # ── Step 1 dialog: Ask ────────────────────────────────────────────────────
    dlg = tk.Toplevel(self)
    dlg.title("Approve All")
    dlg.configure(bg="#F4F6F8")
    dlg.resizable(False, False)
    dlg.grab_set()

    DW, DH = 460, 240
    self.update_idletasks()
    rx = self.winfo_rootx() + (self.winfo_width()  - DW) // 2
    ry = self.winfo_rooty() + (self.winfo_height() - DH) // 2
    dlg.geometry(f"{DW}x{DH}+{rx}+{ry}")

    root_f = tk.Frame(dlg, bg="#F4F6F8",
                      highlightbackground=_SB_ACCENT, highlightthickness=2)
    root_f.pack(fill="both", expand=True)

    # Icon + title
    top_strip = tk.Frame(root_f, bg=ACCENT_SUCCESS, height=4)
    top_strip.pack(fill="x")

    body_f = tk.Frame(root_f, bg="#F4F6F8")
    body_f.pack(fill="both", expand=True, padx=28, pady=20)

    icon_row = tk.Frame(body_f, bg="#F4F6F8")
    icon_row.pack(anchor="w")
    tk.Label(icon_row, text="✔✔", font=("Segoe UI Emoji", 18),
             fg=ACCENT_SUCCESS, bg="#F4F6F8").pack(side="left", padx=(0, 10))
    title_col = tk.Frame(icon_row, bg="#F4F6F8")
    title_col.pack(side="left")
    tk.Label(title_col, text="Approve All Pending Requests",
             font=_F(self, 12, "bold"), fg=NAVY_DEEP, bg="#F4F6F8").pack(anchor="w")
    tk.Label(title_col,
             text=f"This will approve {pending_count:,} pending edit request{'s' if pending_count != 1 else ''}.",
             font=_F(self, 9), fg=TXT_SOFT, bg="#F4F6F8").pack(anchor="w", pady=(2, 0))

    tk.Label(body_f,
             text="All pending edits will be applied to the database.\nDo you want to continue?",
             font=_F(self, 9), fg=TXT_NAVY, bg="#F4F6F8",
             justify="left").pack(anchor="w", pady=(14, 0))

    # Buttons
    tk.Frame(root_f, bg=BORDER_MID, height=1).pack(fill="x", side="bottom")
    btn_f = tk.Frame(root_f, bg="#F4F6F8")
    btn_f.pack(side="bottom", fill="x", padx=20, pady=12)

    def _go_to_confirm():
        dlg.destroy()
        _approve_all_confirm(self, pending_rows, pending_count)

    ctk.CTkButton(
        btn_f, text="Cancel",
        command=dlg.destroy,
        height=36, corner_radius=7,
        fg_color="#DDE6F0", hover_color="#C8D8EC",
        text_color="#1A2E42", font=_F(self, 9),
        border_width=1, border_color="#B0C4D8"
    ).pack(side="left")

    ctk.CTkButton(
        btn_f, text="Yes, Continue →",
        command=_go_to_confirm,
        height=36, corner_radius=7,
        fg_color=NAVY_LIGHT, hover_color=NAVY_MID,
        text_color=WHITE, font=_F(self, 10, "bold"),
        border_width=0
    ).pack(side="right")


def _approve_all_confirm(self, pending_rows: list, pending_count: int):
    """Step 2 — final confirmation before bulk approval."""

    dlg2 = tk.Toplevel(self)
    dlg2.title("Confirm Approve All")
    dlg2.configure(bg="#F4F6F8")
    dlg2.resizable(False, False)
    dlg2.grab_set()

    DW, DH = 460, 260
    self.update_idletasks()
    rx = self.winfo_rootx() + (self.winfo_width()  - DW) // 2
    ry = self.winfo_rooty() + (self.winfo_height() - DH) // 2
    dlg2.geometry(f"{DW}x{DH}+{rx}+{ry}")

    root_f = tk.Frame(dlg2, bg="#F4F6F8",
                      highlightbackground=ACCENT_RED, highlightthickness=2)
    root_f.pack(fill="both", expand=True)

    top_strip = tk.Frame(root_f, bg=ACCENT_RED, height=4)
    top_strip.pack(fill="x")

    body_f = tk.Frame(root_f, bg="#F4F6F8")
    body_f.pack(fill="both", expand=True, padx=28, pady=20)

    icon_row = tk.Frame(body_f, bg="#F4F6F8")
    icon_row.pack(anchor="w")
    tk.Label(icon_row, text="⚠️", font=("Segoe UI Emoji", 18),
             bg="#F4F6F8").pack(side="left", padx=(0, 10))
    title_col = tk.Frame(icon_row, bg="#F4F6F8")
    title_col.pack(side="left")
    tk.Label(title_col, text="Final Confirmation",
             font=_F(self, 12, "bold"), fg=ACCENT_RED, bg="#F4F6F8").pack(anchor="w")
    tk.Label(title_col,
             text=f"You are about to approve {pending_count:,} request{'s' if pending_count != 1 else ''}.",
             font=_F(self, 9), fg=TXT_SOFT, bg="#F4F6F8").pack(anchor="w", pady=(2, 0))

    tk.Label(body_f,
             text="This action cannot be undone. All pending edits will be\n"
                  "permanently written to the applicants table.",
             font=_F(self, 9), fg=TXT_NAVY, bg="#F4F6F8",
             justify="left").pack(anchor="w", pady=(14, 0))

    # Buttons
    tk.Frame(root_f, bg=BORDER_MID, height=1).pack(fill="x", side="bottom")
    btn_f = tk.Frame(root_f, bg="#F4F6F8")
    btn_f.pack(side="bottom", fill="x", padx=20, pady=12)

    ctk.CTkButton(
        btn_f, text="← Cancel",
        command=dlg2.destroy,
        height=36, corner_radius=7,
        fg_color="#DDE6F0", hover_color="#C8D8EC",
        text_color="#1A2E42", font=_F(self, 9),
        border_width=1, border_color="#B0C4D8"
    ).pack(side="left")

    ctk.CTkButton(
        btn_f, text="✔  Confirm Approve All",
        command=lambda: _run_approve_all(self, pending_rows, dlg2),
        height=36, corner_radius=7,
        fg_color=ACCENT_SUCCESS, hover_color=LIME_DARK,
        text_color=WHITE, font=_F(self, 10, "bold"),
        border_width=0
    ).pack(side="right")


def _run_approve_all(self, pending_rows: list, dlg: tk.Toplevel):
    """Execute the bulk approval — iterates every pending row and applies the edit."""
    try:
        conn = self.get_conn()
        if conn is None:
            _set_status(self, "✘ No database connection", ACCENT_RED)
            dlg.destroy()
            return

        cur = conn.cursor()
        success_ids = []
        failed = []

        for row in pending_rows:
            try:
                _apply_edit(cur, row)
                cur.execute(
                    "UPDATE edit_requests "
                    "SET status = %s, reviewed_by = %s, reviewed_at = NOW(), rejection_reason = NULL "
                    "WHERE id = %s",
                    ("approved", getattr(self, "_current_user_id", None), int(row["id"]))
                )
                success_ids.append(row["id"])
            except Exception as row_err:
                conn.rollback()
                failed.append((row["id"], str(row_err)))

        conn.commit()
        cur.close()

    except Exception as e:
        _set_status(self, f"✘ DB error: {e}", ACCENT_RED)
        dlg.destroy()
        return

    # Log
    try:
        from admin_logs import insert_log
        insert_log(
            self,
            "EDIT APPROVE ALL",
            f"Bulk approved {len(success_ids)} request(s). "
            + (f"Failed: {len(failed)}" if failed else "All succeeded.")
        )
    except Exception:
        pass

    dlg.destroy()

    if failed:
        _set_status(self,
                    f"✔  {len(success_ids)} approved  |  ✘ {len(failed)} failed",
                    ACCENT_GOLD)
    else:
        _set_status(self,
                    f"✔  All {len(success_ids)} request{'s' if len(success_ids) != 1 else ''} approved",
                    ACCENT_SUCCESS)

    _load_approvals(self, preserve_page=True)


# ─────────────────────────────────────────────────────────────────────────────
#  APPROVE / REJECT PROCESSING
# ─────────────────────────────────────────────────────────────────────────────

def _process_request(self, row: dict, decision: str, reason: str, popup: tk.Toplevel):
    """Update the edit_requests table with the admin decision."""
    try:
        conn = self.get_conn()
        if conn is None:
            _set_status(self, "✘ No database connection", ACCENT_RED)
            return

        cur = conn.cursor()

        # If approved, apply the actual change to the target table
        if decision == "approved":
            try:
                _apply_edit(cur, row)
            except Exception as apply_err:
                conn.rollback()
                cur.close()
                import tkinter.messagebox as mb
                mb.showerror(
                    "Apply Failed",
                    f"Could not apply the edit to the target record:\n\n{apply_err}",
                    parent=popup
                )
                return

        # Update the edit_requests row status
        cur.execute(
            "UPDATE edit_requests "
            "SET status = %s, reviewed_by = %s, reviewed_at = NOW(), rejection_reason = %s "
            "WHERE id = %s",
            (
                decision,
                getattr(self, "_current_user_id", None),
                reason if decision == "rejected" else None,
                int(row["id"])
            )
        )
        conn.commit()
        cur.close()

    except Exception as e:
        _set_status(self, f"✘ DB error: {e}", ACCENT_RED)
        return

    # Log the action
    try:
        from admin_logs import insert_log
        insert_log(
            self,
            f"EDIT {decision.upper()}",
            f"Request ID {row['id']} | Field: {row.get('field_name', '—')} | "
            f"Record: {row.get('record_type', '—')} #{row.get('record_id', '—')}"
        )
    except Exception:
        pass

    popup.destroy()

    action_word = "approved" if decision == "approved" else "rejected"
    _set_status(self, f"✔  Request {row['id']} {action_word}", ACCENT_SUCCESS)

    # Refresh table — stay on the same page the admin was viewing
    _load_approvals(self, preserve_page=True)


def _apply_edit(cur, row: dict):
    """
    Apply the approved edit to the applicants table.
    Handles both regular cell edits and column deletion requests.
    """
    field_name = (row.get("field_name") or "").strip()
    new_value  = row.get("new_value", "")

    # ── Column deletion request ────────────────────────────────────────
    if new_value == "__DROP_COLUMN__":
        # Validate col name is safe (only a-z, 0-9, underscore)
        import re as _re
        if not field_name or not _re.match(r'^[a-z0-9_]+$', field_name):
            raise ValueError(f"Unsafe column name for DROP: '{field_name}'")
        # Check the column actually exists before trying to drop it
        cur.execute("""
            SELECT 1 FROM information_schema.columns
            WHERE table_name='applicants' AND column_name=%s
        """, (field_name,))
        if not cur.fetchone():
            raise ValueError(
                f"Column '{field_name}' does not exist in applicants table.")
        cur.execute(f"ALTER TABLE applicants DROP COLUMN {field_name}")
        return

    # ── Regular cell edit ──────────────────────────────────────────────
    if not field_name or not field_name.replace("_", "").isalnum():
        raise ValueError(f"Invalid field name: '{field_name}'")

    applicant_id = row.get("record_id")
    if not applicant_id or applicant_id == "—":
        raise ValueError("Missing applicant_id — cannot apply edit.")

    # ── Virtual columns: write into results_json, not a real column ───
    from summary_tab import _VIRTUAL_TO_JSON, _db_update_virtual_cell
    if field_name in _VIRTUAL_TO_JSON:
        _db_update_virtual_cell(int(applicant_id), field_name, new_value)
        return

    sql = f'UPDATE applicants SET "{field_name}" = %s WHERE id = %s'
    cur.execute(sql, (new_value, int(applicant_id)))


# ─────────────────────────────────────────────────────────────────────────────
#  SMALL HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _status_color(status: str):
    key = (status or "").lower().strip()
    return _STATUS_COLORS.get(key, _STATUS_DEFAULT)


def _trunc(text: str, pixel_width: int, ratio: float = 6.5) -> str:
    if pixel_width <= 0:
        return text
    max_c = max(4, int(pixel_width / ratio) - 2)
    return (text[:max_c - 1] + "…") if len(text) > max_c else text


def _set_status(self, msg: str, color: str = TXT_SOFT):
    try:
        if self._approval_status_lbl.winfo_exists():
            self._approval_status_lbl.config(text=msg, fg=color)
    except Exception:
        pass


def _F(self, size: int, weight: str = "normal") -> tuple:
    """Return a scaled font tuple, delegates to self.F() when available."""
    try:
        return self.F(size, weight)
    except Exception:
        zoom = getattr(self, "_ui_zoom", 1.0)
        return ("Segoe UI", max(6, int(round(size * zoom))), weight)


# ─────────────────────────────────────────────────────────────────────────────
#  ATTACH
# ─────────────────────────────────────────────────────────────────────────────

def attach(cls):
    """Called by ui_panels.attach() — injects _build_approval_panel into the app class."""
    cls._build_approval_panel = _build_approval_panel