"""
admin_account.py — DocExtract Pro
===================================
Accounts management tab (super admin only).

Features
--------
• Live search / filter (resets to page 1)
• Clickable column headers → ascending / descending sort with ▲ / ▼ arrows
• Rows fill the full table height (no blank gap at bottom)
• Role / Status pill badges
• Working Edit dialog  → updates role + status in DB
• Working Delete dialog → removes user from DB after confirmation
• Add User dialog → inserts new user (bcrypt password)
  - Only accepts @bsv.ph or @bancosanvicente.com email addresses
  - Sends a 6-digit verification code to the email before saving to DB
• Pagination 20 rows / page  (Prev · Next · Loaded N rows)
"""

import os
import random
import smtplib
import tkinter as tk
import customtkinter as ctk
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from tkinter import messagebox
from datetime import datetime

from dotenv import load_dotenv
load_dotenv()

# ── Design tokens ──────────────────────────────────────────────────────────────
_PAGE_BG        = "#F4F6FA"
_SB_BG          = "#0B1622"
_SB_ACCENT      = "#5BBF3E"
_NAVY_MID       = "#1E3A5F"
_NAVY_LIGHT     = "#2D5F8A"
_NAVY_MIST      = "#EBF0F7"
_NAVY_GHOST     = "#D6E4F0"
_BORDER_MID     = "#C8D8E8"
_BORDER_LIGHT   = "#E8ECF2"
_TXT_NAVY       = "#1A2F47"
_TXT_SOFT       = "#4A6480"
_TXT_MUTED      = "#8A9BB0"
_ACCENT_RED     = "#E05555"
_ACCENT_GOLD    = "#D4A017"
_ACCENT_SUCCESS = "#2E8B4A"
_WHITE          = "#FFFFFF"

# ── Table visuals ──────────────────────────────────────────────────────────────
_HDR_BG  = "#1B2B3A"
_HDR_FG  = "#C8D8E8"
_HDR_H   = 42
_ROW_H   = 38
_ROW_BG  = _WHITE
_ROW_HOV = "#F0F6FF"
_ROW_ALT = "#FAFBFD"
_SEP_CLR = "#E8ECF2"

_PAGE_SIZE = 20

# ── Allowed email domains ──────────────────────────────────────────────────────
_ALLOWED_DOMAINS = {"rvtgroupofcompanies.com", "bsv.ph", "bancosanvicente.com"}

# ── Column definitions: (label, db_key, width, anchor, sortable?) ──────────────
_COLUMNS = [
    ("ID",          "id",            60,   "center", True),
    ("Username",    "username",      180,  "w",      True),
    ("Email",       "email",         60,   "w",      True),
    ("Position",    "position",      260,  "w",      True),
    ("Role",        "role",          160,  "center", True),
    ("Status",      "status",        90,   "center", True),
    ("Created",     "created_at",    140,  "center", True),
    ("Last Login",  "last_login_at", 140,  "center", True),
    ("Delete",      "_delete",       60,   "center", False),
    ("Edit",        "_edit",         60,   "center", False),
]

_ROLE_BADGE = {
    "super admin":         ("#FFFFFF",  "#1E5C1E", "#1E5C1E"),
    "account officer":     (_NAVY_MID,  _NAVY_MIST, _NAVY_LIGHT),
    "credit risk officer": (_TXT_SOFT,  "#F0F4F8",  _BORDER_MID),
}
_STATUS_BADGE = {
    "active":   (_ACCENT_SUCCESS, "#E8F7EE", "#2E8B4A"),
    "inactive": (_ACCENT_RED,     "#FEF0F0", _ACCENT_RED),
    "pending":  (_ACCENT_GOLD,    "#FEF8E8", _ACCENT_GOLD),
}


# ═══════════════════════════════════════════════════════════════════════
#  DATABASE CONNECTION
# ═══════════════════════════════════════════════════════════════════════

def _db_connect():
    import psycopg2
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT", 5432)),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
    )
    return conn


# ═══════════════════════════════════════════════════════════════════════
#  AUDIT LOG HELPER
# ═══════════════════════════════════════════════════════════════════════

def _log_action(self, action: str, description: str):
    """Write an audit log entry to the logs table."""
    try:
        user_id = getattr(self, "_current_user_id", None)
        email   = getattr(self, "_current_username", None) or ""
        with _db_connect() as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO logs (user_id, email, action, description, time) "
                "VALUES (%s, %s, %s, %s, NOW())",
                (user_id, email, action, description)
            )
            conn.commit()
            cur.close()
    except Exception as e:
        print(f"[log_action] failed: {e}")


# ═══════════════════════════════════════════════════════════════════════
#  EMAIL HELPERS
# ═══════════════════════════════════════════════════════════════════════

def _is_allowed_email(email: str) -> bool:
    """Return True only if the email ends with an allowed domain."""
    email = email.strip().lower()
    if "@" not in email:
        return False
    domain = email.split("@", 1)[1]
    return domain in _ALLOWED_DOMAINS


def _generate_code() -> str:
    """Return a random 6-digit verification code as a zero-padded string."""
    return f"{random.randint(0, 999999):06d}"


def _send_verification_email(recipient: str, code: str) -> None:
    """
    Send the verification code to *recipient* via SMTP.

    Required .env keys
    ──────────────────
    SMTP_HOST      – e.g. smtp.gmail.com
    SMTP_PORT      – e.g. 587
    SMTP_USER      – sender address (Gmail: the full address)
    SMTP_PASSWORD  – app-password or SMTP password
    SMTP_FROM_NAME – display name (optional, default "DocExtract Pro")
    """
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", 587))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_pass = os.getenv("SMTP_PASSWORD", "")
    from_name = os.getenv("SMTP_FROM_NAME", "DocExtract Pro")
    from_addr = f"{from_name} <{smtp_user}>"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Your DocExtract Pro verification code"
    msg["From"]    = from_addr
    msg["To"]      = recipient

    plain = (
        f"Your DocExtract Pro account verification code is:\n\n"
        f"  {code}\n\n"
        f"This code is valid for the current session only.\n"
        f"If you did not request this, please contact your administrator."
    )
    html = f"""
    <html><body style="font-family:Segoe UI,sans-serif;background:#F4F6FA;padding:32px;">
      <div style="max-width:440px;margin:auto;background:#fff;border-radius:10px;
                  border:1px solid #C8D8E8;overflow:hidden;">
        <div style="background:#1B2B3A;padding:18px 24px;">
          <span style="color:#5BBF3E;font-size:18px;font-weight:bold;">
            DocExtract Pro
          </span>
        </div>
        <div style="padding:28px 28px 24px;">
          <p style="color:#1A2F47;font-size:15px;margin:0 0 12px;">
            Your new account verification code is:
          </p>
          <div style="background:#EBF0F7;border:1px solid #C8D8E8;border-radius:8px;
                      padding:18px;text-align:center;letter-spacing:8px;
                      font-size:28px;font-weight:bold;color:#1E3A5F;">
            {code}
          </div>
          <p style="color:#4A6480;font-size:12px;margin:16px 0 0;">
            This code is valid for the current session only.<br>
            If you did not request this, contact your administrator.
          </p>
        </div>
      </div>
    </body></html>
    """

    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html,  "html"))

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.ehlo()
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_user, recipient, msg.as_string())


# ─────────────────────────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _fmt_dt(val):
    if val is None:
        return "—"
    if isinstance(val, datetime):
        return val.strftime("%Y-%m-%d %H:%M")
    s = str(val)
    return s[:16] if len(s) >= 16 else s


def _center_dialog(dlg, w, h):
    dlg.update_idletasks()
    sw, sh = dlg.winfo_screenwidth(), dlg.winfo_screenheight()
    dlg.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")


def _pill(parent, text, fg, bg, border):
    wrap = tk.Frame(parent, bg=border, padx=1, pady=1)
    tk.Label(wrap, text=text, font=("Segoe UI", 8, "bold"),
             fg=fg, bg=bg, padx=7, pady=2).pack()
    return wrap


def _all_children(w):
    res = list(w.winfo_children())
    for c in w.winfo_children():
        res.extend(_all_children(c))
    return res


def _safe_bg(w, color):
    try:
        if getattr(w, "_is_badge", False):
            return
        if w.winfo_class() in ("Frame", "Label"):
            w.config(bg=color)
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
#  SORTING
# ─────────────────────────────────────────────────────────────────────────────

def _sort_by(self, col_key):
    if getattr(self, "_acct_sort_col", None) == col_key:
        self._acct_sort_asc = not getattr(self, "_acct_sort_asc", False)
    else:
        self._acct_sort_col = col_key
        self._acct_sort_asc = (col_key != "id")

    self._acct_page = 1
    _render_table(self)
    _refresh_header_labels(self)


def _sorted_data(self):
    data    = _filtered(self)
    col     = getattr(self, "_acct_sort_col", "id")
    asc     = getattr(self, "_acct_sort_asc", False)

    def _key(row):
        v = row.get(col)
        if v is None:
            return ("", )
        if isinstance(v, (int, float)):
            return (0, v)
        if isinstance(v, datetime):
            return (0, v.timestamp())
        return (1, str(v).lower())

    return sorted(data, key=_key, reverse=not asc)


def _col_header_text(self, label, col_key, sortable):
    if not sortable:
        return label
    if getattr(self, "_acct_sort_col", "id") == col_key:
        arrow = " ▲" if getattr(self, "_acct_sort_asc", False) else " ▼"
        return label + arrow
    return label


def _refresh_header_labels(self):
    for col_label, col_key, col_w, col_anchor, sortable in _COLUMNS:
        lbl = self._acct_hdr_labels.get(col_key)
        if lbl:
            lbl.config(text=_col_header_text(self, col_label, col_key, sortable))


# ─────────────────────────────────────────────────────────────────────────────
#  DATA
# ─────────────────────────────────────────────────────────────────────────────

def _load_users(self):
    try:
        conn = self.get_conn()
        if conn is None:
            raise Exception("No database connection.")
        cur = conn.cursor()
        cur.execute("""
            SELECT id, username, email, position, role, status,
                   created_at, last_login_at
            FROM users
        """)
        rows = cur.fetchall()
        cur.close()
        keys = [c[1] for c in _COLUMNS if not c[1].startswith("_")]
        self._acct_data = [dict(zip(keys, r)) for r in rows]
    except Exception as e:
        self._acct_data = []
        self._acct_err_var.set(f"⚠  Could not load users: {e}")
        self._acct_err_lbl.pack(anchor="w", padx=24, pady=(4, 0))
        return

    self._acct_err_lbl.pack_forget()
    self._acct_err_var.set("")
    self._acct_page = 1
    _render_table(self)


def _filtered(self):
    q = self._acct_search.get().strip().lower()
    if not q:
        return self._acct_data
    return [r for r in self._acct_data
            if any(q in str(v).lower() for v in r.values() if v is not None)]


# ─────────────────────────────────────────────────────────────────────────────
#  DIALOGS
# ─────────────────────────────────────────────────────────────────────────────

def _open_edit_dialog(self, user_row):
    """Edit username, email, position, role and status for an existing user."""
    dlg = tk.Toplevel(self)
    dlg.title(f"Edit Mode")
    dlg.configure(bg=_PAGE_BG)
    dlg.resizable(False, False)
    dlg.grab_set()
    _center_dialog(dlg, 500, 530)
    dlg.protocol("WM_DELETE_WINDOW", dlg.destroy)

    hdr = tk.Frame(dlg, bg=_HDR_BG, height=54)
    hdr.pack(fill="x"); hdr.pack_propagate(False)
    tk.Label(hdr, text=f"✏   Edit User  —  {user_row.get('username','')}",
             font=("Segoe UI", 12, "bold"), fg=_WHITE, bg=_HDR_BG,
             anchor="w").pack(side="left", padx=20, fill="y")

    body = tk.Frame(dlg, bg=_PAGE_BG)
    body.pack(fill="both", expand=True, padx=26, pady=18)

    r = tk.Frame(body, bg=_PAGE_BG); r.pack(fill="x", pady=3)
    tk.Label(r, text="ID:", font=("Segoe UI", 9, "bold"),
             fg=_TXT_SOFT, bg=_PAGE_BG, width=10, anchor="w").pack(side="left")
    tk.Label(r, text=str(user_row.get("id") or "—"),
             font=("Segoe UI", 9), bg=_PAGE_BG,
             anchor="w").pack(side="left")

    tk.Frame(body, bg=_BORDER_LIGHT, height=1).pack(fill="x", pady=(6, 4))

    edit_vars = {}

    def _entry_field(label, key):
        r = tk.Frame(body, bg=_PAGE_BG); r.pack(fill="x", pady=4)
        tk.Label(r, text=label + ":", font=("Segoe UI", 9, "bold"),
                 fg=_TXT_SOFT, bg=_PAGE_BG, width=10, anchor="w").pack(side="left")
        wrap = tk.Frame(r, bg=_WHITE,
                        highlightbackground=_BORDER_MID, highlightthickness=1)
        wrap.pack(side="left", fill="x", expand=True)
        var = tk.StringVar(value=str(user_row.get(key) or ""))
        tk.Entry(wrap, textvariable=var, font=("Segoe UI", 10),
                 fg=_TXT_NAVY, bg=_WHITE, relief="flat", bd=4,
                 insertbackground=_NAVY_MID).pack(fill="x")
        edit_vars[key] = var

    _entry_field("Username", "username")
    _entry_field("Email",    "email")
    _entry_field("Position", "position")

    tk.Frame(body, bg=_BORDER_MID, height=1).pack(fill="x", pady=(10, 6))

    role_val   = str(user_row.get("role") or "").strip().title()   # "super admin" → "Super Admin"
    status_val = str(user_row.get("status") or "").strip().capitalize()  # "active" → "Active"
    role_var   = tk.StringVar(value=role_val   or "Account Officer")
    status_var = tk.StringVar(value=status_val or "Active")

    for label, var, vals in [
        ("Role:",   role_var,   ["Super Admin", "Account Officer", "Credit Risk Officer"]),
        ("Status:", status_var, ["Active", "Inactive", "Pending"]),
    ]:
        r = tk.Frame(body, bg=_PAGE_BG); r.pack(fill="x", pady=6)
        tk.Label(r, text=label, font=("Segoe UI", 9, "bold"),
                 fg=_TXT_SOFT, bg=_PAGE_BG, width=10, anchor="w").pack(side="left")
        ctk.CTkOptionMenu(
            r, variable=var, values=vals,
            width=180, height=32, corner_radius=6,
            fg_color=_NAVY_MIST, button_color=_NAVY_LIGHT,   # ← was _NAVY_MID (too dark)
            button_hover_color=_BORDER_MID,                   # ← lighter hover
            text_color=_TXT_NAVY, dropdown_fg_color=_WHITE,
        ).pack(side="left")

    tk.Frame(dlg, bg=_BORDER_LIGHT, height=1).pack(fill="x", pady=(4, 0))

    btn_row = tk.Frame(dlg, bg=_PAGE_BG)
    btn_row.pack(fill="x", padx=26, pady=14)

    def _save():
        uid          = user_row.get("id")
        new_username = edit_vars["username"].get().strip()
        new_email    = edit_vars["email"].get().strip()
        new_position = edit_vars["position"].get().strip()
        new_role     = role_var.get().strip().lower()
        new_status   = status_var.get().strip().lower()

        if not new_username or not new_email:
            messagebox.showwarning("Missing Fields",
                                   "Username and Email are required.", parent=dlg)
            return
        try:
            conn = self.get_conn()
            cur  = conn.cursor()
            cur.execute(
                """UPDATE users
                   SET username=%s, email=%s, position=%s,
                       role=%s, status=%s, updated_at=NOW()
                   WHERE id=%s""",
                (new_username, new_email, new_position or None,
                 new_role, new_status, uid),
            )
            conn.commit()
            cur.close()

            old_username = user_row.get("username", "")
            old_role     = user_row.get("role", "")
            old_status   = user_row.get("status", "")
            changes = []
            if new_username != old_username:
                changes.append(f"username: '{old_username}' → '{new_username}'")
            if new_role != old_role:
                changes.append(f"role: '{old_role}' → '{new_role}'")
            if new_status != old_status:
                changes.append(f"status: '{old_status}' → '{new_status}'")
            change_str = ", ".join(changes) if changes else "no field changes"
            _log_action(self, "edit_user",
                        f"Edited user id={uid} ({new_username}): {change_str}")

            messagebox.showinfo("Saved",
                                f"User #{uid} updated successfully.", parent=dlg)
            dlg.destroy()
            _load_users(self)
        except Exception as e:
            messagebox.showerror("DB Error",
                                 f"Could not update user:\n{e}", parent=dlg)

    ctk.CTkButton(btn_row, text="💾  Save Changes", command=_save,
            width=140, height=36, corner_radius=7,
            fg_color=_SB_ACCENT, hover_color="#4CAF35",
            text_color="#0A1628", font=("Segoe UI", 10, "bold")).pack(side="right", padx=(10, 0))
    ctk.CTkButton(btn_row, text="Cancel", command=dlg.destroy,
                width=90, height=36, corner_radius=7,
                fg_color=_BORDER_MID, hover_color="#B0C4D8",   # ← more visible
                text_color=_TXT_NAVY, font=("Segoe UI", 10)).pack(side="right")


def _open_delete_dialog(self, user_row):
    """Confirm then delete a user from the DB."""
    uid   = user_row.get("id", "")
    uname = user_row.get("username", "")

    dlg = tk.Toplevel(self)
    dlg.title("Confirm Delete")
    dlg.configure(bg=_PAGE_BG)
    dlg.resizable(False, False)
    dlg.grab_set()
    _center_dialog(dlg, 480, 400)
    dlg.protocol("WM_DELETE_WINDOW", dlg.destroy)

    hdr = tk.Frame(dlg, bg="#7A1818", height=54)
    hdr.pack(fill="x"); hdr.pack_propagate(False)
    tk.Label(hdr, text="🗑   Delete User",
             font=("Segoe UI", 12, "bold"), fg=_WHITE, bg="#7A1818",
             anchor="w").pack(side="left", padx=20, fill="y")

    body = tk.Frame(dlg, bg=_PAGE_BG)
    body.pack(fill="both", expand=True, padx=26, pady=22)

    tk.Label(body, text="Are you sure you want to permanently delete:",
             font=("Segoe UI", 10), fg=_TXT_NAVY, bg=_PAGE_BG,
             anchor="w").pack(anchor="w")

    info_box = tk.Frame(body, bg="#FEF0F0",
                        highlightbackground="#F5CCCC", highlightthickness=1)
    info_box.pack(fill="x", pady=(8, 0))

    tk.Label(info_box,
             text=f"  ID: {uid}",
             font=("Segoe UI", 9, "bold"), fg="#7A1818", bg="#FEF0F0",
             anchor="w").pack(anchor="w", padx=10, pady=(8, 0))
    tk.Label(info_box,
             text=f"  Username: {uname}",
             font=("Segoe UI", 9, "bold"), fg="#7A1818", bg="#FEF0F0",
             anchor="w").pack(anchor="w", padx=10)
    tk.Label(info_box,
             text=f"  Email: {user_row.get('email','—')}",
             font=("Segoe UI", 9, "bold"), fg="#7A1818", bg="#FEF0F0",
             anchor="w").pack(anchor="w", padx=10)
    tk.Label(info_box,
             text=f"  Position: {user_row.get('position','—')}",
             font=("Segoe UI", 9, "bold"), fg="#7A1818", bg="#FEF0F0",
             anchor="w").pack(anchor="w", padx=10)
    tk.Label(info_box,
             text=f"  Role: {str(user_row.get('role','—')).title()}",
             font=("Segoe UI", 9, "bold"), fg="#7A1818", bg="#FEF0F0",
             anchor="w").pack(anchor="w", padx=10, pady=(0, 8))

    tk.Label(body, text="⚠  This action cannot be undone.",
             font=("Segoe UI", 9, "italic"), fg=_ACCENT_RED, bg=_PAGE_BG,
             anchor="w").pack(anchor="w", pady=(10, 0))

    tk.Frame(dlg, bg=_BORDER_LIGHT, height=1).pack(fill="x", pady=(0, 0))

    btn_row = tk.Frame(dlg, bg=_PAGE_BG)
    btn_row.pack(fill="x", padx=26, pady=14)

    def _confirm():
        try:
            conn = self.get_conn()
            cur  = conn.cursor()
            cur.execute("DELETE FROM users WHERE id=%s", (uid,))
            conn.commit()
            cur.close()

            _log_action(self, "delete_user",
                        f"Deleted user id={uid} "
                        f"(username='{uname}', "
                        f"email='{user_row.get('email', '')}', "
                        f"role='{user_row.get('role', '')}')")

            messagebox.showinfo("Deleted",
                                f"User '{uname}' has been deleted.", parent=dlg)
            dlg.destroy()
            _load_users(self)
        except Exception as e:
            messagebox.showerror("DB Error",
                                 f"Could not delete user:\n{e}", parent=dlg)

    ctk.CTkButton(btn_row, text="🗑  Yes, Delete", command=_confirm,
                  width=130, height=36, corner_radius=7,
                  fg_color=_ACCENT_RED, hover_color="#BF2222",
                  text_color=_WHITE, font=("Segoe UI", 10, "bold")).pack(side="right")
    ctk.CTkButton(btn_row, text="Cancel", command=dlg.destroy,
                  width=90, height=36, corner_radius=7,
                  fg_color=_BORDER_MID, hover_color="#B0C4D8",   # ← more visible
                  text_color=_TXT_NAVY, font=("Segoe UI", 10)).pack(side="right", padx=(0, 10))
    
# ─────────────────────────────────────────────────────────────────────────────
#  CONFIGURE ROLE TABS DIALOG
# ─────────────────────────────────────────────────────────────────────────────

_ALL_TABS = [
    ("dashboard",      "🏠  Dashboard"),
    ("cibi",           "📋  CIBI Mode"),
    ("extract",        "📄  Extracted"),
    ("analysis",       "🏦  CIBI Analysis"),
    ("summary",        "📊  Summary"),
    ("lookup",         "🔎  Look-Up"),
    ("lookup_summary", "📋  LU Summary"),
    ("lu_analysis",    "📈  LU Analysis"),
    ("logs",           "🗒  Logs"),
    ("accounts",       "👤  Accounts"),
    ("approvals",      "✅  Approvals"),
]

_ALL_ROLES = [
    "super admin",
    "account officer",
    "credit risk officer",
    "user",
]


def _load_role_tab_config(self) -> dict:
    live_roles = _load_all_roles(self)
    result = {r: set() for r in live_roles}
    try:
        conn = self.get_conn()
        cur  = conn.cursor()
        cur.execute("SELECT role, tab_access FROM role_tab_config")
        for role, tabs in cur.fetchall():
            if tabs:
                result[role] = set(tabs)
        cur.close()
    except Exception as e:
        print(f"[_load_role_tab_config] {e}")
    return result


def _save_role_tab_config(self, config: dict):
    """
    Upserts {role: set_of_tab_keys} into role_tab_config.
    Uses PostgreSQL array literal for tab_access column.
    """
    try:
        conn = self.get_conn()
        cur  = conn.cursor()
        for role, tabs in config.items():
            cur.execute(
                """
                INSERT INTO role_tab_config (role, tab_access)
                VALUES (%s, %s)
                ON CONFLICT (role) DO UPDATE
                    SET tab_access = EXCLUDED.tab_access
                """,
                (role, list(tabs))
            )
        conn.commit()
        cur.close()
    except Exception as e:
        raise RuntimeError(f"DB write failed: {e}")
    
def _load_all_roles(self) -> list:
    """Load role names from the roles table. Falls back to hardcoded list."""
    try:
        conn = self.get_conn()
        cur  = conn.cursor()
        cur.execute("SELECT role FROM roles ORDER BY role")
        rows = cur.fetchall()
        cur.close()
        if rows:
            return [r[0] for r in rows]
    except Exception as e:
        print(f"[_load_all_roles] {e}")
    return list(_ALL_ROLES)


def _open_role_tabs_dialog(self):
    live_roles     = _load_all_roles(self)
    current_config = _load_role_tab_config(self)

    # Working state — no DB writes until Save is clicked
    # Each entry: {"original": str|None, "current": str, "deleted": bool}
    # original=None means it's a newly added role (not yet in DB)
    roles_state = [{"original": r, "current": r, "deleted": False}
                   for r in live_roles]

    # check_vars[tab_key][original_role] = BooleanVar
    check_vars = {}
    for tab_key, _ in _ALL_TABS:
        check_vars[tab_key] = {}
        for r in live_roles:
            check_vars[tab_key][r] = tk.BooleanVar(
                value=tab_key in current_config.get(r, set()))

    dlg = tk.Toplevel(self)
    dlg.title("Configure Role Tab Access")
    dlg.configure(bg="#0B1622")
    dlg.resizable(False, False)
    dlg.overrideredirect(True)
    dlg.grab_set()
    _center_dialog(dlg, 850, 600)
    def _on_close():
        # Clean up traces before destroying
        for (v, tid) in getattr(dlg, '_tab_traces', []):
            try:
                v.trace_remove("write", tid)
            except Exception:
                pass
        dlg.destroy()

    dlg.protocol("WM_DELETE_WINDOW", _on_close)

    selected_orig = tk.StringVar(
        value=roles_state[0]["original"] if roles_state else "")

    # ── Root layout ───────────────────────────────────────────────────────
    root_frame = tk.Frame(dlg, bg="#0B1622",
                          highlightbackground="#5BBF3E",
                          highlightthickness=2)
    root_frame.pack(fill="both", expand=True)

    # ══════════════════════════════════════════════════════════════════════
    #  LEFT SIDEBAR
    # ══════════════════════════════════════════════════════════════════════
    sidebar = tk.Frame(root_frame, bg="#0B1622", width=265)
    sidebar.pack(side="left", fill="y")
    sidebar.pack_propagate(False)

    # Header branding
    sb_hdr = tk.Frame(sidebar, bg="#0B1622")
    sb_hdr.pack(fill="x", padx=16, pady=(18, 4))
    tk.Label(sb_hdr, text="⚙", font=("Segoe UI Emoji", 16),
             fg="#5BBF3E", bg="#0B1622").pack(side="left", padx=(0, 8))
    sb_tc = tk.Frame(sb_hdr, bg="#0B1622")
    sb_tc.pack(side="left")
    tk.Label(sb_tc, text="CONFIGURE",
             font=("Segoe UI", 8, "bold"), fg="#4A6480",
             bg="#0B1622", anchor="w").pack(anchor="w")
    tk.Label(sb_tc, text="Role Tab Access",
             font=("Segoe UI", 11, "bold"), fg="#EEF3FA",
             bg="#0B1622", anchor="w").pack(anchor="w")

    tk.Label(sidebar,
             text="Add, rename or remove roles.\nChanges apply on Save.",
             font=("Segoe UI", 8), fg="#4A6480", bg="#0B1622",
             justify="left", anchor="w", wraplength=200
             ).pack(anchor="w", padx=20, pady=(2, 8))

    tk.Frame(sidebar, bg="#1A2F47", height=1).pack(fill="x", padx=12, pady=(0, 6))

    # "ROLES" label + ＋ Add button on same row
    sec_row = tk.Frame(sidebar, bg="#0B1622")
    sec_row.pack(fill="x", padx=14, pady=(0, 4))
    tk.Label(sec_row, text="ROLES",
             font=("Segoe UI", 7, "bold"), fg="#2D4F7A",
             bg="#0B1622").pack(side="left")
    add_lbl = tk.Label(sec_row, text="＋ Add Role",
                       font=("Segoe UI", 7, "bold"), fg="#5BBF3E",
                       bg="#0B1622", cursor="hand2")
    add_lbl.pack(side="right")

    # Pills live here — rebuilt whenever roles_state changes
    pills_frame = tk.Frame(sidebar, bg="#0B1622")
    pills_frame.pack(fill="x")

    # Spacer + version footer
    tk.Frame(sidebar, bg="#0B1622").pack(fill="both", expand=True)
    tk.Frame(sidebar, bg="#1A2F47", height=1).pack(fill="x", padx=12)
    tk.Label(sidebar, text="BSV AI-OCR v2.0",
             font=("Segoe UI", 7), fg="#2D4F7A",
             bg="#0B1622", anchor="w").pack(anchor="w", padx=20, pady=(6, 12))

    # ══════════════════════════════════════════════════════════════════════
    #  RIGHT PANEL
    # ══════════════════════════════════════════════════════════════════════
    right = tk.Frame(root_frame, bg="#F4F6FA")
    right.pack(side="left", fill="both", expand=True)

    # Right header
    r_hdr = tk.Frame(right, bg="#FFFFFF", height=56)
    r_hdr.pack(fill="x")
    r_hdr.pack_propagate(False)
    tk.Frame(right, bg="#E8ECF2", height=1).pack(fill="x")

    right_title_lbl = tk.Label(r_hdr, text="",
                               font=("Segoe UI", 14, "bold"),
                               fg="#1A2F47", bg="#FFFFFF")
    right_title_lbl.pack(side="left", anchor="center", padx=(20, 0))

    close_x = tk.Label(r_hdr, text="✕",
                       font=("Segoe UI", 11, "bold"),
                       fg="#7A94B0", bg="#FFFFFF",
                       cursor="hand2", padx=14)
    close_x.pack(side="right", fill="y")
    close_x.bind("<Enter>",    lambda e: close_x.config(fg="#E05555", bg="#FFF0F0"))
    close_x.bind("<Leave>",    lambda e: close_x.config(fg="#7A94B0", bg="#FFFFFF"))
    # FIXED — calls cleanup first
    close_x.bind("<Button-1>", lambda e: _on_close())

    hint_lbl = tk.Label(right, text="",
                        font=("Segoe UI", 8), fg="#8A9BB0",
                        bg="#F4F6FA", anchor="w")
    hint_lbl.pack(anchor="w", padx=20, pady=(10, 0))

    # Scrollable tab cards
    card_outer = tk.Frame(right, bg="#E8ECF2", padx=1, pady=1)
    card_outer.pack(fill="both", expand=True, padx=20, pady=(8, 0))
    card_area = tk.Frame(card_outer, bg="#FFFFFF")
    card_area.pack(fill="both", expand=True)

    vsb = tk.Scrollbar(card_area, orient="vertical", relief="flat",
                       troughcolor="#F0F4F8", bg="#C8D8E8", width=8, bd=0)
    vsb.pack(side="right", fill="y")
    tab_canvas = tk.Canvas(card_area, bg="#FFFFFF",
                           highlightthickness=0, yscrollcommand=vsb.set)
    tab_canvas.pack(side="left", fill="both", expand=True)
    vsb.config(command=tab_canvas.yview)

    tab_body = tk.Frame(tab_canvas, bg="#FFFFFF")
    _tc_win  = tab_canvas.create_window((0, 0), window=tab_body, anchor="nw")
    tab_body.bind("<Configure>",
                  lambda e: tab_canvas.configure(
                      scrollregion=tab_canvas.bbox("all")))
    tab_canvas.bind("<Configure>",
                    lambda e: tab_canvas.itemconfig(_tc_win, width=e.width))

    def _on_wheel(e):
        tab_canvas.yview_scroll(int(-1*(e.delta/120)), "units")
    tab_canvas.bind("<MouseWheel>", _on_wheel)
    tab_body.bind("<MouseWheel>",   _on_wheel)

    # Footer with Save / Cancel
    tk.Frame(right, bg="#E8ECF2", height=1).pack(fill="x", pady=(6, 0))
    footer_bar = tk.Frame(right, bg="#F4F6FA")
    footer_bar.pack(fill="x", padx=20, pady=10)

    tk.Label(footer_bar,
             text="Changes apply on next login.",
             font=("Segoe UI", 8, "italic"),
             fg="#8A9BB0", bg="#F4F6FA").pack(side="left")

    # ── SAVE ──────────────────────────────────────────────────────────────
    def _save():
        try:
            conn = self.get_conn()
            cur  = conn.cursor()

            for rs in roles_state:
                orig    = rs["original"]   # None if brand-new
                current = rs["current"].strip()
                deleted = rs["deleted"]

                if deleted:
                    if orig:   # only touch DB for existing roles
                        cur.execute(
                            "DELETE FROM role_tab_config WHERE role = %s", (orig,))
                        cur.execute(
                            "DELETE FROM roles WHERE role = %s", (orig,))
                        # Reset affected users to 'user'
                        cur.execute(
                            "UPDATE users SET role = 'user' WHERE role = %s", (orig,))
                    continue

                if not current:
                    continue  # skip blank entries

                if orig is None:
                    # Brand-new role — insert into roles table
                    cur.execute(
                        "INSERT INTO roles (role) VALUES (%s) ON CONFLICT DO NOTHING",
                        (current,))
                elif orig != current:
                    # Renamed — propagate everywhere
                    cur.execute(
                        "UPDATE roles SET role = %s WHERE role = %s",
                        (current, orig))
                    cur.execute(
                        "UPDATE role_tab_config SET role = %s WHERE role = %s",
                        (current, orig))
                    cur.execute(
                        "UPDATE users SET role = %s WHERE role = %s",
                        (current, orig))

                # Save tab access (upsert) using the *current* (possibly new) name
                tabs = [
                    tk_key for tk_key, _ in _ALL_TABS
                    if check_vars.get(tk_key, {}).get(orig) is not None
                    and check_vars[tk_key][orig].get()
                ]
                cur.execute(
                    """
                    INSERT INTO role_tab_config (role, tab_access)
                    VALUES (%s, %s)
                    ON CONFLICT (role) DO UPDATE
                        SET tab_access = EXCLUDED.tab_access
                    """,
                    (current, tabs))

            conn.commit()
            cur.close()

            _log_action(self, "configure_role_tabs",
                        "Updated roles and tab access configuration")
            messagebox.showinfo(
                "Saved",
                "Configuration saved successfully.\n"
                "Users will see the changes on next login.",
                parent=dlg)
            dlg.destroy()

        except Exception as e:
            try:   conn.rollback()
            except Exception: pass
            messagebox.showerror("DB Error",
                                 f"Could not save configuration:\n{e}",
                                 parent=dlg)

    ctk.CTkButton(footer_bar, text="💾  Save Configuration",
                  command=_save,
                  width=160, height=36, corner_radius=7,
                  fg_color="#5BBF3E", hover_color="#4CAF35",
                  text_color="#0A1628",
                  font=("Segoe UI", 10, "bold")).pack(side="right", padx=(8, 0))
    ctk.CTkButton(footer_bar, text="Cancel",
                  command=_on_close,
                  width=90, height=36, corner_radius=7,
                  fg_color="#C8D8E8", hover_color="#B0C4D8",
                  text_color="#1A2F47",
                  font=("Segoe UI", 10)).pack(side="right")

    # ══════════════════════════════════════════════════════════════════════
    #  REFRESH RIGHT PANEL
    # ══════════════════════════════════════════════════════════════════════
    def _refresh_right():
        orig = selected_orig.get()
        rs   = next((r for r in roles_state
                     if r["original"] == orig and not r["deleted"]), None)
        if not rs:
            # Nothing to show — blank slate
            right_title_lbl.config(text="No role selected")
            hint_lbl.config(text="")
            for w in tab_body.winfo_children():
                w.destroy()
            return

        display = rs["current"].title()
        right_title_lbl.config(text=display)
        hint_lbl.config(
            text=f'Tabs visible to  "{display}"  role:')

        for w in tab_body.winfo_children():
            w.destroy()

        # Select All / Deselect All row
        ctrl_row = tk.Frame(tab_body, bg="#FFFFFF")
        ctrl_row.pack(fill="x", padx=16, pady=(10, 4))
        tk.Label(ctrl_row, text="TABS",
                 font=("Segoe UI", 8, "bold"), fg="#4A6480",
                 bg="#FFFFFF").pack(side="left")

        def _sel_all():
            for tk_key, _ in _ALL_TABS:
                if orig in check_vars.get(tk_key, {}):
                    check_vars[tk_key][orig].set(True)

        def _desel_all():
            for tk_key, _ in _ALL_TABS:
                if orig in check_vars.get(tk_key, {}):
                    check_vars[tk_key][orig].set(False)

        desel_lbl = tk.Label(ctrl_row, text="Deselect All",
                             font=("Segoe UI", 8), fg="#E05555",
                             bg="#FFFFFF", cursor="hand2")
        desel_lbl.pack(side="right")
        desel_lbl.bind("<Button-1>", lambda e: _desel_all())

        tk.Label(ctrl_row, text=" · ",
                 font=("Segoe UI", 8), fg="#8A9BB0",
                 bg="#FFFFFF").pack(side="right")

        sel_lbl = tk.Label(ctrl_row, text="Select All",
                           font=("Segoe UI", 8), fg="#5BBF3E",
                           bg="#FFFFFF", cursor="hand2")
        sel_lbl.pack(side="right")
        sel_lbl.bind("<Button-1>", lambda e: _sel_all())

        tk.Frame(tab_body, bg="#E8ECF2", height=1).pack(
            fill="x", padx=16, pady=(0, 6))
        
        # Remove all previously registered traces
        for (v, tid) in getattr(dlg, '_tab_traces', []):
            try:
                v.trace_remove("write", tid)
            except Exception:
                pass
        dlg._tab_traces = []

        for idx, (tab_key, tab_label) in enumerate(_ALL_TABS):
            card_bg = "#FFFFFF" if idx % 2 == 0 else "#FAFBFD"

            # Ensure BooleanVar exists (needed for newly added roles)
            if orig not in check_vars.get(tab_key, {}):
                check_vars.setdefault(tab_key, {})[orig] = tk.BooleanVar(value=False)
            var = check_vars[tab_key][orig]

            card = tk.Frame(tab_body, bg=card_bg,
                            highlightbackground="#E8ECF2",
                            highlightthickness=1, height=52)
            card.pack(fill="x", padx=16, pady=3)
            card.pack_propagate(False)

            acc = tk.Frame(card, bg="#5BBF3E", width=4)

            def _upd(v=var, a=acc):
                # Guard: skip if widget was destroyed
                try:
                    if not a.winfo_exists():
                        return
                    if v.get():
                        a.place(x=0, y=0, width=4, relheight=1.0)
                        a.lift()
                    else:
                        a.place_forget()
                except Exception:
                    pass

            trace_id = var.trace_add("write", lambda *_, fn=_upd: fn())
            # Store trace for cleanup on next rebuild
            dlg._tab_traces.append((var, trace_id))
            _upd()

            icon_txt = tab_label.split("  ")[0] if "  " in tab_label else "📄"
            name_txt = (tab_label.split("  ", 1)[1]
                        if "  " in tab_label else tab_label)

            left = tk.Frame(card, bg=card_bg)
            left.pack(side="left", fill="y", padx=(14, 0))
            tk.Label(left, text=icon_txt,
                     font=("Segoe UI Emoji", 14),
                     fg="#5BBF3E", bg=card_bg
                     ).pack(side="left", padx=(0, 10), pady=14)
            tk.Label(left, text=name_txt,
                     font=("Segoe UI", 10, "bold"),
                     fg="#1A2F47", bg=card_bg, anchor="w"
                     ).pack(side="left", anchor="center")

            cb_frame = tk.Frame(card, bg=card_bg, padx=16)
            cb_frame.pack(side="right", fill="y")
            tk.Checkbutton(
                cb_frame, variable=var,
                bg=card_bg, activebackground=card_bg,
                selectcolor="#D6EFD0",
                relief="flat", bd=0, cursor="hand2",
                padx=6, pady=6
            ).pack(anchor="center", expand=True)

            all_cw = [card, left] + list(left.winfo_children())

            def _hov_on(e=None, wl=all_cw):
                for w in wl:
                    try: w.config(bg="#EEF7EC")
                    except Exception: pass

            def _hov_off(e=None, wl=all_cw, bg=card_bg):
                for w in wl:
                    try: w.config(bg=bg)
                    except Exception: pass

            def _toggle(e=None, v=var):
                v.set(not v.get())

            for w in all_cw:
                w.bind("<Enter>",    _hov_on)
                w.bind("<Leave>",    _hov_off)
                w.bind("<Button-1>", _toggle)

        tk.Frame(tab_body, bg="#FFFFFF", height=12).pack()
        tab_canvas.yview_moveto(0)

    # ══════════════════════════════════════════════════════════════════════
    #  BUILD / REBUILD SIDEBAR PILLS
    # ══════════════════════════════════════════════════════════════════════
    def _rebuild_pills():
        for w in pills_frame.winfo_children():
            w.destroy()

        active_exists = any(
            rs["original"] == selected_orig.get() and not rs["deleted"]
            for rs in roles_state)
        if not active_exists and roles_state:
            # Select first non-deleted
            first = next(
                (rs for rs in roles_state if not rs["deleted"]), None)
            selected_orig.set(first["original"] if first else "")

        for rs in roles_state:
            if rs["deleted"]:
                continue

            orig   = rs["original"]
            is_act = (selected_orig.get() == orig)
            p_bg   = "#162438" if is_act else "#0B1622"
            t_fg   = "#EEF3FA" if is_act else "#7A94B0"

            pill = tk.Frame(pills_frame, bg=p_bg, height=46, cursor="hand2")
            pill.pack(fill="x", padx=8, pady=1)
            pill.pack_propagate(False)

            stripe = tk.Frame(pill, bg="#5BBF3E", width=3)
            if is_act:
                stripe.place(x=0, y=0, width=3, relheight=1.0)

            tk.Label(pill, text="👤",
                     font=("Segoe UI Emoji", 11),
                     fg="#5BBF3E" if is_act else "#4A6480",
                     bg=p_bg, width=3).pack(side="left", padx=(10, 4))

            name_var = tk.StringVar(value=rs["current"].title())
            name_lbl = tk.Label(
                pill, textvariable=name_var,
                font=("Segoe UI", 9, "bold") if is_act else ("Segoe UI", 9),
                fg=t_fg, bg=p_bg, anchor="w",
                width=13, wraplength=0) 

            # Delete icon — pack RIGHT before name expands
            del_ico = tk.Label(pill, text="🗑",
                               font=("Segoe UI Emoji", 10),
                               fg="#663333", bg=p_bg,
                               cursor="hand2", padx=4)
            del_ico.pack(side="right", padx=(0, 2))

            # Rename icon — pack RIGHT before name expands
            ren_ico = tk.Label(pill, text="✎",
                               font=("Segoe UI", 11),
                               fg="#2D4F7A", bg=p_bg,
                               cursor="hand2", padx=4)
            ren_ico.pack(side="right")

            # Name label last — now it only fills what's left
            name_lbl.pack(side="left", fill="x", expand=True)

            # Activate on click
            def _activate(e=None, o=orig):
                selected_orig.set(o)
                _rebuild_pills()
                _refresh_right()

            def _p_enter(e=None, p=pill, s=stripe, o=orig):
                if selected_orig.get() != o:
                    p.config(bg="#131D2D")
                    for w in p.winfo_children():
                        if w is not s:
                            try: w.config(bg="#131D2D")
                            except: pass

            def _p_leave(e=None, p=pill, s=stripe, bg=p_bg, o=orig):
                if selected_orig.get() != o:
                    p.config(bg=bg)
                    for w in p.winfo_children():
                        if w is not s:
                            try: w.config(bg=bg)
                            except: pass

            for w in (pill, name_lbl):
                w.bind("<Button-1>", _activate)
                w.bind("<Enter>",    _p_enter)
                w.bind("<Leave>",    _p_leave)

            # ── Rename popover ────────────────────────────────────────────
            def _open_rename(e=None, rs_ref=rs, nv=name_var, p=pill):
                pop = tk.Toplevel(dlg)
                pop.overrideredirect(True)
                pop.configure(bg="#1A2F47")
                pop.grab_set()
                px = p.winfo_rootx()
                py = p.winfo_rooty() + p.winfo_height() + 4
                pop.geometry(f"230x46+{px}+{py}")

                inner = tk.Frame(pop, bg="#1A2F47",
                                 highlightbackground="#2D5F8A",
                                 highlightthickness=1)
                inner.pack(fill="both", expand=True)

                ent_var = tk.StringVar(value=rs_ref["current"])
                ent = tk.Entry(inner, textvariable=ent_var,
                               font=("Segoe UI", 10),
                               fg="#EEF3FA", bg="#0B1622",
                               relief="flat", bd=6,
                               insertbackground="#5BBF3E")
                ent.pack(side="left", fill="x", expand=True, padx=(6, 0))
                ent.focus_set()
                ent.select_range(0, "end")

                def _apply(e=None):
                    new_name = ent_var.get().strip()
                    if new_name:
                        rs_ref["current"] = new_name
                        nv.set(new_name.title())
                        if selected_orig.get() == rs_ref["original"]:
                            right_title_lbl.config(text=new_name.title())
                            hint_lbl.config(
                                text=f'Tabs visible to  "{new_name.title()}"  role:')
                    pop.destroy()

                ok_lbl = tk.Label(inner, text="✔",
                                  font=("Segoe UI", 11, "bold"),
                                  fg="#5BBF3E", bg="#1A2F47",
                                  cursor="hand2", padx=8)
                ok_lbl.pack(side="right")
                ok_lbl.bind("<Button-1>", _apply)
                ent.bind("<Return>",  _apply)
                ent.bind("<Escape>",  lambda e: pop.destroy())

            ren_ico.bind("<Button-1>", _open_rename)

            # ── Mark deleted (no DB change yet) ───────────────────────────
            def _mark_delete(e=None, rs_ref=rs, o=orig):
                confirmed = messagebox.askyesno(
                    "Delete Role",
                    f'Remove role  "{rs_ref["current"]}"?\n\n'
                    f'Users with this role will be reset to  "user"  on Save.',
                    parent=dlg)
                if not confirmed:
                    return
                rs_ref["deleted"] = True
                # If it was selected, move selection to first available
                if selected_orig.get() == o:
                    first = next(
                        (r for r in roles_state if not r["deleted"]), None)
                    selected_orig.set(first["original"] if first else "")
                _rebuild_pills()
                _refresh_right()

            del_ico.bind("<Button-1>", _mark_delete)

    # ── Add Role handler ──────────────────────────────────────────────────
    def _add_role(e=None):
        # Inline popover below the Add label
        pop = tk.Toplevel(dlg)
        pop.overrideredirect(True)
        pop.configure(bg="#1A2F47")
        pop.grab_set()
        px = add_lbl.winfo_rootx()
        py = add_lbl.winfo_rooty() + add_lbl.winfo_height() + 4
        pop.geometry(f"230x46+{px}+{py}")

        inner = tk.Frame(pop, bg="#1A2F47",
                         highlightbackground="#2D5F8A",
                         highlightthickness=1)
        inner.pack(fill="both", expand=True)

        ent_var = tk.StringVar()
        ent = tk.Entry(inner, textvariable=ent_var,
                       font=("Segoe UI", 10),
                       fg="#EEF3FA", bg="#0B1622",
                       relief="flat", bd=6,
                       insertbackground="#5BBF3E",
                       width=18)
        ent.pack(side="left", fill="x", expand=True, padx=(6, 0))
        ent.focus_set()

        def _confirm_add(e=None):
            name = ent_var.get().strip().lower()
            pop.destroy()
            if not name:
                return
            # Check duplicate
            existing = [rs["current"].lower() for rs in roles_state
                        if not rs["deleted"]]
            if name in existing:
                messagebox.showwarning("Duplicate",
                                       f'Role "{name}" already exists.',
                                       parent=dlg)
                return
            # Add to working state with original=None (new)
            new_rs = {"original": None, "current": name, "deleted": False}
            roles_state.append(new_rs)
            # Pre-create BooleanVars for new role
            for tk_key, _ in _ALL_TABS:
                check_vars.setdefault(tk_key, {})[None] = tk.BooleanVar(value=False)
            # Since multiple new roles would all share original=None,
            # use a unique sentinel — the index
            sentinel = f"__new_{len(roles_state)}__"
            new_rs["original"] = sentinel
            for tk_key, _ in _ALL_TABS:
                check_vars.setdefault(tk_key, {})[sentinel] = tk.BooleanVar(value=False)
            selected_orig.set(sentinel)
            _rebuild_pills()
            _refresh_right()

        ok_lbl = tk.Label(inner, text="✔",
                          font=("Segoe UI", 11, "bold"),
                          fg="#5BBF3E", bg="#1A2F47",
                          cursor="hand2", padx=8)
        ok_lbl.pack(side="right")
        ok_lbl.bind("<Button-1>", _confirm_add)
        ent.bind("<Return>",  _confirm_add)
        ent.bind("<Escape>",  lambda e: pop.destroy())

    add_lbl.bind("<Button-1>", _add_role)

    # Initial render
    _rebuild_pills()
    _refresh_right()


# ─────────────────────────────────────────────────────────────────────────────
#  ADD USER DIALOG  (domain validation + two-step email verification)
# ─────────────────────────────────────────────────────────────────────────────

def _open_add_dialog(self):
    """
    Create a new user.

    Flow
    ────
    Step 1 — Fill in details then click "✉ Send Verification Code"
             • Validates required fields and email domain
             • Sends a 6-digit OTP to the target email via SMTP
             • Reveals the Step-2 code entry section

    Step 2 — Enter the code then click "✔ Create User"
             • Compares entered code against the generated one
             • On match → inserts the row into PostgreSQL
             • "↺ Resend" generates a fresh code and re-sends it
    """
    dlg = tk.Toplevel(self)
    dlg.title("New User")
    dlg.configure(bg=_PAGE_BG)
    dlg.resizable(False, False)
    dlg.grab_set()
    _center_dialog(dlg, 500, 546)
    dlg.protocol("WM_DELETE_WINDOW", dlg.destroy)

    # Mutable state for the pending OTP
    _pending_code = {"value": None}

    # ── Header ────────────────────────────────────────────────────────────
    hdr = tk.Frame(dlg, bg=_HDR_BG, height=54)
    hdr.pack(fill="x")
    hdr.pack_propagate(False)
    tk.Label(hdr, text="➕   Add New User",
             font=("Segoe UI", 12, "bold"), fg=_WHITE, bg=_HDR_BG,
             anchor="w").pack(side="left", padx=20, fill="y")

    body = tk.Frame(dlg, bg=_PAGE_BG)
    body.pack(fill="both", expand=True, padx=26, pady=14)

    fields = {}

    def _entry_field(label, key, show=""):
        """Build a labelled entry row and register it in `fields`."""
        r = tk.Frame(body, bg=_PAGE_BG)
        r.pack(fill="x", pady=4)
        tk.Label(r, text=label + ":", font=("Segoe UI", 9, "bold"),
                 fg=_TXT_SOFT, bg=_PAGE_BG, width=10, anchor="w").pack(side="left")
        wrap = tk.Frame(r, bg=_WHITE,
                        highlightbackground=_BORDER_MID, highlightthickness=1)
        wrap.pack(side="left", fill="x", expand=True)
        var = tk.StringVar()
        tk.Entry(wrap, textvariable=var, font=("Segoe UI", 10),
                 fg=_TXT_NAVY, bg=_WHITE, relief="flat", bd=4,
                 show=show, insertbackground=_NAVY_MID).pack(fill="x")
        fields[key] = var
        return wrap  # caller keeps a ref for highlight colour changes

    _entry_field("Username", "username")
    email_wrap = _entry_field("Email", "email")   # ref kept for red-border on bad domain

    # Domain hint shown under the email row
    tk.Label(body,
             text="✉ Only @bsv.ph/@bancosanvicente.com addresses are accepted.",
             font=("Segoe UI", 7, "italic"),
             fg=_TXT_MUTED, bg=_PAGE_BG, anchor="w").pack(
                 fill="x", padx=(95, 0), pady=(0, 4))

    _entry_field("Password", "password", show="•")
    _entry_field("Position", "position")

    role_var   = tk.StringVar(value="Account Officer")
    status_var = tk.StringVar(value="Active")

    for label, var, opts in [
        ("Role",   role_var,   ["Super Admin", "Account Officer", "Credit Risk Officer"]),
        ("Status", status_var, ["Active", "Inactive"]),
    ]:
        r = tk.Frame(body, bg=_PAGE_BG)
        r.pack(fill="x", pady=4)
        tk.Label(r, text=label + ":", font=("Segoe UI", 9, "bold"),
                 fg=_TXT_SOFT, bg=_PAGE_BG, width=10, anchor="w").pack(side="left")
        ctk.CTkOptionMenu(r, variable=var, values=opts,
                          width=180, height=32, corner_radius=6,
                          fg_color=_NAVY_MIST, button_color=_NAVY_LIGHT,
                          button_hover_color=_NAVY_LIGHT,
                          text_color=_TXT_NAVY,
                          dropdown_fg_color=_WHITE).pack(side="left")

    # ── Verification code section (hidden until code is sent) ─────────────
    code_section = tk.Frame(body, bg=_PAGE_BG)
    # packed later by _send_code()

    code_box = tk.Frame(code_section, bg="#EBF7EE",
                        highlightbackground="#A8D5B5", highlightthickness=1)
    code_box.pack(fill="x")

    tk.Label(code_box,
             text="✉  A 6-digit code has been sent to the email address.",
             font=("Segoe UI", 9), fg=_ACCENT_SUCCESS, bg="#EBF7EE",
             anchor="w").pack(anchor="w", padx=10, pady=(8, 2))

    code_row = tk.Frame(code_box, bg="#EBF7EE")
    code_row.pack(fill="x", padx=10, pady=(8, 8))

    tk.Label(code_row, text="Enter code:", font=("Segoe UI", 9, "bold"),
             fg=_TXT_SOFT, bg="#EBF7EE", width=10, anchor="w").pack(side="left")

    code_entry_wrap = tk.Frame(code_row, bg=_WHITE,
                               highlightbackground=_BORDER_MID,
                               highlightthickness=1)
    code_entry_wrap.pack(side="left")
    code_var = tk.StringVar()

    def _validate_code(P):
        return P.isdigit() and len(P) <= 6 or P == ""
    vcmd = dlg.register(_validate_code)

    tk.Entry(code_entry_wrap, textvariable=code_var,
             font=("Segoe UI", 11, "bold"),
             fg=_TXT_NAVY, bg=_WHITE, relief="flat", bd=2,
             width=10, justify="center",
             validate="key", validatecommand=(vcmd, "%P"),
             insertbackground=_NAVY_MID).pack()

    # ── Divider + button row ──────────────────────────────────────────────
    tk.Frame(dlg, bg=_BORDER_LIGHT, height=1).pack(fill="x", pady=(6, 0))

    btn_row = tk.Frame(dlg, bg=_PAGE_BG)
    btn_row.pack(fill="x", padx=26, pady=12)

    # ── STEP 1: validate + send OTP ───────────────────────────────────────
    def _send_code():
        username = fields["username"].get().strip()
        email    = fields["email"].get().strip()
        password = fields["password"].get().strip()

        if not username or not email or not password:
            messagebox.showwarning("Missing Fields",
                                   "Username, Email and Password are required.",
                                   parent=dlg)
            return

        if not _is_allowed_email(email):
            email_wrap.config(highlightbackground=_ACCENT_RED)
            messagebox.showwarning(
                "Invalid Email Domain",
                "Only @bsv.ph and @bancosanvicente.com addresses are allowed.",
                parent=dlg)
            return

        # Domain OK — reset border colour
        email_wrap.config(highlightbackground=_BORDER_MID)

        code = _generate_code()
        try:
            _send_verification_email(email, code)
        except Exception as e:
            messagebox.showerror("Email Error",
                                 f"Could not send the verification email:\n{e}",
                                 parent=dlg)
            return

        _pending_code["value"] = code

        # Transition UI to Step 2
        send_btn.pack_forget()
        code_var.set("")
        code_section.pack(fill="x", pady=(8, 0))       # show green OTP box
        create_btn.pack(side="right")
        resend_btn.pack(side="right", padx=(0, 8))

    # ── STEP 2: verify OTP then insert into DB ────────────────────────────
    def _create():
        entered = code_var.get().strip()
        if not entered:
            messagebox.showwarning("Enter Code",
                                   "Please enter the verification code.", parent=dlg)
            return

        if entered != _pending_code["value"]:
            code_entry_wrap.config(highlightbackground=_ACCENT_RED)
            messagebox.showerror("Wrong Code",
                                 "The code is incorrect. Try again or click Resend.",
                                 parent=dlg)
            return

        code_entry_wrap.config(highlightbackground=_BORDER_MID)

        username = fields["username"].get().strip()
        email    = fields["email"].get().strip()
        password = fields["password"].get().strip()
        position = fields["position"].get().strip()
        role     = role_var.get().strip().lower()
        status   = status_var.get().strip().lower()

        try:
            conn = self.get_conn()
            cur  = conn.cursor()

            cur.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM users")
            next_id = cur.fetchone()[0]

            cur.execute(
                """INSERT INTO users
                   (id, username, email, password, position, role, status,
                    created_at, updated_at)
                   VALUES (%s, %s, %s, crypt(%s, gen_salt('bf')), %s, %s, %s,
                           NOW(), NOW())""",
                (next_id, username, email, password,
                 position or None, role, status),
            )
            conn.commit()
            cur.close()

            _log_action(self, "add_user",
                        f"Created new user: username='{username}', "
                        f"email='{email}', role='{role}', status='{status}'")

            messagebox.showinfo("Created",
                                f"User '{username}' created successfully.",
                                parent=dlg)
            dlg.destroy()
            _load_users(self)
        except Exception as e:
            messagebox.showerror("DB Error",
                                 f"Could not create user:\n{e}", parent=dlg)

    # ── Resend handler ────────────────────────────────────────────────────
    def _resend():
        email = fields["email"].get().strip()
        code  = _generate_code()
        try:
            _send_verification_email(email, code)
            _pending_code["value"] = code
            code_var.set("")
            code_entry_wrap.config(highlightbackground=_BORDER_MID)
            messagebox.showinfo("Code Resent",
                                "A new verification code has been sent.",
                                parent=dlg)
        except Exception as e:
            messagebox.showerror("Email Error",
                                 f"Could not resend the code:\n{e}", parent=dlg)

    # ── Initial button (Step 1, always visible first) ─────────────────────
    send_btn = ctk.CTkButton(
        btn_row, text="✉  Send Verification Code",
        command=_send_code,
        width=195, height=36, corner_radius=7,
        fg_color=_NAVY_MID, hover_color=_NAVY_LIGHT,
        text_color=_WHITE, font=("Segoe UI", 10, "bold"))
    send_btn.pack(side="right")

    # Step-2 buttons (hidden until code is sent)
    create_btn = ctk.CTkButton(
        btn_row, text="✔  Create User",
        command=_create,
        width=130, height=36, corner_radius=7,
        fg_color=_SB_ACCENT, hover_color="#4CAF35",
        text_color="#0A1628", font=("Segoe UI", 10, "bold"))

    resend_btn = ctk.CTkButton(
        btn_row, text="↺  Resend",
        command=_resend,
        width=90, height=36, corner_radius=7,
        fg_color=_NAVY_MIST, hover_color=_NAVY_GHOST,
        text_color=_TXT_SOFT, font=("Segoe UI", 10))

    # Cancel is always visible on the right
    ctk.CTkButton(btn_row, text="Cancel", command=dlg.destroy,
                  width=90, height=36, corner_radius=7,
                  fg_color=_BORDER_MID, hover_color="#B0C4D8",   # ← more visible
                  text_color=_TXT_NAVY,
                  font=("Segoe UI", 10)).pack(side="left")


# ─────────────────────────────────────────────────────────────────────────────
#  TABLE RENDERING
# ─────────────────────────────────────────────────────────────────────────────

def _render_table(self, *_):
    for w in self._acct_body.winfo_children():
        w.destroy()

    data        = _sorted_data(self)
    page        = max(1, getattr(self, "_acct_page", 1))
    total_pages = max(1, -(-len(data) // _PAGE_SIZE))
    page        = min(page, total_pages)
    self._acct_page = page

    start     = (page - 1) * _PAGE_SIZE
    page_data = data[start: start + _PAGE_SIZE]
    loaded    = min(page * _PAGE_SIZE, len(data))

    self._loaded_lbl.config(text=f"✔  Loaded {loaded} rows")
    total  = len(self._acct_data)
    filt   = len(_filtered(self))
    end    = min(start + _PAGE_SIZE, filt)
    suffix = f" (filtered from {total})" if self._acct_search.get().strip() else ""
    self._count_lbl.config(
        text=f"Page {page}/{total_pages}  ·  {start+1}–{end} of {filt}{suffix}")

    _set_nav(self, page, total_pages)

    if not page_data:
        tk.Label(self._acct_body, text="No users found.",
                 font=("Segoe UI", 11), fg=_TXT_MUTED,
                 bg=_ROW_BG).pack(pady=50)
        return

    for idx, row in enumerate(page_data):
        bg = _ROW_BG if idx % 2 == 0 else _ROW_ALT
        _build_row(self, row, idx, bg)

    filler = tk.Frame(self._acct_body, bg=_ROW_BG)
    filler.pack(fill="both", expand=True)

    self._acct_body.update_idletasks()
    self._acct_canvas.configure(
        scrollregion=self._acct_canvas.bbox("all"))
    self._acct_canvas.yview_moveto(0)


def _build_row(self, row, idx, bg):
    row_frame = tk.Frame(self._acct_body, bg=bg, height=_ROW_H)
    row_frame.pack(fill="x")
    row_frame.pack_propagate(False)

    for col_label, col_key, col_w, col_anchor, sortable in _COLUMNS:
        cell = tk.Frame(row_frame, bg=bg, width=col_w)
        if col_key == "email":
            cell.pack(side="left", fill="both", expand=True)
        elif col_key in ("_edit", "_delete"):
            cell.pack(side="right", fill="y")
        else:
            cell.pack(side="left", fill="y")
        cell.pack_propagate(False)

        val = row.get(col_key)

        if col_key == "_edit":
            ico = tk.Label(cell, text="✏", font=("Segoe UI Emoji", 13),
                           fg=_NAVY_LIGHT, bg=bg, cursor="hand2")
            ico.place(relx=0.5, rely=0.5, anchor="center")
            for w in (ico, cell):
                w.bind("<Button-1>", lambda e, r=row: _open_edit_dialog(self, r))
                w.bind("<Enter>",    lambda e, i=ico: i.config(fg=_SB_ACCENT))
                w.bind("<Leave>",    lambda e, i=ico, c=bg: i.config(fg=_NAVY_LIGHT))

        elif col_key == "_delete":
            ico = tk.Label(cell, text="🗑", font=("Segoe UI Emoji", 13),
                           fg="#CC3333", bg=bg, cursor="hand2")
            ico.place(relx=0.5, rely=0.5, anchor="center")
            for w in (ico, cell):
                w.bind("<Button-1>", lambda e, r=row: _open_delete_dialog(self, r))
                w.bind("<Enter>",    lambda e, i=ico: i.config(fg="#881111"))
                w.bind("<Leave>",    lambda e, i=ico, c=bg: i.config(fg="#CC3333"))

        elif col_key == "role":
            v = str(val).lower() if val else "user"
            fg, pbg, bd = _ROLE_BADGE.get(v, (_TXT_SOFT, "#F0F4F8", _BORDER_MID))
            display_role = str(val).title() if val else "User"
            pill = _pill(cell, display_role, fg, pbg, bd)
            pill.place(relx=0.5, rely=0.5, anchor="center")
            pill._is_badge = True
            for child in _all_children(pill):
                child._is_badge = True

        elif col_key == "status":
            v = str(val).lower() if val else "unknown"
            fg, pbg, bd = _STATUS_BADGE.get(v, (_TXT_SOFT, _NAVY_MIST, _BORDER_MID))
            pill = _pill(cell, v.capitalize(), fg, pbg, bd)
            pill.place(relx=0.5, rely=0.5, anchor="center")
            pill._is_badge = True
            for child in _all_children(pill):
                child._is_badge = True

        elif col_key in ("created_at", "last_login_at"):
            tk.Label(cell, text=_fmt_dt(val), font=("Segoe UI", 9),
                     fg=_TXT_SOFT, bg=bg).place(relx=0.5, rely=0.5, anchor="center")

        elif col_key == "id":
            tk.Label(cell, text=str(val) if val is not None else "—",
                     font=("Segoe UI", 9), fg=_TXT_SOFT,
                     bg=bg).place(relx=0.5, rely=0.5, anchor="center")

        else:
            display  = str(val) if val is not None else "—"
            lbl = tk.Label(cell, text=display, font=("Segoe UI", 9),
               fg=_TXT_NAVY, bg=bg, anchor=col_anchor)
            if col_anchor == "center":
                lbl.place(relx=0.5, rely=0.5, anchor="center")
            else:
                lbl.pack(side="left", padx=(8, 0), fill="y")

    tk.Frame(self._acct_body, bg=_SEP_CLR, height=1).pack(fill="x")

    all_w = _all_children(row_frame)

    def _enter(*_):
        row_frame.config(bg=_ROW_HOV)
        for c in all_w: _safe_bg(c, _ROW_HOV)

    def _leave(*_):
        row_frame.config(bg=bg)
        for c in all_w: _safe_bg(c, bg)

    for w in [row_frame] + all_w:
        w.bind("<Enter>",           _enter)
        w.bind("<Leave>",           _leave)
        w.bind("<Double-Button-1>", lambda e, r=row: _open_edit_dialog(self, r))


# ─────────────────────────────────────────────────────────────────────────────
#  PAGINATION HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _set_nav(self, page, total_pages):
    for btn, enabled in ((self._prev_btn, page > 1),
                          (self._next_btn, page < total_pages)):
        if enabled:
            btn.configure(state="normal",  fg_color=_NAVY_MIST,
                          text_color=_TXT_NAVY, border_color=_BORDER_MID)
        else:
            btn.configure(state="disabled", fg_color="#F0F0F0",
                          text_color=_TXT_MUTED, border_color=_BORDER_LIGHT)


def _go_page(self, delta):
    data        = _sorted_data(self)
    total_pages = max(1, -(-len(data) // _PAGE_SIZE))
    new_page    = getattr(self, "_acct_page", 1) + delta
    if 1 <= new_page <= total_pages:
        self._acct_page = new_page
        _render_table(self)


# ─────────────────────────────────────────────────────────────────────────────
#  PANEL BUILD
# ─────────────────────────────────────────────────────────────────────────────

def _build_accounts_panel(self, parent):
    self._acct_data       = []
    self._acct_page       = 1
    self._acct_search     = tk.StringVar()
    self._acct_sort_col   = "id"
    self._acct_sort_asc   = False
    self._acct_hdr_labels = {}

    self._accounts_frame = tk.Frame(parent, bg=_PAGE_BG)
    frame = self._accounts_frame

    # ── Toolbar ───────────────────────────────────────────────────────────
    toolbar = tk.Frame(frame, bg=_PAGE_BG)
    toolbar.pack(fill="x", padx=20, pady=(14, 6))

    lbl_blk = tk.Frame(toolbar, bg=_PAGE_BG)
    lbl_blk.pack(side="left", fill="y")
    tk.Frame(lbl_blk, bg=_SB_ACCENT, width=3, height=16).pack(
        side="left", padx=(0, 8), pady=2)
    tk.Label(lbl_blk, text="USER ACCOUNTS",
             font=("Segoe UI", 8, "bold"), fg=_TXT_SOFT,
             bg=_PAGE_BG).pack(side="left")

    self._count_lbl = tk.Label(toolbar, text="Loading…",
                                font=("Segoe UI", 8), fg=_TXT_MUTED, bg=_PAGE_BG)
    self._count_lbl.pack(side="left", padx=(14, 0))

    ctk.CTkButton(toolbar, text="➕  Add User",
                  command=lambda: _open_add_dialog(self),
                  width=110, height=30, corner_radius=6,
                  fg_color=_SB_ACCENT, hover_color="#4CAF35",
                  text_color="#0A1628", font=("Segoe UI", 9, "bold"),
                  ).pack(side="right")
    ctk.CTkButton(toolbar, text="⟳  Refresh",
                  command=lambda: _load_users(self),
                  width=90, height=30, corner_radius=6,
                  fg_color=_NAVY_MIST, hover_color=_NAVY_GHOST,
                  text_color=_TXT_SOFT, font=("Segoe UI", 9),
                  border_width=1, border_color=_BORDER_MID,
                  ).pack(side="right", padx=(0, 6))
    ctk.CTkButton(toolbar, text="⚙  Role Tabs",
                  command=lambda: _open_role_tabs_dialog(self),
                  width=100, height=30, corner_radius=6,
                  fg_color=_NAVY_MID, hover_color=_NAVY_LIGHT,
                  text_color=_WHITE, font=("Segoe UI", 9, "bold"),
                  ).pack(side="right", padx=(0, 6))

    # ── Search bar ────────────────────────────────────────────────────────
    sb_row = tk.Frame(frame, bg=_PAGE_BG)
    sb_row.pack(fill="x", padx=20, pady=(0, 8))

    sb_wrap = tk.Frame(sb_row, bg=_WHITE,
                       highlightbackground=_BORDER_MID, highlightthickness=1)
    sb_wrap.pack(side="left", fill="x", expand=True)
    tk.Label(sb_wrap, text="🔍", font=("Segoe UI Emoji", 10),
             bg=_WHITE, fg="#AABDD0").pack(side="left", padx=(10, 2))
    tk.Entry(sb_wrap, textvariable=self._acct_search,
             font=("Segoe UI", 10), fg=_TXT_NAVY, bg=_WHITE,
             relief="flat", bd=0, insertbackground=_NAVY_MID,
             width=36).pack(side="left", fill="x", expand=True, pady=6)
    clr = tk.Label(sb_wrap, text="✕", font=("Segoe UI", 9),
                   fg=_ACCENT_RED, bg=_WHITE, padx=8, cursor="hand2")
    clr.pack(side="right")
    clr.bind("<Button-1>", lambda e: self._acct_search.set(""))

    def _on_search(*_):
        self._acct_page = 1
        _render_table(self)

    self._acct_search.trace_add("write", _on_search)

    # ── Error label ───────────────────────────────────────────────────────
    self._acct_err_var = tk.StringVar()
    self._acct_err_lbl = tk.Label(
        frame, textvariable=self._acct_err_var,
        font=("Segoe UI", 9), fg=_ACCENT_RED, bg=_PAGE_BG, anchor="w")

    # ══ TABLE CARD ════════════════════════════════════════════════════════
    outer = tk.Frame(frame, bg=_BORDER_MID, padx=1, pady=1)
    outer.pack(fill="both", expand=True, padx=20)

    card = tk.Frame(outer, bg=_WHITE)
    card.pack(fill="both", expand=True)

    # ── Column headers (clickable) ────────────────────────────────────────
    hdr_frame = tk.Frame(card, bg=_HDR_BG, height=_HDR_H)
    hdr_frame.pack(fill="x")
    hdr_frame.pack_propagate(False)

    tk.Frame(hdr_frame, bg=_HDR_BG, width=8).pack(side="right", fill="y")
    
    for col_label, col_key, col_w, col_anchor, sortable in _COLUMNS:
        hcell = tk.Frame(hdr_frame, bg=_HDR_BG, width=col_w,
                 cursor="hand2" if sortable else "arrow")
        if col_key == "email":
            hcell.pack(side="left", fill="both", expand=True)
        elif col_key in ("_edit", "_delete"):
            hcell.pack(side="right", fill="y")
        else:
            hcell.pack(side="left", fill="y")
        hcell.pack_propagate(False)

        init_text = _col_header_text(self, col_label, col_key, sortable)

        lbl = tk.Label(hcell, text=init_text,
                       font=("Segoe UI", 9, "bold"),
                       fg=_SB_ACCENT if (col_key == getattr(self, "_acct_sort_col", "id"))
                          else _HDR_FG,
                       bg=_HDR_BG, anchor=col_anchor,
                       cursor="hand2" if sortable else "arrow")
        if col_anchor == "center":
            lbl.place(relx=0.5, rely=0.5, anchor="center")
        else:
            lbl.pack(side="left", padx=(8, 0), fill="y")

        self._acct_hdr_labels[col_key] = lbl

        if sortable:
            def _make_sort_cb(k):
                def _cb(e): _sort_by(self, k)
                return _cb

            cb = _make_sort_cb(col_key)
            lbl.bind("<Button-1>",   cb)
            hcell.bind("<Button-1>", cb)

            def _hdr_enter(e, c=hcell, l=lbl):
                c.config(bg="#243F56")
                l.config(bg="#243F56")

            def _hdr_leave(e, c=hcell, l=lbl):
                c.config(bg=_HDR_BG)
                l.config(bg=_HDR_BG)

            hcell.bind("<Enter>", _hdr_enter)
            hcell.bind("<Leave>", _hdr_leave)
            lbl.bind("<Enter>",   _hdr_enter)
            lbl.bind("<Leave>",   _hdr_leave)

    tk.Frame(card, bg="#263D52", height=1).pack(fill="x")

    # ── Scrollable body ───────────────────────────────────────────────────
    body_wrap = tk.Frame(card, bg=_WHITE)
    body_wrap.pack(fill="both", expand=True)

    vsb = tk.Scrollbar(body_wrap, orient="vertical", relief="flat",
                   troughcolor="#F0F4F8", bg=_BORDER_MID, width=8, bd=0)
    vsb.pack(side="right", fill="y")

    self._acct_canvas = tk.Canvas(body_wrap, bg=_WHITE,
                                   highlightthickness=0,
                                   yscrollcommand=vsb.set)
    self._acct_canvas.pack(side="left", fill="both", expand=True)
    vsb.config(command=self._acct_canvas.yview)

    self._acct_body = tk.Frame(self._acct_canvas, bg=_WHITE)
    _win = self._acct_canvas.create_window(
        (0, 0), window=self._acct_body, anchor="nw")

    self._acct_body.bind(
        "<Configure>",
        lambda e: self._acct_canvas.configure(
            scrollregion=self._acct_canvas.bbox("all")))
    self._acct_canvas.bind(
        "<Configure>",
        lambda e: self._acct_canvas.itemconfig(_win, width=e.width))

    def _wheel(e):
        self._acct_canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")

    self._acct_canvas.bind("<MouseWheel>", _wheel)
    self._acct_body.bind("<MouseWheel>",   _wheel)

    # ══ FOOTER ════════════════════════════════════════════════════════════
    footer = tk.Frame(frame, bg=_WHITE,
                      highlightbackground=_BORDER_MID, highlightthickness=1)
    footer.pack(fill="x", padx=20, pady=(0, 14))

    inner = tk.Frame(footer, bg=_WHITE)
    inner.pack(fill="x", padx=10, pady=6)

    self._prev_btn = ctk.CTkButton(
        inner, text="◀  Prev",
        command=lambda: _go_page(self, -1),
        width=76, height=26, corner_radius=4,
        fg_color=_NAVY_MIST, hover_color=_NAVY_GHOST,
        text_color=_TXT_NAVY, font=("Segoe UI", 8, "bold"),
        border_width=1, border_color=_BORDER_MID)
    self._prev_btn.pack(side="left")

    self._next_btn = ctk.CTkButton(
        inner, text="Next  ▶",
        command=lambda: _go_page(self, +1),
        width=76, height=26, corner_radius=4,
        fg_color=_NAVY_MIST, hover_color=_NAVY_GHOST,
        text_color=_TXT_NAVY, font=("Segoe UI", 8, "bold"),
        border_width=1, border_color=_BORDER_MID)
    self._next_btn.pack(side="left", padx=(6, 0))

    self._loaded_lbl = tk.Label(inner, text="✔  Loaded 0 rows",
                                 font=("Segoe UI", 9), fg=_ACCENT_SUCCESS, bg=_WHITE)
    self._loaded_lbl.pack(side="left", padx=(16, 0))

    tk.Label(inner,
             text="Double-click a row to edit  ·  Passwords stored as bcrypt",
             font=("Segoe UI", 7), fg=_TXT_MUTED, bg=_WHITE).pack(side="right")

    frame.after(120, lambda: _load_users(self))


# ─────────────────────────────────────────────────────────────────────────────
#  ATTACH
# ─────────────────────────────────────────────────────────────────────────────

def attach(cls):
    cls._build_accounts_panel  = _build_accounts_panel
    cls._load_role_tab_config  = _load_role_tab_config
    cls._save_role_tab_config  = _save_role_tab_config
    cls._load_all_roles        = _load_all_roles