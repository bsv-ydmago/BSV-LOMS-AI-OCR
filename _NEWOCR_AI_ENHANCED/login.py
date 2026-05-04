"""
login.py — DocExtract Pro  (Banco San Vicente)
===============================================
Two columns, no gaps. Uses tk.Tk directly (not CTk) so there
are zero internal margins. Left = dark sidebar. Right = white, full fill.
"""
import tkinter as tk

import threading
import time
from dotenv import load_dotenv
import os
from PIL import Image, ImageTk
import psycopg2
import threading
import time
from dotenv import load_dotenv
import os
from PIL import Image, ImageTk
import psycopg2
import json

# ── Palette ────────────────────────────────────────────────────────────────────
APP_BG         = "#0F1520"
APP_BG_MID     = "#161E30"
APP_BG_HOVER   = "#1C2640"
APP_BORDER     = "#1E2A42"
HEADER_BG      = "#0A1018"
WHITE          = "#FFFFFF"
BSV_GREEN      = "#8DC63F"
BSV_GREEN_D    = "#6FA030"
TEXT_MED_LIGHT = "#8A9BBF"
TEXT_DIM       = "#4A5878"
TEXT_DARK      = "#0F1733"
TEXT_MED       = "#3A4A6A"
TEXT_SOFT      = "#6A7A9A"
TEXT_HINT      = "#A0AABF"
TEXT_LIGHT     = "#E8EDF5"
DIVIDER        = "#1E2A42"
DIVIDER_LIGHT  = "#E0E6F0"
ERROR          = "#E0405A"
INPUT_BG       = "#F8FAFE"
INPUT_BORDER   = "#D0D8EC"

FUI  = "Segoe UI"
FMONO = "Consolas"

load_dotenv()

# ── Database config ────────────────────────────────────────────────────────────
DB_CONFIG = {
    "host":     os.getenv("DB_HOST", "localhost"),
    "port":     int(os.getenv("DB_PORT", 5432)),
    "dbname":   os.getenv("DB_NAME", "docextract_db"),
    "user":     os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", ""),
}

_REMEMBER_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".remember_me")

def _save_remembered(email: str):
    try:
        with open(_REMEMBER_FILE, "w") as f:
            json.dump({"email": email}, f)
    except Exception:
        pass

def _load_remembered() -> str:
    try:
        with open(_REMEMBER_FILE, "r") as f:
            return json.load(f).get("email", "")
    except Exception:
        return ""

def _clear_remembered():
    try:
        os.remove(_REMEMBER_FILE)
    except Exception:
        pass

def db_check_login(email: str, password: str):
    """Returns (id, display_name) tuple if credentials match, else None."""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur  = conn.cursor()
        cur.execute(
            "SELECT id, username, status FROM users WHERE email = %s "  # ← add status
            "AND password = crypt(%s, password)",
            (email, password)
        )
        row = cur.fetchone()
        if row:
            user_id, username, status = row  # ← unpack status

            # ── Check account status first ─────────────────────────────
            if status != 'active':
                cur.close()
                conn.close()
                return "INACTIVE"
            # ──────────────────────────────────────────────────────────

            # ── Check if already logged in ─────────────────────────────
            cur.execute(
                "SELECT is_logged_in FROM public.users WHERE id = %s",
                (user_id,)
            )
            status = cur.fetchone()
            if status and status[0]:  # is_logged_in is True
                cur.close()
                conn.close()
                return "ALREADY_LOGGED_IN"
            # ──────────────────────────────────────────────────────────

            cur.execute(
                "UPDATE public.users SET is_logged_in = TRUE WHERE id = %s",
                (user_id,)
            )
            cur.execute(
                "UPDATE public.users SET last_login_at = NOW() WHERE id = %s",
                (user_id,)
            )
            cur.execute(
                """
                INSERT INTO logs (user_id, email, action, description, time)
                VALUES (%s, %s, %s, %s, NOW())
                """,
                (
                    user_id,
                    username,
                    "LOGGED IN",
                    f"User '{username}' ({email}) successfully logged in to DocExtract Pro.",
                )
            )

            conn.commit()
            row = (user_id, username)

        cur.close()
        conn.close()
        return row
    except Exception as ex:
        print(f"DB error: {ex}")
        return None

# ══════════════════════════════════════════════════════════════════════════════
class LeftCanvas(tk.Canvas):
    def __init__(self, parent, **kw):
        super().__init__(parent, bg=APP_BG, highlightthickness=0, bd=0, **kw)
        self.bind("<Configure>", self._draw)

    def _draw(self, e=None):
        self.delete("all")
        w = e.width  if e else self.winfo_width()
        h = e.height if e else self.winfo_height()
        if w < 2 or h < 2:
            return
        for gy in range(0, h, 40):
            self.create_line(0, gy, w, gy, fill=APP_BORDER)
        for gx in range(0, w, 40):
            self.create_line(gx, 0, gx, h, fill=APP_BORDER)
        cx, cy = w // 2, int(h * 0.88)
        for r in range(150, 0, -20):
            g = int(0x30 * (150 - r) / 150)
            col = f"#{max(0x0F, 0x0F+g):02x}{max(0x15, 0x15+g):02x}20"
            self.create_oval(cx-r, cy-r, cx+r, cy+r, fill=col, outline="")
        self.create_rectangle(0, int(h*.47), 3, int(h*.57),
                              fill=BSV_GREEN, outline="")


# ══════════════════════════════════════════════════════════════════════════════
class LoginWindow(tk.Tk):
    W  = 860
    H  = 540
    PW = 260
    TH = 28

    def __init__(self, on_success):
        super().__init__()
        self._ok      = on_success
        self._busy    = False
        self._logo    = None
        self._eyebtn  = None
        self._ticking = False
        self._after_id = None

        self.title("DocExtract Pro")
        self.configure(bg=HEADER_BG)
        self.resizable(False, False)
        self.overrideredirect(True)

        # Hide first, center after fully mapped
        self.withdraw()
        self._dx = self._dy = 0
        self._build()
        self.bind_all("<Return>", lambda _: self._login())

        # ── Load remembered email ─────────────────────────────────────
        remembered = _load_remembered()
        if remembered:
            self._remember_var.set(True)
            # Pre-fill the email field
            self._ue.delete(0, "end")
            self._ue.config(fg=TEXT_DARK, show="")
            self._ue.insert(0, remembered)

        self.after(10, self._center_and_show)

        # Center after window is fully rendered
        self.after(10, self._center_and_show)

    def _center_and_show(self):
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x  = (sw - self.W) // 2
        y  = (sh - self.H) // 2
        self.geometry(f"{self.W}x{self.H}+{x}+{y}")
        self.deiconify()
        self.lift()
        self.focus_force()

    # ── Layout ─────────────────────────────────────────────────────────────
    def _build(self):
        TH = self.TH
        BH = self.H - TH      # body height
        PW = self.PW
        RW = self.W - PW      # right panel width

        # ── Title bar ──────────────────────────────────────────────────────
        bar = tk.Frame(self, bg=HEADER_BG)
        bar.place(x=0, y=0, width=self.W, height=TH)
        bar.bind("<ButtonPress-1>", self._ds)
        bar.bind("<B1-Motion>",     self._dm)

        tk.Label(bar, text="  ◈  DocExtract Pro",
                 bg=HEADER_BG, fg=TEXT_DIM,
                 font=(FMONO, 8)).place(x=6, y=6)

        vf = tk.Frame(bar, bg="#1C2640", padx=6, pady=1)
        vf.place(x=PW - 36, y=4)
        tk.Label(vf, text="v2.0", bg="#1C2640", fg=BSV_GREEN,
                 font=(FMONO, 7)).pack()

        for txt, cmd, xoff, hov in [
            ("✕", self.destroy, -18, ERROR),
            ("—", self.iconify, -42, TEXT_MED_LIGHT),
        ]:
            b = tk.Button(bar, text=txt, bg=HEADER_BG, fg=TEXT_DIM,
                          bd=0, cursor="hand2", font=(FUI, 8),
                          activebackground=HEADER_BG, activeforeground=hov,
                          command=cmd)
            b.place(relx=1.0, x=xoff, y=5, anchor="ne")

        # ── Left column ────────────────────────────────────────────────────
        LeftCanvas(self).place(x=0, y=TH, width=PW, height=BH)
        brand = tk.Frame(self, bg=APP_BG)
        brand.place(x=0, y=TH, width=PW, height=BH)
        brand.lift()
        self._left(brand, PW, BH)

        # ── Right column — white, pixel-perfect fill ────────────────────────
        right = tk.Frame(self, bg=WHITE)
        right.place(x=PW, y=TH, width=RW, height=BH)
        self._right(right, RW, BH)

        # divider
        tk.Frame(self, bg=DIVIDER).place(x=PW, y=TH, width=1, height=BH)

    # ── Left brand ─────────────────────────────────────────────────────────
    def _left(self, parent, pw, bh):
        P = 20
        f = tk.Frame(parent, bg=APP_BG)
        f.place(x=P, y=P, width=pw - P*2, height=bh - P*2)

        # ── Logo icon (bsv_logo.png) beside bank name ──────────────────────
        row = tk.Frame(f, bg=APP_BG)
        row.pack(anchor="w", pady=(0, 10))

        base = os.path.dirname(os.path.abspath(__file__))
        self._logo = None
        for lp in [os.path.join(base, "image", "bsv_logo.png"),
                   "image/bsv_logo.png", "logo_bsv.png"]:
            if os.path.exists(lp):
                try:
                    img = Image.open(lp).convert("RGBA")
                    img.putdata([
                        (r, g, b, 0) if r > 210 and g > 210 and b > 210
                        else (r, g, b, a)
                        for r, g, b, a in img.getdata()
                    ])
                    ih = 30                            # icon height in px (smaller)
                    iw = int(img.width * ih / img.height)
                    img = img.resize((iw, ih), Image.LANCZOS)
                    self._logo = ImageTk.PhotoImage(img)
                    tk.Label(row, image=self._logo, bg=APP_BG, bd=0
                             ).pack(side="left", padx=(0, 8))
                    break
                except Exception as ex:
                    print(f"Logo: {ex}")

        if self._logo is None:
            # Fallback square icon if file missing
            c = tk.Canvas(row, width=24, height=24, bg=APP_BG,
                          highlightthickness=0)
            c.pack(side="left", padx=(0, 8))
            c.create_rectangle(2, 2, 22, 22, fill=BSV_GREEN, outline="")
            c.create_rectangle(7, 7, 17, 17, fill=APP_BG, outline="")

        nf = tk.Frame(row, bg=APP_BG)
        nf.pack(side="left")
        tk.Label(nf, text="BANCO SAN VICENTE",
                 bg=APP_BG, fg=TEXT_LIGHT,
                 font=(FUI, 8, "bold")).pack(anchor="w")
        tk.Label(nf, text="A Rural Bank",
                 bg=APP_BG, fg=BSV_GREEN,
                 font=(FUI, 7)).pack(anchor="w")

        tk.Frame(f, bg=DIVIDER, height=1).pack(fill="x", pady=(0, 12))

        tk.Label(f,
                 text="Intelligent document\nextraction & financial\nanalysis platform.",
                 bg=APP_BG, fg=TEXT_MED_LIGHT,
                 font=(FUI, 8), justify="left").pack(anchor="w")

        pip = tk.Frame(f, bg=APP_BG_MID,
                       highlightbackground=APP_BORDER, highlightthickness=1)
        pip.pack(anchor="w", fill="x", pady=(14, 0))
        pi = tk.Frame(pip, bg=APP_BG_MID)
        pi.pack(anchor="w", padx=8, pady=6)
        tk.Label(pi, text="Pipeline",
                 bg=APP_BG_MID, fg=TEXT_DIM,
                 font=(FMONO, 6)).pack(anchor="w")
        tk.Label(pi, text="PaddleOCR  →  Gemini 2.5 Flash  →  CIBI",
                 bg=APP_BG_MID, fg=TEXT_MED_LIGHT,
                 font=(FMONO, 6)).pack(anchor="w", pady=(2, 0))

        sr = tk.Frame(f, bg=APP_BG)
        sr.pack(anchor="w", pady=(10, 0))
        c2 = tk.Canvas(sr, width=7, height=7, bg=APP_BG, highlightthickness=0)
        c2.pack(side="left", padx=(0, 5))
        c2.create_oval(1, 1, 6, 6, fill=BSV_GREEN, outline="")
        tk.Label(sr, text="System Ready", bg=APP_BG, fg=BSV_GREEN,
                 font=(FMONO, 8)).pack(side="left")

        tk.Label(f, text="v2.4.1  ·  Internal Release",
                 bg=APP_BG, fg=TEXT_DIM,
                 font=(FMONO, 7)).pack(anchor="w", side="bottom")

    # ── Right form ─────────────────────────────────────────────────────────
    def _right(self, parent, rw, bh):
        tk.Frame(parent, bg=BSV_GREEN).place(x=0, y=0, width=rw, height=3)

        PAD = int(rw * 0.08)
        FW  = rw - PAD * 2
        FH  = 360
        FY  = max(10, (bh - FH) // 2)

        f = tk.Frame(parent, bg=WHITE)
        f.place(x=PAD, y=FY, width=FW, height=FH)

        tk.Label(f, text="Welcome back",
                 bg=WHITE, fg=TEXT_DARK,
                 font=(FUI, 18, "bold")).pack(anchor="w")
        tk.Label(f, text="Sign in to your DocExtract Pro account",
                 bg=WHITE, fg=TEXT_SOFT,
                 font=(FUI, 8)).pack(anchor="w", pady=(3, 18))

        self._ue = self._field(f, "EMAIL ADDRESS",
                               "e.g.  juan@bancosanvicente.com")
        tk.Frame(f, bg=WHITE, height=8).pack()
        self._pe = self._field(f, "PASSWORD",
                               "Enter your password", secret=True)

        fr = tk.Frame(f, bg=WHITE)
        fr.pack(fill="x", pady=(6, 10))

        # ── Remember Me — same row as Forgot password ─────────────────
        self._remember_var = tk.BooleanVar(value=False)
        tk.Checkbutton(fr, text="Remember me",
                       variable=self._remember_var,
                       bg=WHITE, fg=TEXT_SOFT,
                       font=(FUI, 8),
                       activebackground=WHITE,
                       selectcolor=WHITE,
                       cursor="hand2").pack(side="left")

        self._errlbl = tk.Label(f, text="", bg=WHITE, fg=ERROR,
                                font=(FUI, 8))
        self._errlbl.pack(anchor="w", pady=(0, 6))

        self._btn = tk.Button(f, text="Sign In  →",
                              bg=APP_BG, fg=WHITE,
                              font=(FUI, 10, "bold"),
                              bd=0, cursor="hand2", relief="flat",
                              activebackground=APP_BG_HOVER,
                              activeforeground=WHITE,
                              command=self._login)
        self._btn.pack(fill="x")
        self._btn.configure(height=3)
        self._btn.bind("<Enter>",
            lambda _: self._btn.config(bg=APP_BG_HOVER)
            if not self._busy else None)
        self._btn.bind("<Leave>",
            lambda _: self._btn.config(bg=APP_BG)
            if not self._busy else None)

    # ── Field ──────────────────────────────────────────────────────────────
    def _field(self, parent, label, ph="", secret=False):
        tk.Label(parent, text=label, bg=WHITE, fg=TEXT_SOFT,
                 font=(FMONO, 7, "bold")).pack(anchor="w")

        wrap = tk.Frame(parent, bg=INPUT_BG,
                        highlightbackground=INPUT_BORDER, highlightthickness=1)
        wrap.pack(fill="x", pady=(4, 0))

        e = tk.Entry(wrap, bg=INPUT_BG, fg=TEXT_HINT,
                     insertbackground=APP_BG, relief="flat", bd=0,
                     font=(FUI, 9))
        e.pack(side="left", fill="x", expand=True, padx=(10, 5), pady=10)
        e.insert(0, ph)

        def _in(ev, ent=e, w=wrap, p=ph, sec=secret):
            if ent.cget("fg") == TEXT_HINT:
                ent.delete(0, "end")
                ent.config(fg=TEXT_DARK, show="•" if sec else "")
            w.config(highlightbackground=BSV_GREEN, highlightthickness=2)

        def _out(ev, ent=e, w=wrap, p=ph):
            if ent.get() == "":
                ent.config(fg=TEXT_HINT, show="", bg=INPUT_BG)
                ent.insert(0, p)
            w.config(highlightbackground=INPUT_BORDER, highlightthickness=1)

        e.bind("<FocusIn>",  _in)
        e.bind("<FocusOut>", _out)

        if secret:
            base = os.path.dirname(os.path.abspath(__file__))
            self._img_eye_open = self._img_eye_hide = None
            for name, attr in [("open_eye.png",  "_img_eye_open"),
                                ("eye_hide.png",  "_img_eye_hide")]:
                for lp in [os.path.join(base, "image", name), f"image/{name}"]:
                    if os.path.exists(lp):
                        try:
                            im = Image.open(lp).convert("RGBA")
                            ih = 16
                            iw = int(im.width * ih / im.height)
                            im = im.resize((iw, ih), Image.LANCZOS)
                            setattr(self, attr, ImageTk.PhotoImage(im))
                        except Exception as ex:
                            print(f"Eye icon {name}: {ex}")
                        break

            eye_kw = dict(bg=INPUT_BG, bd=0, cursor="hand2",
                          activebackground=INPUT_BG,
                          command=lambda ent=e: self._eye(ent))
            if self._img_eye_hide:
                self._eyebtn = tk.Button(wrap, image=self._img_eye_hide,
                                         **eye_kw)
            else:
                self._eyebtn = tk.Button(wrap, text="👁", fg=TEXT_SOFT,
                                         font=(FUI, 10), **eye_kw)
            self._eyebtn.pack(side="right", padx=(0, 8))

        return e

    def _eye(self, e):
        if e.cget("fg") == TEXT_HINT:
            return
        hidden = e.cget("show") == "•"
        e.config(show="" if hidden else "•")
        if self._eyebtn:
            if hidden and self._img_eye_open:
                self._eyebtn.config(image=self._img_eye_open)
            elif not hidden and self._img_eye_hide:
                self._eyebtn.config(image=self._img_eye_hide)
            else:
                self._eyebtn.config(
                    text="👁", fg=TEXT_DARK if hidden else TEXT_HINT)

    def _val(self, e):
        return "" if e.cget("fg") == TEXT_HINT else e.get().strip()

    def _login(self):
        if self._busy:
            return
        u = self._val(self._ue)
        p = self._val(self._pe)
        if not u or not p:
            self._errlbl.config(text="⚠  Please enter your credentials.")
            return
        self._errlbl.config(text="")
        self._busy = True
        self._btn.config(text="Authenticating…", state="disabled",
                         bg="#1C2640", fg=TEXT_MED_LIGHT)
        self._ticking = True
        self._tick(0)

        def _auth():
            result = db_check_login(u, p)
            self.after(0, lambda: self._done(result))

        threading.Thread(target=_auth, daemon=True).start()

    def _tick(self, n):
        if not self._ticking:
            return
        dots = ["·", "· ·", "· · ·", ""]
        try:
            self._btn.config(text=f"Authenticating {dots[n%4]}")
        except Exception:
            pass
        self._after_id = self.after(320, lambda: self._tick(n + 1))

    def _done(self, result):
        self._ticking = False
        self._busy = False
        if self._after_id:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
        self._btn.config(text="Sign In  →", state="normal",
                         bg=APP_BG, fg=WHITE)
        if result == "ALREADY_LOGGED_IN":
            self._show_popup("Account is already logged in.\nReport to administrator if this is a mistake.")
        elif result == "INACTIVE":
            self._show_popup("Your account is inactive.\nPlease contact the administrator.")
        elif result:
            user_id, username = result
            # ── Save or clear remembered email ────────────────────────
            if self._remember_var.get():
                _save_remembered(self._val(self._ue))
            else:
                _clear_remembered()
            # ─────────────────────────────────────────────────────────
            self.destroy()
            self._ok(user_id, username)
        else:
            self._errlbl.config(
                text="⚠  Incorrect username or password.")
    
    def _show_popup(self, message: str):
        popup = tk.Toplevel(self)
        popup.title("")
        popup.configure(bg=APP_BG)
        popup.resizable(False, False)
        popup.overrideredirect(True)

        pw, ph = 350, 150
        x = self.winfo_x() + (self.W - pw) // 2
        y = self.winfo_y() + (self.H - ph) // 2
        popup.geometry(f"{pw}x{ph}+{x}+{y}")

        tk.Frame(popup, bg=ERROR, height=3).pack(fill="x")
        tk.Label(popup, text="⚠  Access Denied",
                 bg=APP_BG, fg=ERROR,
                 font=(FUI, 10, "bold")).pack(pady=(14, 4))
        tk.Label(popup, text=message,
                 bg=APP_BG, fg=TEXT_MED_LIGHT,
                 font=(FUI, 9)).pack()
        tk.Button(popup, text="OK", bg=APP_BG_HOVER, fg=WHITE,
                  font=(FUI, 9, "bold"), bd=0, cursor="hand2",
                  width=10, command=popup.destroy).pack(pady=14)

        popup.grab_set()
        popup.lift()

    def _ds(self, e):
        self._dx = e.x_root - self.winfo_x()
        self._dy = e.y_root - self.winfo_y()

    def _dm(self, e):
        self.geometry(f"+{e.x_root-self._dx}+{e.y_root-self._dy}")


# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    LoginWindow(on_success=lambda: print("Logged in")).mainloop()