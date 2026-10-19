#!/usr/bin/env python3
"""
Expense Tracker - Glass Edition
-------------------------------
A frosted-glass interface (translucent panels floating over a glowing gradient)
that opens in its own window.

Needs:  pip install pillow        (Tkinter already ships with Python)
Data:   expenses.json next to this script (same file the other versions use)
"""

import csv
import json
import sys
import tkinter as tk
from datetime import date, datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter import font as tkfont

try:
    from  PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps, ImageTk
except ImportError:
    _root = tk.Tk()
    _root.withdraw()
    messagebox.showerror(
        "Pillow is required",
        "The glass theme needs the Pillow imaging library.\n\n"
        "Install it by running this in a terminal:\n\n    pip install pillow\n\n"
        "then start the app again.")
    sys.exit(1)

# ---------------------------------------------------------------- settings
DATA_FILE = Path(__file__).with_name("expenses.json")
DATE_FORMAT = "%Y-%m-%d"
CURRENCY = "৳"  # change to "$", "€", "₹" ...
DEFAULT_CATEGORIES = ["Food", "Transport", "Bills", "Shopping",
                      "Health", "Education", "Entertainment", "Other"]

# ---------------------------------------------------------------- colours
WINDOW_BG = "#0b0f2e"
TEXT = "#f3f4ff"
MUTED = "#aeb0dc"
ACCENT = "#8b7cff"
ACCENT_HOVER = "#a398ff"
DANGER = "#ff5d7a"
DANGER_HOVER = "#ff8097"
GHOST = "#3b3a82"
GHOST_HOVER = "#4c4a9a"
FIELD_BG = "#1f1d4b"
FIELD_BORDER = "#5551a3"
TREE_BG = "#211f4f"
TREE_ALT = "#292660"
TREE_SEL = "#4d46bf"
TREE_HEAD = "#37338f"
TRACK = "#3c3980"
CHART_COLORS = ["#8b7cff", "#38d6f5", "#34e0a1", "#ffc857", "#ff6b8b", "#c084fc"]

# glowing colour blobs behind the glass: (x, y, radius) as fractions of the width, colour, alpha
ORBS = [
    (0.10, 0.15, 0.20, (124, 92, 255), 170),
    (0.88, 0.10, 0.18, (40, 205, 245), 140),
    (0.78, 0.88, 0.24, (255, 80, 160), 130),
    (0.15, 0.92, 0.20, (45, 220, 160), 110),
    (0.48, 0.55, 0.16, (90, 100, 255), 90),
]

RS = getattr(Image, "Resampling", Image)  # works on old and new Pillow


def money(value):
    return f"{CURRENCY}{value:,.2f}"


# ================================================================ glass rendering
def compute_layout(W, H):
    """Rectangles (x, y, w, h) of every glass panel for a window of W x H."""
    M, G = 24, 14
    layout = {"header": (M, 16, W - 2 * M, 62)}
    y = 16 + 62 + G
    card_h = 86
    card_w = (W - 2 * M - 3 * G) / 4
    layout["stats"] = [(int(M + i * (card_w + G)), y, int(card_w), card_h) for i in range(4)]
    body_y = y + card_h + G
    body_h = H - M - body_y
    left_w, form_h, bar_h = 330, 296, 58
    layout["form"] = (M, body_y, left_w, form_h)
    layout["chart"] = (M, body_y + form_h + G, left_w, body_h - form_h - G)
    rx = M + left_w + G
    rw = W - M - rx
    layout["toolbar"] = (rx, body_y, rw, bar_h)
    layout["table"] = (rx, body_y + bar_h + G, rw, body_h - bar_h - G)
    return layout


def _rounded_mask(w, h, r, scale=3):
    mask = Image.new("L", (w * scale, h * scale), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w * scale - 1, h * scale - 1),
                                           radius=r * scale, fill=255)
    return mask.resize((w, h), RS.LANCZOS)


def _vertical_ramp(w, h):
    """0 at the top -> 255 at the bottom."""
    return Image.linear_gradient("L").resize((w, h), RS.BILINEAR)


def _orb(W, H, cx, cy, r, color, alpha):
    s = 4  # work at 1/4 size: much faster, and the blur hides the difference
    layer = Image.new("RGBA", (W // s, H // s), color + (0,))
    ImageDraw.Draw(layer).ellipse((cx / s - r / s, cy / s - r / s, cx / s + r / s, cy / s + r / s),
                                  fill=color + (alpha,))
    layer = layer.filter(ImageFilter.GaussianBlur(r / s * 0.55))
    return layer.resize((W, H), RS.BICUBIC)


def _glass_panel(clean, target, x, y, w, h, r):
    """Frost the part of `clean` under the panel and paste it onto `target`."""
    box = (x, y, x + w, y + h)
    frosted = clean.crop(box).filter(ImageFilter.GaussianBlur(8))
    # smoked-glass tint keeps the text readable over the bright glow
    frosted = Image.blend(frosted, Image.new("RGB", (w, h), (16, 18, 58)), 0.34)
    # white sheen: stronger at the top, fading towards the bottom
    sheen = _vertical_ramp(w, h).point(lambda p: int(50 - p * 0.15))
    frosted = Image.composite(Image.new("RGB", (w, h), (240, 244, 255)), frosted, sheen)
    target.paste(frosted, (x, y), _rounded_mask(w, h, r))

    # thin light edge, brighter on top
    s = 3
    edge = Image.new("L", (w * s, h * s), 0)
    ImageDraw.Draw(edge).rounded_rectangle((0, 0, w * s - 1, h * s - 1), radius=r * s,
                                           outline=255, width=s)
    edge = edge.resize((w, h), RS.LANCZOS)
    fade = _vertical_ramp(w, h).point(lambda p: int(175 - p * 0.5))
    target.paste((255, 255, 255), box, ImageChops.multiply(edge, fade))


def render_glass_background(W, H, panels):
    """Gradient + glowing orbs, with frosted glass panels [(x, y, w, h, radius), ...]."""
    ramp_v = _vertical_ramp(W, H)
    ramp_h = Image.linear_gradient("L").rotate(90).resize((W, H), RS.BILINEAR)
    t = Image.blend(ramp_h, ramp_v, 0.45)
    bg = ImageOps.colorize(t, black=(9, 12, 42), mid=(40, 20, 96), white=(12, 58, 104)).convert("RGBA")
    for fx, fy, fr, color, alpha in ORBS:
        bg = Image.alpha_composite(bg, _orb(W, H, fx * W, fy * H, fr * W, color, alpha))
    clean = bg.convert("RGB")

    # soft drop shadows under the panels
    shadow = Image.new("L", (W, H), 0)
    sd = ImageDraw.Draw(shadow)
    for x, y, w, h, r in panels:
        sd.rounded_rectangle((x, y + 10, x + w, y + h + 10), radius=r, fill=120)
    shadow = shadow.filter(ImageFilter.GaussianBlur(14))
    out = Image.composite(Image.new("RGB", (W, H), (4, 5, 22)), clean, shadow)

    for x, y, w, h, r in panels:
        _glass_panel(clean, out, x, y, w, h, r)
    return out


# ================================================================ application
class ExpenseTracker(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Expense Tracker")
        self.geometry("1180x780")
        self.minsize(1060, 720)
        self.configure(bg=WINDOW_BG)

        families = set(tkfont.families(self))
        self.font = next((f for f in ("Segoe UI", "SF Pro Text", "Helvetica Neue", "Ubuntu",
                                      "DejaVu Sans") if f in families), "Helvetica")

        self.expenses = self.load_expenses()
        self.editing_id = None
        self.layout = None
        self.bg_photo = None
        self._last_size = None
        self._resize_job = None

        self.setup_styles()
        self.canvas = tk.Canvas(self, bg=WINDOW_BG, highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)
        self.bg_item = self.canvas.create_image(0, 0, anchor="nw")
        self.create_widgets()
        self.refresh()

        self.canvas.bind("<Configure>", self.on_resize)
        self.bind("<Escape>", lambda e: self.clear_form())

    # ------------------------------------------------------------ data
    def load_expenses(self):
        if DATA_FILE.exists():
            try:
                with open(DATA_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                messagebox.showwarning("Data file", "Could not read expenses.json. Starting fresh.")
        return []

    def save_expenses(self):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(self.expenses, f, indent=2)

    def next_id(self):
        return max((e["id"] for e in self.expenses), default=0) + 1

    # ------------------------------------------------------------ styling
    def setup_styles(self):
        F = self.font
        s = ttk.Style(self)
        s.theme_use("clam")

        s.configure("Glass.TEntry", fieldbackground=FIELD_BG, foreground=TEXT, insertcolor=TEXT,
                    bordercolor=FIELD_BORDER, lightcolor=FIELD_BORDER, darkcolor=FIELD_BORDER,
                    padding=(8, 5), font=(F, 10))
        s.map("Glass.TEntry", bordercolor=[("focus", ACCENT)], lightcolor=[("focus", ACCENT)],
              darkcolor=[("focus", ACCENT)])

        s.configure("Glass.TCombobox", fieldbackground=FIELD_BG, background=GHOST, foreground=TEXT,
                    arrowcolor=TEXT, insertcolor=TEXT, bordercolor=FIELD_BORDER,
                    lightcolor=FIELD_BORDER, darkcolor=FIELD_BORDER, padding=(8, 5),
                    selectbackground=FIELD_BG, selectforeground=TEXT, font=(F, 10))
        s.map("Glass.TCombobox",
              fieldbackground=[("readonly", FIELD_BG)], foreground=[("readonly", TEXT)],
              selectbackground=[("readonly", FIELD_BG)], selectforeground=[("readonly", TEXT)],
              bordercolor=[("focus", ACCENT)], lightcolor=[("focus", ACCENT)],
              darkcolor=[("focus", ACCENT)], background=[("active", GHOST_HOVER)])
        # drop-down list of the comboboxes
        self.option_add("*TCombobox*Listbox.background", FIELD_BG)
        self.option_add("*TCombobox*Listbox.foreground", TEXT)
        self.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
        self.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")
        self.option_add("*TCombobox*Listbox.font", f"{{{F}}} 10")

        for name, bg, hover, fg in (("Accent", ACCENT, ACCENT_HOVER, "#ffffff"),
                                    ("Danger", DANGER, DANGER_HOVER, "#ffffff"),
                                    ("Ghost", GHOST, GHOST_HOVER, TEXT)):
            s.configure(f"{name}.TButton", background=bg, foreground=fg, bordercolor=bg,
                        lightcolor=bg, darkcolor=bg, borderwidth=0, focusthickness=0,
                        focuscolor=bg, relief="flat", font=(F, 10, "bold"), padding=(10, 6))
            s.map(f"{name}.TButton",
                  background=[("active", hover), ("pressed", hover)],
                  bordercolor=[("active", hover)], lightcolor=[("active", hover)],
                  darkcolor=[("active", hover)])

        s.configure("Glass.Treeview", background=TREE_BG, fieldbackground=TREE_BG, foreground=TEXT,
                    rowheight=32, borderwidth=0, relief="flat", font=(F, 10))
        s.map("Glass.Treeview", background=[("selected", TREE_SEL)],
              foreground=[("selected", "#ffffff")])
        s.configure("Glass.Treeview.Heading", background=TREE_HEAD, foreground="#ffffff",
                    font=(F, 10, "bold"), padding=8, borderwidth=0, relief="flat")
        s.map("Glass.Treeview.Heading", background=[("active", TREE_SEL)])

        s.configure("Glass.Vertical.TScrollbar", background="#5a56a8", troughcolor=TREE_BG,
                    bordercolor=TREE_BG, lightcolor="#5a56a8", darkcolor="#5a56a8",
                    arrowcolor=TEXT, relief="flat")
        s.map("Glass.Vertical.TScrollbar", background=[("active", "#7773c4")])

    # ------------------------------------------------------------ widgets
    def create_widgets(self):
        c = self.canvas

        # add / edit form
        self.amount_var = tk.StringVar()
        self.category_var = tk.StringVar()
        self.date_var = tk.StringVar(value=date.today().strftime(DATE_FORMAT))
        self.desc_var = tk.StringVar()
        self.amount_entry = ttk.Entry(c, textvariable=self.amount_var, style="Glass.TEntry")
        self.date_entry = ttk.Entry(c, textvariable=self.date_var, style="Glass.TEntry")
        self.category_box = ttk.Combobox(c, textvariable=self.category_var, style="Glass.TCombobox",
                                         values=self.all_categories())
        self.desc_entry = ttk.Entry(c, textvariable=self.desc_var, style="Glass.TEntry")
        self.submit_btn = ttk.Button(c, text="Add Expense", style="Accent.TButton",
                                     command=self.submit, cursor="hand2")
        self.clear_btn = ttk.Button(c, text="Clear", style="Ghost.TButton",
                                    command=self.clear_form, cursor="hand2")
        for w in (self.amount_entry, self.date_entry, self.category_box, self.desc_entry):
            w.bind("<Return>", lambda e: self.submit())

        # toolbar
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self.refresh_table())
        self.search_entry = ttk.Entry(c, textvariable=self.search_var, style="Glass.TEntry")
        self.filter_var = tk.StringVar(value="All categories")
        self.filter_box = ttk.Combobox(c, textvariable=self.filter_var, state="readonly",
                                       style="Glass.TCombobox", values=["All categories"])
        self.filter_box.bind("<<ComboboxSelected>>", lambda e: self.refresh_table())
        self.delete_btn = ttk.Button(c, text="Delete", style="Danger.TButton",
                                     command=self.delete_selected, cursor="hand2")
        self.export_btn = ttk.Button(c, text="Export CSV", style="Ghost.TButton",
                                     command=self.export_csv, cursor="hand2")

        # table
        self.tree = ttk.Treeview(c, columns=("date", "category", "description", "amount"),
                                 show="headings", selectmode="browse", style="Glass.Treeview")
        for col, text, width, anchor, stretch in (("date", "Date", 110, "w", False),
                                                  ("category", "Category", 140, "w", False),
                                                  ("description", "Description", 220, "w", True),
                                                  ("amount", "Amount", 130, "e", False)):
            self.tree.heading(col, text=text, anchor=anchor)
            self.tree.column(col, width=width, anchor=anchor, stretch=stretch)
        self.tree.tag_configure("alt", background=TREE_ALT)
        self.scroll = ttk.Scrollbar(c, orient="vertical", command=self.tree.yview,
                                    style="Glass.Vertical.TScrollbar")
        self.tree.configure(yscrollcommand=self.scroll.set)
        self.tree.bind("<<TreeviewSelect>>", self.on_select)
        self.tree.bind("<Delete>", lambda e: self.delete_selected())

    @staticmethod
    def put(widget, rect):
        x, y, w, h = rect
        widget.place(x=x, y=y, width=w, height=h)

    def form_rects(self):
        x, y, w, h = self.layout["form"]
        pad = 18
        cw = w - 2 * pad
        half = (cw - 10) // 2
        return {
            "amount": (x + pad, y + 62, half, 32),
            "date": (x + pad + half + 10, y + 62, cw - half - 10, 32),
            "category": (x + pad, y + 120, cw, 32),
            "description": (x + pad, y + 178, cw, 32),
            "submit": (x + pad, y + 228, cw - 108, 38),
            "clear": (x + w - pad - 100, y + 228, 100, 38),
        }

    def place_widgets(self):
        L = self.layout
        r = self.form_rects()
        self.put(self.amount_entry, r["amount"])
        self.put(self.date_entry, r["date"])
        self.put(self.category_box, r["category"])
        self.put(self.desc_entry, r["description"])
        self.put(self.submit_btn, r["submit"])
        self.put(self.clear_btn, r["clear"])

        x, y, w, h = L["toolbar"]
        cat_w, del_w, exp_w = 170, 84, 110
        search_w = max(120, w - 38 - 12 - cat_w - 12 - del_w - 8 - exp_w - 18)
        self.put(self.search_entry, (x + 38, y + (h - 32) // 2, search_w, 32))
        self.put(self.filter_box, (x + 38 + search_w + 12, y + (h - 32) // 2, cat_w, 32))
        self.put(self.export_btn, (x + w - 18 - exp_w, y + (h - 34) // 2, exp_w, 34))
        self.put(self.delete_btn, (x + w - 18 - exp_w - 8 - del_w, y + (h - 34) // 2, del_w, 34))

        x, y, w, h = L["table"]
        self.put(self.tree, (x + 12, y + 12, w - 40, h - 24))
        self.put(self.scroll, (x + w - 24, y + 12, 12, h - 24))

    # ------------------------------------------------------------ drawing
    def on_resize(self, _event):
        if self._resize_job:
            self.after_cancel(self._resize_job)
        self._resize_job = self.after(100, self.rebuild)

    def panel_rects(self):
        L = self.layout
        panels = [L["header"] + (20,)]
        panels += [rect + (18,) for rect in L["stats"]]
        panels += [L[name] + (22,) for name in ("form", "chart", "toolbar", "table")]
        return panels

    def rebuild(self):
        self._resize_job = None
        w, h = self.canvas.winfo_width(), self.canvas.winfo_height()
        if w < 400 or h < 400 or (w, h) == self._last_size:
            return
        self._last_size = (w, h)
        self.layout = compute_layout(w, h)
        image = render_glass_background(w, h, self.panel_rects())
        self.bg_photo = ImageTk.PhotoImage(image)  # keep a reference
        self.canvas.itemconfigure(self.bg_item, image=self.bg_photo)
        self.place_widgets()
        self.draw_ui()

    def draw_ui(self):
        """Text, icons and the chart are drawn straight on the canvas (so they sit on the glass)."""
        if not self.layout:
            return
        c, L, F = self.canvas, self.layout, self.font
        c.delete("ui")

        # header
        x, y, w, h = L["header"]
        cy = y + h / 2
        c.create_oval(x + 20, cy - 18, x + 56, cy + 18, fill=ACCENT, outline="#d2ccff", width=1, tags="ui")
        c.create_text(x + 38, cy, text=CURRENCY, fill="#ffffff", font=(F, 15, "bold"), tags="ui")
        c.create_text(x + 70, cy, text="Expense Tracker", anchor="w", fill=TEXT,
                      font=(F, 20, "bold"), tags="ui")
        c.create_text(x + w - 24, cy, text=date.today().strftime("%A, %d %B %Y"), anchor="e",
                      fill=MUTED, font=(F, 11), tags="ui")

        # stat cards
        total = sum(e["amount"] for e in self.expenses)
        month_prefix = date.today().strftime("%Y-%m")
        month_total = sum(e["amount"] for e in self.expenses if e["date"].startswith(month_prefix))
        totals = self.category_totals()
        top = totals[0][0] if totals else "-"
        stats = [("TOTAL SPENT", money(total), CHART_COLORS[0]),
                 ("THIS MONTH", money(month_total), CHART_COLORS[1]),
                 ("ENTRIES", str(len(self.expenses)), CHART_COLORS[2]),
                 ("TOP CATEGORY", top, CHART_COLORS[3])]
        for (x, y, w, h), (title, value, color) in zip(L["stats"], stats):
            c.create_line(x + 16, y + 22, x + 16, y + h - 22, width=4, fill=color,
                          capstyle="round", tags="ui")
            c.create_text(x + 32, y + 27, text=title, anchor="w", fill=MUTED,
                          font=(F, 9, "bold"), tags="ui")
            size = 19 if len(value) <= 11 else 15
            c.create_text(x + 32, y + 55, text=value, anchor="w", fill=TEXT,
                          font=(F, size, "bold"), tags="ui")

        # form
        x, y, w, h = L["form"]
        r = self.form_rects()
        c.create_text(x + 18, y + 26, anchor="w", fill=TEXT, font=(F, 14, "bold"), tags="ui",
                      text="Edit Expense" if self.editing_id is not None else "Add Expense")
        for key, label in (("amount", f"AMOUNT ({CURRENCY})"), ("date", "DATE (YYYY-MM-DD)"),
                           ("category", "CATEGORY"), ("description", "DESCRIPTION")):
            fx, fy, _, _ = r[key]
            c.create_text(fx, fy - 12, text=label, anchor="w", fill=MUTED,
                          font=(F, 8, "bold"), tags="ui")

        # toolbar magnifier icon
        x, y, w, h = L["toolbar"]
        mx, my = x + 18, y + h / 2 - 7
        c.create_oval(mx, my, mx + 11, my + 11, outline=MUTED, width=2, tags="ui")
        c.create_line(mx + 10, my + 10, mx + 15, my + 15, fill=MUTED, width=2,
                      capstyle="round", tags="ui")

        self.draw_chart()

    def draw_chart(self):
        c, F = self.canvas, self.font
        x, y, w, h = self.layout["chart"]
        c.create_text(x + 18, y + 26, text="Spending by Category", anchor="w", fill=TEXT,
                      font=(F, 12, "bold"), tags="ui")
        totals = self.category_totals()
        if not totals:
            c.create_text(x + w / 2, y + h / 2 + 12, text="No expenses yet.\nAdd one to see the chart.",
                          fill=MUTED, font=(F, 10), justify="center", tags="ui")
            return
        rows = max(1, int((h - 62) // 30))
        totals = totals[:rows]
        biggest = totals[0][1]
        bx0, bx1 = x + 18 + 86 + 5, x + w - 18 - 84 - 5
        for i, (name, value) in enumerate(totals):
            cy = y + 64 + i * 30
            color = CHART_COLORS[i % len(CHART_COLORS)]
            c.create_text(x + 18, cy, text=name[:11], anchor="w", fill=TEXT,
                          font=(F, 9, "bold"), tags="ui")
            c.create_line(bx0, cy, bx1, cy, width=10, fill=TRACK, capstyle="round", tags="ui")
            end = max(bx0 + 1, bx0 + (bx1 - bx0) * (value / biggest))
            c.create_line(bx0, cy, end, cy, width=10, fill=color, capstyle="round", tags="ui")
            c.create_text(x + w - 18, cy, text=money(value), anchor="e", fill=MUTED,
                          font=(F, 9), tags="ui")

    # ------------------------------------------------------------ actions
    def all_categories(self):
        used = {e["category"] for e in self.expenses}
        return sorted(set(DEFAULT_CATEGORIES) | used)

    def submit(self):
        try:
            amount = round(float(self.amount_var.get().replace(",", "")), 2)
            if amount <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid amount", "Please enter an amount greater than 0.")
            self.amount_entry.focus_set()
            return

        date_text = self.date_var.get().strip()
        try:
            datetime.strptime(date_text, DATE_FORMAT)
        except ValueError:
            messagebox.showerror("Invalid date", "Use the format YYYY-MM-DD, e.g. 2026-10-20.")
            return

        category = self.category_var.get().strip().title() or "Other"
        description = self.desc_var.get().strip()

        if self.editing_id is None:
            self.expenses.append({"id": self.next_id(), "date": date_text, "category": category,
                                  "amount": amount, "description": description})
        else:
            for e in self.expenses:
                if e["id"] == self.editing_id:
                    e.update(date=date_text, category=category, amount=amount,
                             description=description)
                    break

        self.save_expenses()
        self.clear_form()
        self.refresh()

    def clear_form(self):
        self.editing_id = None
        self.amount_var.set("")
        self.category_var.set("")
        self.desc_var.set("")
        self.date_var.set(date.today().strftime(DATE_FORMAT))
        self.submit_btn.config(text="Add Expense")
        if self.tree.selection():
            self.tree.selection_remove(self.tree.selection())
        self.draw_ui()
        self.amount_entry.focus_set()

    def on_select(self, _event=None):
        sel = self.tree.selection()
        if not sel:
            return
        expense_id = int(sel[0])
        e = next((x for x in self.expenses if x["id"] == expense_id), None)
        if not e:
            return
        self.editing_id = expense_id
        self.amount_var.set(f"{e['amount']:.2f}")
        self.category_var.set(e["category"])
        self.date_var.set(e["date"])
        self.desc_var.set(e["description"])
        self.submit_btn.config(text="Update Expense")
        self.draw_ui()

    def delete_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Delete", "Select an expense in the table first.")
            return
        expense_id = int(sel[0])
        if messagebox.askyesno("Delete expense", "Delete the selected expense?"):
            self.expenses = [e for e in self.expenses if e["id"] != expense_id]
            self.save_expenses()
            self.clear_form()
            self.refresh()

    def export_csv(self):
        if not self.expenses:
            messagebox.showinfo("Export", "There is nothing to export yet.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv",
                                            initialfile="expenses_export.csv",
                                            filetypes=[("CSV file", "*.csv")])
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=["id", "date", "category", "amount", "description"])
            writer.writeheader()
            writer.writerows(sorted(self.expenses, key=lambda e: e["date"]))
        messagebox.showinfo("Export", f"Saved to:\n{path}")

    # ------------------------------------------------------------ refresh
    def refresh(self):
        cats = self.all_categories()
        self.category_box.config(values=cats)
        self.filter_box.config(values=["All categories"] + cats)
        if self.filter_var.get() not in ["All categories"] + cats:
            self.filter_var.set("All categories")
        self.refresh_table()
        self.draw_ui()

    def refresh_table(self):
        term = self.search_var.get().strip().lower()
        cat = self.filter_var.get()
        rows = [e for e in self.expenses
                if (cat == "All categories" or e["category"] == cat)
                and (not term or term in e["description"].lower() or term in e["category"].lower())]
        rows.sort(key=lambda e: (e["date"], e["id"]), reverse=True)

        self.tree.delete(*self.tree.get_children())
        for i, e in enumerate(rows):
            self.tree.insert("", "end", iid=str(e["id"]),
                             values=(e["date"], e["category"], e["description"], money(e["amount"])),
                             tags=("alt",) if i % 2 else ())

    def category_totals(self):
        totals = {}
        for e in self.expenses:
            totals[e["category"]] = totals.get(e["category"], 0) + e["amount"]
        return sorted(totals.items(), key=lambda x: x[1], reverse=True)


if __name__ == "__main__":
    ExpenseTracker().mainloop()
