# -*- coding: utf-8 -*-
"""Booky.tn – CustomTkinter desktop application (Django ORM + Ollama)"""

import os, sys, django, requests, json, threading, io
from pathlib import Path
from PIL import Image as PILImage

# ── Bootstrap Django ──────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Biblio_Chat_Bot.settings")
django.setup()

from django.db.models import Q
from library.models import Book, Category
from chat.models import Conversation, Message

import customtkinter as ctk

# ── Design tokens ─────────────────────────────────────────────────────────────
PRIMARY      = "#C4778A"   # soft rose pink
PRIMARY_DARK = "#9A4D62"   # deep rose
PRIMARY_PALE = ("#FDF0F3", "#2A1520")   # lightest blush / deep rose-dark
SIDEBAR_LOGO = ("#F8EEF0", "#1E0F14")   # blush white / near-black

GREEN      = "#22C55E"    # available
RED        = "#EF4444"    # unavailable / error
AMBER      = "#C898A0"    # ratings
MAIN_TEXT  = ("#1F2937", "#F3F4F6")   # primary text
MUTED      = ("#6B7280", "#9CA3AF")   # secondary text
CARD_HOVER = ("#F3F0F8", "#2E1E28")   # card hover tint

CAT_COLORS = ["#C4778A","#9A4D62","#C090A8","#9080A0",
              "#B098B0","#C08898","#A09098","#D0A0B8"]

OLLAMA_URL    = "http://localhost:11434"
DEFAULT_MODEL = "llama3.2"
SESSION_KEY   = "desktop_app"

COVER_CACHE   = BASE_DIR / ".cover_cache"
COVER_CACHE.mkdir(exist_ok=True)

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme(str(BASE_DIR / "rose_theme.json"))


# ── Cover image helpers ───────────────────────────────────────────────────────

def _fetch_cover_pil(book) -> PILImage.Image | None:
    """
    Returns a PIL Image for the book cover.
    Priority: 1) local Django cover_image  2) Open Library by ISBN
              3) Open Library search by title   4) None (fallback to colour)
    Results are cached on disk as <book_id>.jpg.
    """
    cache_path = COVER_CACHE / f"{book.pk}.jpg"
    if cache_path.exists():
        try:
            return PILImage.open(cache_path).convert("RGB")
        except Exception:
            cache_path.unlink(missing_ok=True)

    # 1. Local cover_image field
    if book.cover_image:
        try:
            img = PILImage.open(book.cover_image.path).convert("RGB")
            img.save(cache_path)
            return img
        except Exception:
            pass

    # 2. Open Library by ISBN
    if book.isbn:
        url = f"https://covers.openlibrary.org/b/isbn/{book.isbn}-M.jpg"
        img = _download_image(url)
        if img:
            img.save(cache_path)
            return img

    # 3. Open Library search by title → cover_i
    try:
        query = requests.utils.quote(book.title)
        r = requests.get(
            f"https://openlibrary.org/search.json?title={query}&fields=cover_i&limit=1",
            timeout=6, verify=False)
        docs = r.json().get("docs", [])
        if docs and docs[0].get("cover_i"):
            url = f"https://covers.openlibrary.org/b/id/{docs[0]['cover_i']}-M.jpg"
            img = _download_image(url)
            if img:
                img.save(cache_path)
                return img
    except Exception:
        pass

    return None


def _download_image(url: str) -> PILImage.Image | None:
    try:
        r = requests.get(url, timeout=6, verify=False)
        if r.status_code == 200 and len(r.content) > 1000:
            return PILImage.open(io.BytesIO(r.content)).convert("RGB")
    except Exception:
        pass
    return None


def ctk_cover(pil_img: PILImage.Image, w: int, h: int) -> ctk.CTkImage:
    """Resize a PIL image and wrap it in CTkImage."""
    resized = pil_img.resize((w, h), PILImage.LANCZOS)
    return ctk.CTkImage(light_image=resized, dark_image=resized, size=(w, h))


# ── ORM helpers ───────────────────────────────────────────────────────────────

def orm_books(search=None, category_id=None, available_only=False):
    qs = Book.objects.select_related("author").prefetch_related("categories").order_by("title")
    if search:
        qs = qs.filter(Q(title__icontains=search)
                       | Q(author__name__icontains=search)
                       | Q(description__icontains=search))
    if category_id:
        qs = qs.filter(categories__id=category_id).distinct()
    if available_only:
        qs = qs.filter(available_copies__gt=0)
    return list(qs)


def orm_book(pk):
    try:
        return Book.objects.select_related("author").prefetch_related("categories").get(pk=pk)
    except Book.DoesNotExist:
        return None


def orm_categories():
    return list(Category.objects.order_by("name"))


def orm_conversation():
    conv, _ = Conversation.objects.get_or_create(session_key=SESSION_KEY)
    return conv


def orm_save_msg(conv, role, content):
    Message.objects.create(conversation=conv, role=role, content=content)


def orm_clear_conv():
    Conversation.objects.filter(session_key=SESSION_KEY).delete()


def orm_history(conv):
    return [{"role": m.role, "content": m.content}
            for m in conv.messages.order_by("created_at")]


# ── Tiny utilities ────────────────────────────────────────────────────────────

def star_str(rating: float) -> str:
    n = round(rating)
    return "★" * n + "☆" * (5 - n)


def cat_str(book) -> str:
    """Return 'icon name, icon name' for all categories of a book."""
    parts = [f"{c.icon} {c.name}" for c in book.categories.all()]
    return ", ".join(parts) if parts else "General"


def cat_names(book) -> str:
    parts = [c.name for c in book.categories.all()]
    return ", ".join(parts) if parts else "General"


def _try(widget, **kw):
    """Configure a widget, silently swallowing errors if it was destroyed."""
    try:
        widget.configure(**kw)
    except Exception:
        pass


# ═════════════════════════════════════════════════════════════════════════════
#  Main application
# ═════════════════════════════════════════════════════════════════════════════

class BiblioApp(ctk.CTk):

    def __init__(self):
        super().__init__()
        self.title("Booky.tn")
        self.geometry("1360x820")
        self.minsize(980, 640)

        self._streaming  = False
        self._model      = DEFAULT_MODEL
        self._view_mode  = "grid"   # "grid" | "list"

        self._build_skeleton()
        self._fetch_models()
        self.show_home()

    # ── App skeleton ──────────────────────────────────────────────────────────

    def _build_skeleton(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._build_sidebar()

        self._main = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        self._main.grid(row=0, column=1, sticky="nsew")
        self._main.grid_columnconfigure(0, weight=1)
        self._main.grid_rowconfigure(0, weight=1)

    def _build_sidebar(self):
        sb = ctk.CTkFrame(self, width=160, corner_radius=0)
        sb.grid(row=0, column=0, sticky="nsew")
        sb.grid_rowconfigure(6, weight=1)
        sb.grid_propagate(False)
        sb.grid_columnconfigure(0, weight=1)

        # Logo band
        logo_band = ctk.CTkFrame(sb, fg_color=SIDEBAR_LOGO, corner_radius=0)
        logo_band.grid(row=0, column=0, sticky="ew")
        logo_band.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(logo_band, text="📚  Booky.tn",
                     font=ctk.CTkFont(size=16, weight="bold"),
                     text_color=(PRIMARY, "#E8B8C4")).grid(
            row=0, column=0, padx=14, pady=(16, 2))
        ctk.CTkLabel(logo_band, text="Library · AI",
                     font=ctk.CTkFont(size=10), text_color=MUTED).grid(
            row=1, column=0, padx=14, pady=(0, 14))

        ctk.CTkFrame(sb, height=1, fg_color=("gray80", "gray25")).grid(
            row=1, column=0, sticky="ew")

        # Navigation
        self._nav_btns: dict[str, ctk.CTkButton] = {}
        self._nav_indicators: dict[str, ctk.CTkFrame] = {}
        nav = [
            ("🏠", "Home",       self.show_home),
            ("📖", "Books",      self.show_books),
            ("📂", "Categories", self.show_categories),
            ("💬", "Chat",       self.show_chat),
        ]
        nav_frame = ctk.CTkFrame(sb, fg_color="transparent")
        nav_frame.grid(row=2, column=0, padx=8, pady=10, sticky="ew")
        nav_frame.grid_columnconfigure(0, weight=1)

        self._nav_icon_lbls: dict[str, ctk.CTkLabel] = {}
        self._nav_text_lbls: dict[str, ctk.CTkLabel] = {}

        for i, (icon, label, cmd) in enumerate(nav):
            key = f"{icon}  {label}"

            row_wrap = ctk.CTkFrame(nav_frame, fg_color="transparent", corner_radius=0)
            row_wrap.grid(row=i, column=0, pady=1, sticky="ew")
            row_wrap.grid_columnconfigure(1, weight=1)

            # Left border indicator
            ind = ctk.CTkFrame(row_wrap, width=4, corner_radius=2, fg_color="transparent")
            ind.grid(row=0, column=0, sticky="nsew", padx=(0, 3), pady=4)
            ind.grid_propagate(False)

            # Clickable frame with icon on top, label below
            btn = ctk.CTkFrame(row_wrap, corner_radius=8, width=110,
                                fg_color="transparent", cursor="hand2")
            btn.grid(row=0, column=1, padx=4, pady=3)
            btn.grid_columnconfigure(0, weight=1)

            icon_lbl = ctk.CTkLabel(btn, text=icon,
                                     font=ctk.CTkFont(size=24),
                                     text_color=MAIN_TEXT)
            icon_lbl.grid(row=0, column=0, pady=(5, 1))

            text_lbl = ctk.CTkLabel(btn, text=label,
                                     font=ctk.CTkFont(size=11),
                                     text_color=MUTED)
            text_lbl.grid(row=1, column=0, pady=(0, 5))

            # Hover + click bindings
            for w in (btn, icon_lbl, text_lbl):
                w.bind("<Button-1>", lambda _, c=cmd: c())
                w.bind("<Enter>",
                       lambda _, f=btn: f.configure(fg_color=PRIMARY_PALE))
                w.bind("<Leave>",
                       lambda _, f=btn: f.configure(fg_color="transparent"))

            self._nav_btns[key] = btn
            self._nav_indicators[key] = ind
            self._nav_icon_lbls[key] = icon_lbl
            self._nav_text_lbls[key] = text_lbl

        # Divider + appearance
        ctk.CTkFrame(sb, height=1, fg_color=("gray80", "gray25")).grid(
            row=7, column=0, padx=10, pady=8, sticky="ew")
        ctk.CTkLabel(sb, text="Appearance", font=ctk.CTkFont(size=10),
                     text_color=MUTED).grid(row=8, column=0, padx=12, pady=(0, 3), sticky="w")
        ctk.CTkOptionMenu(sb, values=["Dark", "Light", "System"],
                          command=ctk.set_appearance_mode,
                          height=30, corner_radius=8).grid(
            row=9, column=0, padx=10, pady=(0, 16), sticky="ew")

    def _clear_main(self):
        self._streaming = False
        for w in self._main.winfo_children():
            w.destroy()

    def _activate_nav(self, key: str):
        for k, frame in self._nav_btns.items():
            ind       = self._nav_indicators.get(k)
            icon_lbl  = self._nav_icon_lbls.get(k)
            text_lbl  = self._nav_text_lbls.get(k)
            active    = k == key
            try:
                frame.configure(fg_color=PRIMARY_PALE if active else "transparent")
            except Exception:
                pass
            if icon_lbl:
                icon_lbl.configure(
                    text_color=(PRIMARY, "#E8B8C4") if active else MAIN_TEXT)
            if text_lbl:
                text_lbl.configure(
                    text_color=(PRIMARY, "#E8B8C4") if active else MUTED,
                    font=ctk.CTkFont(size=11, weight="bold" if active else "normal"))
            if ind:
                ind.configure(fg_color=(PRIMARY, PRIMARY) if active else "transparent")

    def _add_tooltip(self, widget, text: str):
        """Show a small label next to the widget on hover."""
        tip: ctk.CTkToplevel | None = None

        def _show(e):
            nonlocal tip
            tip = ctk.CTkToplevel(self)
            tip.wm_overrideredirect(True)
            tip.wm_attributes("-topmost", True)
            ctk.CTkLabel(tip, text=text,
                          font=ctk.CTkFont(size=12),
                          fg_color=(PRIMARY, PRIMARY_DARK),
                          text_color="white",
                          corner_radius=6).pack(ipadx=8, ipady=4)
            tip.update_idletasks()
            tip.wm_geometry(f"+{e.x_root + 56}+{e.y_root - 10}")

        def _hide(_):
            nonlocal tip
            if tip:
                try:
                    tip.destroy()
                except Exception:
                    pass
                tip = None

        widget.bind("<Enter>", _show, add="+")
        widget.bind("<Leave>", _hide, add="+")

    def _toggle_appearance(self):
        modes = ["Dark", "Light", "System"]
        current = ctk.get_appearance_mode()
        nxt = modes[(modes.index(current.capitalize()) + 1) % 3] \
              if current.capitalize() in modes else "Light"
        ctk.set_appearance_mode(nxt)

    # ── Shared component builders ─────────────────────────────────────────────

    def _page_header(self, parent, title: str, subtitle: str = "") -> ctk.CTkFrame:
        hdr = ctk.CTkFrame(parent, fg_color="transparent")
        hdr.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(hdr, text=title,
                     font=ctk.CTkFont(size=23, weight="bold")).grid(
            row=0, column=0, sticky="w")
        if subtitle:
            ctk.CTkLabel(hdr, text=subtitle, font=ctk.CTkFont(size=12),
                         text_color=MUTED).grid(row=1, column=0, sticky="w", pady=(1, 0))
        # Accent underline
        ctk.CTkFrame(hdr, height=3, corner_radius=2,
                     fg_color=(PRIMARY, PRIMARY)).grid(
            row=2, column=0, sticky="w", pady=(6, 0), ipadx=28)
        return hdr

    def _cover_thumb(self, parent, book, w: int, h: int,
                     corner_radius: int = 6) -> ctk.CTkFrame:
        """
        Fixed w×h cover thumbnail. Shows real image (async) or coloured fallback.
        """
        color = book.cover_color or PRIMARY
        frame = ctk.CTkFrame(parent, width=w, height=h,
                              corner_radius=corner_radius,
                              fg_color=(color, color))
        frame.grid_propagate(False)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(0, weight=1)

        # Placeholder
        lbl = ctk.CTkLabel(frame,
                            text=book.title[:16] + ("…" if len(book.title) > 16 else ""),
                            font=ctk.CTkFont(size=8, weight="bold"),
                            text_color="white", wraplength=w - 8, justify="center")
        lbl.grid(row=0, column=0, padx=2, pady=2)

        def _load():
            pil = _fetch_cover_pil(book)
            if pil:
                try:
                    cimg = ctk_cover(pil, w, h)
                    self.after(0, lambda: self._apply_img(lbl, cimg, frame))
                except Exception:
                    pass
        threading.Thread(target=_load, daemon=True).start()
        return frame

    def _cover_banner(self, parent, book, h: int,
                      corner_radius: int = 10) -> ctk.CTkFrame:
        """
        Full-width banner cover. Stretches horizontally, fixed height h.
        Shows real image centred on the colour background.
        """
        color = book.cover_color or PRIMARY
        frame = ctk.CTkFrame(parent, corner_radius=corner_radius,
                              fg_color=(color, color))
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(0, minsize=h)

        lbl = ctk.CTkLabel(frame,
                            text=book.title[:24],
                            font=ctk.CTkFont(size=11, weight="bold"),
                            text_color="white", wraplength=170, justify="center")
        lbl.grid(row=0, column=0, padx=8, pady=4)

        def _load():
            pil = _fetch_cover_pil(book)
            if pil:
                try:
                    # Keep aspect ratio, fit to height h
                    ratio   = h / pil.height
                    new_w   = max(1, int(pil.width * ratio))
                    resized = pil.resize((new_w, h), PILImage.LANCZOS)
                    cimg = ctk.CTkImage(light_image=resized,
                                         dark_image=resized,
                                         size=(new_w, h))
                    self.after(0, lambda: self._apply_img(lbl, cimg, frame))
                except Exception:
                    pass
        threading.Thread(target=_load, daemon=True).start()
        return frame

    @staticmethod
    def _apply_img(label: ctk.CTkLabel, cimg: ctk.CTkImage,
                   frame: ctk.CTkFrame | None = None):
        try:
            label.configure(image=cimg, text="")
            label._img_ref = cimg                    # prevent GC
            if frame is not None:
                frame.configure(fg_color="transparent")  # remove coloured bg
        except Exception:
            pass

    def _badge(self, parent, text: str, color: str,
               fg: str = "white") -> ctk.CTkLabel:
        return ctk.CTkLabel(parent, text=f"  {text}  ",
                             font=ctk.CTkFont(size=10, weight="bold"),
                             fg_color=color, text_color=fg, corner_radius=5, height=22)

    def _add_hover(self, card: ctk.CTkFrame,
                   normal=None, hover=CARD_HOVER):
        """Recursively bind Enter/Leave for a card hover tint."""
        if normal is None:
            try:
                normal = card.cget("fg_color")
            except Exception:
                return

        def _enter(_):
            try: card.configure(fg_color=hover)
            except Exception: pass

        def _leave(_):
            try: card.configure(fg_color=normal)
            except Exception: pass

        def _bind(w):
            try:
                w.bind("<Enter>", _enter, add="+")
                w.bind("<Leave>", _leave, add="+")
            except Exception:
                pass
            for child in w.winfo_children():
                _bind(child)

        _bind(card)

    def _empty_state(self, parent, icon: str, title: str, subtitle: str = ""):
        wrap = ctk.CTkFrame(parent, fg_color="transparent")
        wrap.grid(row=0, column=0, columnspan=10, pady=70)
        ctk.CTkLabel(wrap, text=icon, font=ctk.CTkFont(size=52)).pack()
        ctk.CTkLabel(wrap, text=title,
                     font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(10, 3))
        if subtitle:
            ctk.CTkLabel(wrap, text=subtitle,
                         font=ctk.CTkFont(size=13), text_color=MUTED).pack()

    # ════════════════════════════════════════════════════════════════════
    #  HOME
    # ════════════════════════════════════════════════════════════════════

    def show_home(self):
        self._clear_main()
        self._activate_nav("🏠  Home")

        scroll = ctk.CTkScrollableFrame(self._main, fg_color="transparent")
        scroll.grid(row=0, column=0, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)

        # ── Compact hero with search ──────────────────────────────────
        hero = ctk.CTkFrame(scroll, corner_radius=14,
                             fg_color=(PRIMARY, PRIMARY_DARK))
        hero.grid(row=0, column=0, padx=18, pady=(16, 0), sticky="ew")
        hero.grid_columnconfigure(0, weight=1)
        hero.grid_columnconfigure(1, weight=1)

        # Left: title + subtitle
        left = ctk.CTkFrame(hero, fg_color="transparent")
        left.grid(row=0, column=0, padx=(24, 12), pady=18, sticky="w")
        ctk.CTkLabel(left, text="📚  Your Library",
                     font=ctk.CTkFont(size=22, weight="bold"),
                     text_color="white").pack(anchor="w")
        total  = Book.objects.count()
        n_cats = Category.objects.count()
        avail  = Book.objects.filter(available_copies__gt=0).count()
        ctk.CTkLabel(left,
                     text=f"{total} books · {n_cats} categories · {avail} available",
                     font=ctk.CTkFont(size=12), text_color="#F8E0E8").pack(anchor="w", pady=(3, 0))

        # Right: search bar
        search_wrap = ctk.CTkFrame(hero, corner_radius=10, height=42,
                                    fg_color=("white", "#3D1A2E"))
        search_wrap.grid(row=0, column=1, padx=(12, 24), pady=18, sticky="ew")
        search_wrap.grid_columnconfigure(1, weight=1)
        search_wrap.grid_propagate(False)
        ctk.CTkLabel(search_wrap, text="🔍",
                      font=ctk.CTkFont(size=14),
                      text_color=(PRIMARY, "#E8B8C4")).grid(
            row=0, column=0, padx=(10, 4))
        self._hero_q = ctk.StringVar()
        he = ctk.CTkEntry(search_wrap, textvariable=self._hero_q,
                           placeholder_text="Search books, authors…",
                           border_width=0, fg_color="transparent",
                           height=38, font=ctk.CTkFont(size=13),
                           text_color=(PRIMARY, "white"))
        he.grid(row=0, column=1, sticky="ew", padx=(0, 4))
        he.bind("<Return>", lambda _: self._hero_search())
        ctk.CTkButton(search_wrap, text="Search", width=70, height=30,
                       corner_radius=8, font=ctk.CTkFont(size=12),
                       command=self._hero_search).grid(row=0, column=2, padx=(0, 6))

        # ── Stats row (horizontal) ────────────────────────────────────
        stats_row = ctk.CTkFrame(scroll, fg_color="transparent")
        stats_row.grid(row=1, column=0, padx=18, pady=(14, 0), sticky="ew")
        stats_row.grid_columnconfigure((0, 1, 2), weight=1)

        for col, (icon, val, lbl, color) in enumerate([
            ("📚", total,  "Total Books",   PRIMARY),
            ("📂", n_cats, "Categories",    AMBER),
            ("✅", avail,  "Available Now", GREEN),
        ]):
            sc = ctk.CTkFrame(stats_row, corner_radius=12)
            sc.grid(row=0, column=col, padx=7, sticky="ew")
            sc.grid_columnconfigure(1, weight=1)
            ib = ctk.CTkFrame(sc, width=44, height=44, corner_radius=10,
                               fg_color=(color, color))
            ib.grid(row=0, column=0, rowspan=2, padx=(14, 10), pady=14)
            ib.grid_propagate(False)
            ctk.CTkLabel(ib, text=icon, font=ctk.CTkFont(size=20)).place(
                relx=.5, rely=.5, anchor="center")
            ctk.CTkLabel(sc, text=str(val),
                          font=ctk.CTkFont(size=24, weight="bold"),
                          text_color=color).grid(row=0, column=1, sticky="sw", pady=(12, 0))
            ctk.CTkLabel(sc, text=lbl, font=ctk.CTkFont(size=11),
                          text_color=MUTED).grid(row=1, column=1, sticky="nw", pady=(0, 12))
            self._add_hover(sc)

        # ── Featured Recommendation (full width) ──────────────────────
        feat = (Book.objects.select_related("author").prefetch_related("categories")
                .filter(available_copies__gt=0).order_by("-rating").first())
        if feat:
            fr = ctk.CTkFrame(scroll, corner_radius=14)
            fr.grid(row=2, column=0, padx=18, pady=(12, 0), sticky="ew")
            fr.grid_columnconfigure(1, weight=1)

            ctk.CTkFrame(fr, height=4, corner_radius=0,
                          fg_color=(PRIMARY, PRIMARY)).grid(
                row=0, column=0, columnspan=3, sticky="ew")

            ctk.CTkLabel(fr, text="⭐  Featured Recommendation",
                          font=ctk.CTkFont(size=11, weight="bold"),
                          text_color=(PRIMARY, "#E8B8C4")).grid(
                row=1, column=0, columnspan=3, padx=16, pady=(10, 6), sticky="w")

            thumb = self._cover_thumb(fr, feat, w=80, h=110, corner_radius=8)
            thumb.grid(row=2, column=0, rowspan=3, padx=(16, 14), pady=(0, 16))

            ctk.CTkLabel(fr, text=feat.title,
                          font=ctk.CTkFont(size=15, weight="bold"),
                          text_color=MAIN_TEXT,
                          wraplength=500, justify="left").grid(
                row=2, column=1, sticky="w", padx=(0, 14), pady=(2, 2))
            ctk.CTkLabel(fr, text=f"by {feat.author.name}",
                          font=ctk.CTkFont(size=12), text_color=MUTED).grid(
                row=3, column=1, sticky="w", padx=(0, 14))

            meta = ctk.CTkFrame(fr, fg_color="transparent")
            meta.grid(row=4, column=1, sticky="w", padx=(0, 14), pady=(4, 0))
            ctk.CTkLabel(meta, text=f"★ {float(feat.rating):.1f}",
                          font=ctk.CTkFont(size=12, weight="bold"),
                          text_color=AMBER).pack(side="left")
            ctk.CTkLabel(meta, text=f"  ·  {cat_str(feat)}",
                          font=ctk.CTkFont(size=12), text_color=MUTED).pack(side="left")

            act = ctk.CTkFrame(fr, fg_color="transparent")
            act.grid(row=5, column=1, sticky="w", padx=(0, 14), pady=(10, 16))
            fid = feat.pk
            ctk.CTkButton(act, text="View Details", height=32, width=110,
                           corner_radius=8, font=ctk.CTkFont(size=11),
                           command=lambda b=fid: self.show_book_detail(b)).pack(
                side="left", padx=(0, 8))
            ctk.CTkButton(act, text="💬 Ask AI", height=32, width=90,
                           corner_radius=8, font=ctk.CTkFont(size=11),
                           fg_color=GREEN, hover_color="#16A34A",
                           command=lambda: self.show_chat(
                               prefill=f"Tell me about '{feat.title}'."
                           )).pack(side="left")

        # ── Recently Added ────────────────────────────────────────────
        self._page_header(scroll, "Recently Added",
                           "Latest books in the collection").grid(
            row=3, column=0, padx=22, pady=(14, 12), sticky="ew")

        recent_row = ctk.CTkFrame(scroll, fg_color="transparent")
        recent_row.grid(row=4, column=0, padx=18, pady=(0, 6), sticky="ew")
        recent = list(Book.objects.select_related("author").prefetch_related("categories")
                      .order_by("-created_at")[:4])
        for i, book in enumerate(recent):
            recent_row.grid_columnconfigure(i, weight=1)
            self._small_book_card(recent_row, book, 0, i)

        # ── Top Rated ─────────────────────────────────────────────────
        self._page_header(scroll, "Top Rated",
                           "Highest-rated titles in our catalog").grid(
            row=5, column=0, padx=22, pady=(14, 12), sticky="ew")

        grid = ctk.CTkFrame(scroll, fg_color="transparent")
        grid.grid(row=6, column=0, padx=18, pady=(0, 24), sticky="ew")
        COLS = 3
        for c in range(COLS):
            grid.grid_columnconfigure(c, weight=1)

        top_rated = list(Book.objects.select_related("author").prefetch_related("categories")
                         .order_by("-rating")[:6])
        for i, book in enumerate(top_rated):
            self._home_book_card(grid, book, i // COLS, i % COLS)

    def _hero_search(self):
        q = self._hero_q.get().strip() if hasattr(self, "_hero_q") else ""
        self.show_books()
        if q:
            self._search_var.set(q)
            self._reload_books()

    def _small_book_card(self, parent, book, row: int, col: int):
        """Compact horizontal card used in the 'Recently Added' row."""
        card = ctk.CTkFrame(parent, corner_radius=12)
        card.grid(row=row, column=col, padx=7, pady=4, sticky="ew")
        card.grid_columnconfigure(0, weight=1)

        cover = self._cover_banner(card, book, h=110, corner_radius=8)
        cover.grid(row=0, column=0, padx=8, pady=(10, 0), sticky="ew")

        ctk.CTkLabel(card, text=book.title,
                      font=ctk.CTkFont(size=12, weight="bold"),
                      text_color=MAIN_TEXT,
                      wraplength=160, justify="left").grid(
            row=1, column=0, padx=10, pady=(6, 1), sticky="w")
        ctk.CTkLabel(card, text=book.author.name,
                      font=ctk.CTkFont(size=10), text_color=MUTED).grid(
            row=2, column=0, padx=10, sticky="w")
        ctk.CTkLabel(card, text=f"★ {float(book.rating):.1f}",
                      font=ctk.CTkFont(size=10, weight="bold"),
                      text_color=AMBER).grid(
            row=3, column=0, padx=10, pady=(2, 10), sticky="w")

        bid = book.pk
        card.bind("<Button-1>", lambda _: self.show_book_detail(bid))
        self._add_hover(card)

    def _home_book_card(self, parent, book, row: int, col: int):
        card = ctk.CTkFrame(parent, corner_radius=14)
        card.grid(row=row, column=col, padx=8, pady=8, sticky="ew")
        card.grid_columnconfigure(0, weight=1)

        # Larger cover: 135px
        cover = self._cover_banner(card, book, h=135, corner_radius=10)
        cover.grid(row=0, column=0, padx=10, pady=(12, 0), sticky="ew")

        # Title — bold, dark
        ctk.CTkLabel(card, text=book.title,
                      font=ctk.CTkFont(size=13, weight="bold"),
                      text_color=MAIN_TEXT,
                      wraplength=185, justify="left").grid(
            row=1, column=0, padx=12, pady=(8, 1), sticky="w")

        # Author — muted
        ctk.CTkLabel(card, text=book.author.name,
                      font=ctk.CTkFont(size=11),
                      text_color=MUTED).grid(
            row=2, column=0, padx=12, sticky="w")

        # Category tag pill
        cats = list(book.categories.all()[:1])
        if cats:
            self._badge(card, f"{cats[0].icon} {cats[0].name}",
                         PRIMARY_PALE[0], PRIMARY).grid(
                row=3, column=0, padx=12, pady=(4, 0), sticky="w")

        # Rating + availability
        footer = ctk.CTkFrame(card, fg_color="transparent")
        footer.grid(row=4, column=0, padx=10, pady=(4, 4), sticky="ew")
        ctk.CTkLabel(footer, text=f"★ {float(book.rating):.1f}",
                      font=ctk.CTkFont(size=11, weight="bold"),
                      text_color=AMBER).pack(side="left", padx=(2, 0))
        self._badge(footer,
                    "Available" if book.is_available else "Unavailable",
                    GREEN if book.is_available else RED).pack(side="right", padx=(0, 2))

        bid = book.pk
        ctk.CTkButton(card, text="View Details →", height=32, corner_radius=8,
                       font=ctk.CTkFont(size=11),
                       command=lambda b=bid: self.show_book_detail(b)).grid(
            row=5, column=0, padx=12, pady=(2, 12), sticky="ew")

        self._add_hover(card)

    # ════════════════════════════════════════════════════════════════════
    #  BOOKS
    # ════════════════════════════════════════════════════════════════════

    def show_books(self, *, preset_category=None):
        self._clear_main()
        self._activate_nav("📖  Books")

        outer = ctk.CTkFrame(self._main, fg_color="transparent")
        outer.grid(row=0, column=0, sticky="nsew")
        outer.grid_columnconfigure(0, weight=1)
        outer.grid_rowconfigure(2, weight=1)

        # Header
        self._page_header(outer, "Book Catalog",
                           f"{Book.objects.count()} volumes · use filters to narrow your search").grid(
            row=0, column=0, padx=22, pady=(18, 12), sticky="ew")

        # ── Toolbar ──
        toolbar = ctk.CTkFrame(outer, fg_color="transparent")
        toolbar.grid(row=1, column=0, padx=18, pady=(0, 10), sticky="ew")
        toolbar.grid_columnconfigure(0, weight=1)

        # Search box
        search_wrap = ctk.CTkFrame(toolbar, corner_radius=10, height=44,
                                    border_width=1,
                                    border_color=("gray72", "gray32"))
        search_wrap.grid(row=0, column=0, padx=(0, 8), sticky="ew")
        search_wrap.grid_columnconfigure(1, weight=1)
        search_wrap.grid_propagate(False)
        ctk.CTkLabel(search_wrap, text="🔍",
                      font=ctk.CTkFont(size=16)).grid(row=0, column=0, padx=(10, 4))
        self._search_var = ctk.StringVar()
        entry = ctk.CTkEntry(search_wrap, textvariable=self._search_var,
                              placeholder_text="Search title, author, description…",
                              border_width=0, fg_color="transparent",
                              height=40, font=ctk.CTkFont(size=13))
        entry.grid(row=0, column=1, sticky="ew", padx=(0, 8))
        entry.bind("<Return>", lambda _: self._reload_books())

        # Category dropdown
        cats = orm_categories()
        self._cat_var = ctk.StringVar(value=preset_category or "All Genres")
        ctk.CTkOptionMenu(toolbar, variable=self._cat_var,
                           values=["All Genres"] + [c.name for c in cats],
                           width=162, height=44, corner_radius=10,
                           command=lambda _: self._reload_books()).grid(
            row=0, column=1, padx=(0, 8))

        # Available-only toggle
        self._avail_var = ctk.BooleanVar(value=False)
        ctk.CTkSwitch(toolbar, text="Available only",
                       variable=self._avail_var,
                       font=ctk.CTkFont(size=12),
                       command=self._reload_books).grid(row=0, column=2, padx=(0, 8))

        # Grid / List segmented button
        self._view_seg = ctk.CTkSegmentedButton(
            toolbar, values=["⊞  Grid", "☰  List"],
            height=44, corner_radius=10,
            command=self._on_view_change, width=148)
        self._view_seg.set("⊞  Grid" if self._view_mode == "grid" else "☰  List")
        self._view_seg.grid(row=0, column=3, padx=(0, 8))

        ctk.CTkButton(toolbar, text="Search", height=44, width=92,
                       corner_radius=10, font=ctk.CTkFont(size=13),
                       command=self._reload_books).grid(row=0, column=4)

        # Results pane
        self._books_pane = ctk.CTkScrollableFrame(outer, fg_color="transparent")
        self._books_pane.grid(row=2, column=0, padx=16, pady=(0, 14), sticky="nsew")

        self._reload_books()

    def _on_view_change(self, val: str):
        self._view_mode = "grid" if "⊞" in val else "list"
        self._reload_books()

    def _reload_books(self):
        for w in self._books_pane.winfo_children():
            w.destroy()

        search    = self._search_var.get().strip() or None
        cat_name  = self._cat_var.get()
        avail     = self._avail_var.get()

        cat_id = None
        if cat_name not in ("All Genres", ""):
            try:
                cat_id = Category.objects.get(name=cat_name).pk
            except Category.DoesNotExist:
                pass

        books = orm_books(search=search, category_id=cat_id, available_only=avail)

        if not books:
            self._books_pane.grid_columnconfigure(0, weight=1)
            self._empty_state(self._books_pane, "📭", "No books found",
                               "Try a different search or clear the filters.")
            return

        if self._view_mode == "grid":
            COLS = 4
            for c in range(COLS):
                self._books_pane.grid_columnconfigure(c, weight=1)
            for i, book in enumerate(books):
                self._book_grid_card(self._books_pane, book, i // COLS, i % COLS)
        else:
            self._books_pane.grid_columnconfigure(0, weight=1)
            for c in range(1, 5):
                self._books_pane.grid_columnconfigure(c, weight=0)
            for i, book in enumerate(books):
                self._book_list_row(self._books_pane, book, i)

    def _book_grid_card(self, parent, book, row: int, col: int):
        card = ctk.CTkFrame(parent, corner_radius=12)
        card.grid(row=row, column=col, padx=6, pady=6, sticky="ew")
        card.grid_columnconfigure(0, weight=1)

        cover = self._cover_banner(card, book, h=86, corner_radius=8)
        cover.grid(row=0, column=0, padx=8, pady=(10, 0), sticky="ew")

        ctk.CTkLabel(card, text=book.title,
                      font=ctk.CTkFont(size=12, weight="bold"),
                      wraplength=160, justify="left").grid(
            row=1, column=0, padx=10, pady=(6, 1), sticky="w")
        ctk.CTkLabel(card, text=book.author.name,
                      font=ctk.CTkFont(size=10), text_color=MUTED).grid(
            row=2, column=0, padx=10, sticky="w")

        foot = ctk.CTkFrame(card, fg_color="transparent")
        foot.grid(row=3, column=0, padx=8, pady=(4, 4), sticky="ew")
        ctk.CTkLabel(foot, text=f"★ {float(book.rating):.1f}",
                      font=ctk.CTkFont(size=10), text_color=AMBER).pack(side="left")
        self._badge(foot, "In" if book.is_available else "Out",
                    GREEN if book.is_available else RED).pack(side="right")

        bid = book.pk
        ctk.CTkButton(card, text="Details", height=28, corner_radius=7,
                       font=ctk.CTkFont(size=10),
                       command=lambda b=bid: self.show_book_detail(b)).grid(
            row=4, column=0, padx=10, pady=(0, 10), sticky="ew")

        self._add_hover(card)

    def _book_list_row(self, parent, book, idx: int):
        row = ctk.CTkFrame(parent, corner_radius=10)
        row.grid(row=idx, column=0, padx=2, pady=3, sticky="ew")
        row.grid_columnconfigure(3, weight=1)

        # Left border indicator (stronger, 6px)
        strip = ctk.CTkFrame(row, width=6, corner_radius=0,
                              fg_color=book.cover_color or PRIMARY)
        strip.grid(row=0, column=0, rowspan=3, sticky="nsew")
        strip.grid_propagate(False)
        self._add_hover(row)

        # Thumbnail cover
        mini = self._cover_thumb(row, book, w=52, h=70)
        mini.grid(row=0, column=1, rowspan=3, padx=(10, 6), pady=10)

        # Text block
        ctk.CTkLabel(row, text=book.title,
                      font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=0, column=3, sticky="w", pady=(10, 1), padx=(4, 0))
        ctk.CTkLabel(row, text=f"by {book.author.name}  ·  {cat_str(book)}",
                      font=ctk.CTkFont(size=11), text_color=MUTED).grid(
            row=1, column=3, sticky="w", padx=(4, 0))
        meta = (f"★ {float(book.rating):.1f}"
                + (f"  ·  {book.pages} pp" if book.pages else "")
                + (f"  ·  {book.published_year}" if book.published_year else ""))
        ctk.CTkLabel(row, text=meta, font=ctk.CTkFont(size=11),
                      text_color=MUTED).grid(
            row=2, column=3, sticky="w", pady=(0, 10), padx=(4, 0))

        # Right panel
        right = ctk.CTkFrame(row, fg_color="transparent")
        right.grid(row=0, column=4, rowspan=3, padx=14, pady=10, sticky="e")
        self._badge(right,
                    "Available" if book.is_available else "Unavailable",
                    GREEN if book.is_available else RED).pack(pady=(4, 8))
        bid = book.pk
        ctk.CTkButton(right, text="View →", width=84, height=32,
                       corner_radius=8, font=ctk.CTkFont(size=11),
                       command=lambda b=bid: self.show_book_detail(b)).pack()

    # ════════════════════════════════════════════════════════════════════
    #  BOOK DETAIL
    # ════════════════════════════════════════════════════════════════════

    def show_book_detail(self, book_id: int):
        self._clear_main()
        self._activate_nav("📖  Books")

        book = orm_book(book_id)
        if not book:
            return

        scroll = ctk.CTkScrollableFrame(self._main, fg_color="transparent")
        scroll.grid(row=0, column=0, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)

        # Back
        ctk.CTkButton(scroll, text="← Back to Books",
                       width=165, height=34, corner_radius=9,
                       fg_color="transparent", border_width=1,
                       border_color=("gray70", "gray38"),
                       text_color=MAIN_TEXT,
                       hover_color=("gray88", "gray22"),
                       command=self.show_books).grid(
            row=0, column=0, padx=20, pady=(16, 10), sticky="w")

        # ── Hero card ──
        c = book.cover_color or PRIMARY
        hero = ctk.CTkFrame(scroll, corner_radius=18, fg_color=(c, c))
        hero.grid(row=1, column=0, padx=20, pady=(0, 18), sticky="ew")
        hero.grid_columnconfigure(1, weight=1)

        # Cover thumbnail inside hero
        self._cover_thumb(hero, book, w=115, h=150, corner_radius=8).grid(
            row=0, column=0, rowspan=4, padx=(26, 20), pady=26)

        ctk.CTkLabel(hero, text=book.title,
                      font=ctk.CTkFont(size=27, weight="bold"),
                      text_color="white", wraplength=620, justify="left").grid(
            row=0, column=1, padx=(0, 26), pady=(26, 4), sticky="w")
        ctk.CTkLabel(hero, text=f"by {book.author.name}",
                      font=ctk.CTkFont(size=14), text_color="#F8E0E8").grid(
            row=1, column=1, padx=(0, 26), sticky="w")
        ctk.CTkLabel(hero,
                      text=f"{star_str(float(book.rating))}   {float(book.rating):.1f} / 5",
                      font=ctk.CTkFont(size=15), text_color=AMBER).grid(
            row=2, column=1, padx=(0, 26), pady=(6, 0), sticky="w")
        avail_txt = "✅  Available for borrowing" if book.is_available else "❌  Currently unavailable"
        ctk.CTkLabel(hero, text=avail_txt, font=ctk.CTkFont(size=13),
                      text_color="#86EFAC" if book.is_available else "#FCA5A5").grid(
            row=3, column=1, padx=(0, 26), pady=(4, 26), sticky="w")

        # ── Metadata grid ──
        meta_card = ctk.CTkFrame(scroll, corner_radius=14)
        meta_card.grid(row=2, column=0, padx=20, pady=(0, 16), sticky="ew")
        meta_card.grid_columnconfigure((0, 1, 2, 3, 4), weight=1)

        fields = [
            ("📂  Categories", cat_str(book) or "N/A"),
            ("📄  Pages",    str(book.pages) if book.pages else "N/A"),
            ("📅  Year",     str(book.published_year) if book.published_year else "N/A"),
            ("🌐  Language", book.language or "N/A"),
            ("🗂️  Copies",  f"{book.available_copies} / {book.total_copies}"),
        ]
        for col, (lbl, val) in enumerate(fields):
            ctk.CTkLabel(meta_card, text=lbl, font=ctk.CTkFont(size=10),
                          text_color=MUTED).grid(row=0, column=col, padx=14, pady=(14, 2))
            ctk.CTkLabel(meta_card, text=val,
                          font=ctk.CTkFont(size=13, weight="bold")).grid(
                row=1, column=col, padx=14, pady=(0, 14))

        if book.isbn:
            ctk.CTkLabel(scroll, text=f"ISBN  {book.isbn}",
                          font=ctk.CTkFont(size=11), text_color=MUTED).grid(
                row=3, column=0, padx=24, pady=(0, 10), sticky="w")

        next_row = 4

        # ── Description ──
        if book.description:
            self._page_header(scroll, "About This Book").grid(
                row=next_row, column=0, padx=24, pady=(6, 8), sticky="ew")
            next_row += 1
            section = ctk.CTkFrame(scroll, corner_radius=14)
            section.grid(row=next_row, column=0, padx=20, pady=(0, 16), sticky="ew")
            ctk.CTkLabel(section, text=book.description,
                          font=ctk.CTkFont(size=13), wraplength=820,
                          justify="left",
                          text_color=("gray15", "gray82")).pack(padx=22, pady=18, anchor="w")
            next_row += 1

        # ── Author bio ──
        if book.author.bio:
            self._page_header(scroll, f"About {book.author.name}").grid(
                row=next_row, column=0, padx=24, pady=(6, 8), sticky="ew")
            next_row += 1
            section = ctk.CTkFrame(scroll, corner_radius=14)
            section.grid(row=next_row, column=0, padx=20, pady=(0, 16), sticky="ew")
            ctk.CTkLabel(section, text=book.author.bio,
                          font=ctk.CTkFont(size=13), wraplength=820,
                          justify="left",
                          text_color=("gray15", "gray82")).pack(padx=22, pady=18, anchor="w")
            next_row += 1

        # ── Chat CTA ──
        t, a = book.title, book.author.name
        ctk.CTkButton(scroll,
                       text="💬   Ask Booky.tn AI about this book",
                       height=48, corner_radius=12,
                       font=ctk.CTkFont(size=14, weight="bold"),
                       fg_color=GREEN, hover_color="#16A34A",
                       command=lambda: self.show_chat(
                           prefill=f"Tell me about '{t}' by {a}."
                       )).grid(row=next_row, column=0, padx=20, pady=(4, 28), sticky="ew")

    # ════════════════════════════════════════════════════════════════════
    #  CATEGORIES
    # ════════════════════════════════════════════════════════════════════

    def show_categories(self):
        self._clear_main()
        self._activate_nav("📂  Categories")

        scroll = ctk.CTkScrollableFrame(self._main, fg_color="transparent")
        scroll.grid(row=0, column=0, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)

        self._page_header(scroll, "Categories",
                           "Browse the library by genre").grid(
            row=0, column=0, padx=24, pady=(18, 16), sticky="ew")

        grid = ctk.CTkFrame(scroll, fg_color="transparent")
        grid.grid(row=1, column=0, padx=16, pady=(0, 22), sticky="ew")
        COLS = 3
        for c in range(COLS):
            grid.grid_columnconfigure(c, weight=1)

        for i, cat in enumerate(orm_categories()):
            self._cat_card(grid, cat, "#7D7D8D", i // COLS, i % COLS)

    def _cat_card(self, parent, cat, color: str, row: int, col: int):
        card = ctk.CTkFrame(parent, corner_radius=16)
        card.grid(row=row, column=col, padx=10, pady=10, sticky="ew")
        card.grid_columnconfigure(0, weight=1)

        # Colored top band with icon
        band = ctk.CTkFrame(card, corner_radius=12, height=78,
                             fg_color=(color, color))
        band.grid(row=0, column=0, padx=10, pady=(12, 0), sticky="ew")
        band.grid_propagate(False)
        band.grid_columnconfigure(0, weight=1)
        band.grid_rowconfigure(0, weight=1)
        ctk.CTkLabel(band, text=cat.icon or "📚",
                      font=ctk.CTkFont(size=32), text_color="white").grid(row=0, column=0)

        ctk.CTkLabel(card, text=cat.name,
                      font=ctk.CTkFont(size=16, weight="bold")).grid(
            row=1, column=0, pady=(8, 2))

        count = Book.objects.filter(categories=cat).count()
        ctk.CTkLabel(card, text=f"{count} book{'s' if count != 1 else ''}",
                      font=ctk.CTkFont(size=12), text_color=MUTED).grid(row=2, column=0)

        if cat.description:
            ctk.CTkLabel(card, text=cat.description,
                          font=ctk.CTkFont(size=11), text_color=MUTED,
                          wraplength=180, justify="center").grid(
                row=3, column=0, padx=14, pady=(6, 0))

        n = cat.name
        ctk.CTkButton(card, text="Browse →", height=36, corner_radius=10,
                       font=ctk.CTkFont(size=12),
                       command=lambda name=n: self.show_books(preset_category=name)).grid(
            row=4, column=0, padx=14, pady=(10, 16), sticky="ew")

    # ════════════════════════════════════════════════════════════════════
    #  CHAT
    # ════════════════════════════════════════════════════════════════════

    def show_chat(self, *, prefill: str | None = None):
        self._clear_main()
        self._activate_nav("💬  Chat")

        self._conv    = orm_conversation()
        self._msg_row = 0

        outer = ctk.CTkFrame(self._main, fg_color="transparent")
        outer.grid(row=0, column=0, sticky="nsew")
        outer.grid_columnconfigure(0, weight=1)
        outer.grid_rowconfigure(1, weight=1)

        # ── Top bar ──
        topbar = ctk.CTkFrame(outer, corner_radius=14, height=58)
        topbar.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 8))
        topbar.grid_columnconfigure(1, weight=1)
        topbar.grid_propagate(False)

        ctk.CTkLabel(topbar, text="💬  Booky.tn AI",
                      font=ctk.CTkFont(size=17, weight="bold")).grid(
            row=0, column=0, padx=18, pady=14)

        self._status_lbl = ctk.CTkLabel(topbar, text="●  Checking…",
                                         font=ctk.CTkFont(size=12),
                                         text_color=MUTED)
        self._status_lbl.grid(row=0, column=1, padx=10, sticky="w")

        ctk.CTkLabel(topbar, text="Model:", font=ctk.CTkFont(size=12),
                      text_color=MUTED).grid(row=0, column=2, padx=(6, 3))

        self._model_menu = ctk.CTkOptionMenu(
            topbar, values=[self._model], width=158, height=34,
            corner_radius=8,
            command=lambda m: setattr(self, "_model", m))
        self._model_menu.grid(row=0, column=3, padx=(0, 8))

        ctk.CTkButton(topbar, text="🗑  Clear",
                       width=80, height=34, corner_radius=8,
                       fg_color=RED, hover_color="#DC2626",
                       font=ctk.CTkFont(size=12),
                       command=self._clear_chat).grid(row=0, column=4, padx=(0, 14))

        # ── Messages pane ──
        self._chat_pane = ctk.CTkScrollableFrame(outer, fg_color="transparent")
        self._chat_pane.grid(row=1, column=0, sticky="nsew", padx=16)
        self._chat_pane.grid_columnconfigure(0, weight=1)

        # Replay saved history
        history = orm_history(self._conv)
        if history:
            for msg in history:
                if msg["role"] == "user":
                    self._add_user_bubble(msg["content"], save=False)
                else:
                    self._add_assistant_bubble(msg["content"])
        else:
            self._add_assistant_bubble(
                "Hello! I'm Booky — your AI library companion.\n"
                "Ask me for recommendations, info about a book, or anything about our catalog!"
            )

        # ── Suggestion chips ──
        chips = ctk.CTkFrame(outer, fg_color="transparent")
        chips.grid(row=2, column=0, padx=16, pady=(6, 4), sticky="ew")
        for i, (emoji, text) in enumerate([
            ("📡", "Recommend a sci-fi novel"),
            ("🔍", "What mystery books do you have?"),
            ("⭐", "Best-rated books in the library"),
        ]):
            ctk.CTkButton(chips, text=f"  {emoji}  {text}  ",
                           height=32, corner_radius=16,
                           fg_color="transparent", border_width=1,
                           border_color=("gray65", "gray38"),
                           text_color=("gray15", "gray80"),
                           hover_color=("gray88", "gray22"),
                           font=ctk.CTkFont(size=11),
                           command=lambda t=text: self._dispatch_user_msg(t)).grid(
                row=0, column=i, padx=4)

        # ── Input bar ──
        input_bar = ctk.CTkFrame(outer, corner_radius=14, height=60)
        input_bar.grid(row=3, column=0, padx=16, pady=(4, 16), sticky="ew")
        input_bar.grid_columnconfigure(0, weight=1)
        input_bar.grid_propagate(False)

        self._chat_entry = ctk.CTkEntry(
            input_bar, placeholder_text="Ask about books, authors, or get a recommendation…",
            height=40, corner_radius=10, border_width=0,
            font=ctk.CTkFont(size=13))
        self._chat_entry.grid(row=0, column=0, padx=(14, 8), pady=10, sticky="ew")
        self._chat_entry.bind("<Return>", lambda _: self._on_send())

        self._send_btn = ctk.CTkButton(
            input_bar, text="Send  ➤", width=100, height=40,
            corner_radius=10, font=ctk.CTkFont(size=13, weight="bold"),
            command=self._on_send)
        self._send_btn.grid(row=0, column=1, padx=(0, 14), pady=10)

        self._check_ollama_status()
        self._update_model_menu()

        if prefill:
            self._chat_entry.insert(0, prefill)

    # ── Chat helpers ──────────────────────────────────────────────────────────

    def _add_user_bubble(self, text: str, *, save: bool = True):
        wrap = ctk.CTkFrame(self._chat_pane, fg_color="transparent")
        wrap.grid(row=self._msg_row, column=0, sticky="ew", padx=8, pady=3)
        wrap.grid_columnconfigure(0, weight=1)

        bubble = ctk.CTkFrame(wrap, corner_radius=16,
                               fg_color=(PRIMARY, PRIMARY_DARK))
        bubble.grid(row=0, column=0, sticky="e", padx=(130, 0))
        ctk.CTkLabel(bubble, text=text, font=ctk.CTkFont(size=13),
                      wraplength=440, justify="left",
                      text_color="white").pack(padx=16, pady=11)

        self._msg_row += 1
        self.after(60, self._scroll_bottom)
        if save:
            orm_save_msg(self._conv, "user", text)

    def _add_assistant_bubble(self, text: str) -> ctk.CTkLabel:
        wrap = ctk.CTkFrame(self._chat_pane, fg_color="transparent")
        wrap.grid(row=self._msg_row, column=0, sticky="ew", padx=8, pady=3)
        wrap.grid_columnconfigure(1, weight=1)

        # Avatar circle
        av = ctk.CTkFrame(wrap, width=38, height=38, corner_radius=19,
                           fg_color=PRIMARY_PALE)
        av.grid(row=0, column=0, sticky="nw", padx=(0, 10), pady=4)
        av.grid_propagate(False)
        ctk.CTkLabel(av, text="📚", font=ctk.CTkFont(size=17)).place(
            relx=.5, rely=.5, anchor="center")

        bubble = ctk.CTkFrame(wrap, corner_radius=16)
        bubble.grid(row=0, column=1, sticky="w")
        clean = text.replace("**", "").replace("*", "").replace("`", "")
        label = ctk.CTkLabel(bubble, text=clean, font=ctk.CTkFont(size=13),
                              wraplength=530, justify="left")
        label.pack(padx=16, pady=11)

        self._msg_row += 1
        self.after(60, self._scroll_bottom)
        return label

    def _scroll_bottom(self):
        try:
            self._chat_pane._parent_canvas.yview_moveto(1.0)
        except Exception:
            pass

    def _clear_chat(self):
        orm_clear_conv()
        self._conv    = orm_conversation()
        self._msg_row = 0
        for w in self._chat_pane.winfo_children():
            w.destroy()
        self._add_assistant_bubble("Conversation cleared. How can I help you?")

    def _on_send(self):
        msg = self._chat_entry.get().strip()
        if not msg or self._streaming:
            return
        self._chat_entry.delete(0, "end")
        self._dispatch_user_msg(msg)

    def _dispatch_user_msg(self, msg: str):
        self._add_user_bubble(msg)
        placeholder = self._add_assistant_bubble("…")
        self._streaming = True
        self._send_btn.configure(state="disabled", text="…")
        threading.Thread(target=self._stream_ollama,
                         args=(placeholder,), daemon=True).start()

    def _library_context(self) -> str:
        from django.db import close_old_connections
        close_old_connections()
        lines = ["Library catalog:"]
        for b in Book.objects.select_related("author").prefetch_related("categories").order_by("title"):
            cats  = ", ".join(c.name for c in b.categories.all()) or "General"
            avail = "available" if b.is_available else "unavailable"
            lines.append(f"  • '{b.title}' by {b.author.name} [{cats}, ★{float(b.rating):.1f}] — {avail}")
        return "\n".join(lines)

    # ── Ollama ────────────────────────────────────────────────────────────────

    def _stream_ollama(self, label: ctk.CTkLabel):
        from django.db import close_old_connections
        close_old_connections()
        system = (
            "You are Booky, a knowledgeable and friendly library assistant. "
            "Help users discover books, give recommendations, and discuss literature. "
            "Be concise and warm.\n\n" + self._library_context()
        )
        msgs = [{"role": "system", "content": system}] + orm_history(self._conv)

        try:
            resp = requests.post(
                f"{OLLAMA_URL}/api/chat",
                json={"model": self._model, "messages": msgs, "stream": True},
                stream=True, timeout=90)
            full = ""
            for line in resp.iter_lines():
                if line:
                    try:
                        chunk = json.loads(line).get("message", {}).get("content", "")
                        if chunk:
                            full += chunk
                            clean = full.replace("**","").replace("*","").replace("`","")
                            self.after(0, lambda t=clean: _try(label, text=t))
                            self.after(0, self._scroll_bottom)
                    except json.JSONDecodeError:
                        pass
            if full:
                orm_save_msg(self._conv, "assistant", full)

        except requests.exceptions.ConnectionError:
            self.after(0, lambda: _try(
                label, text="❌  Ollama not reachable. Make sure it's running on localhost:11434"))
        except Exception as exc:
            self.after(0, lambda e=str(exc): _try(label, text=f"❌  Error: {e}"))

        self._streaming = False
        if hasattr(self, "_send_btn"):
            self.after(0, lambda: _try(self._send_btn, state="normal", text="Send  ➤"))

    def _check_ollama_status(self):
        def _check():
            try:
                ok = requests.get(f"{OLLAMA_URL}/api/tags", timeout=3).status_code == 200
                self.after(0, lambda: _try(
                    self._status_lbl,
                    text="●  Ollama Online" if ok else "●  Ollama Error",
                    text_color=GREEN if ok else RED,
                ) if hasattr(self, "_status_lbl") else None)
            except Exception:
                self.after(0, lambda: _try(
                    self._status_lbl, text="●  Ollama Offline", text_color=RED,
                ) if hasattr(self, "_status_lbl") else None)
        threading.Thread(target=_check, daemon=True).start()

    def _fetch_models(self):
        def _load():
            try:
                r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=4)
                if r.status_code == 200:
                    models = [m["name"] for m in r.json().get("models", [])]
                    if models:
                        self._model = models[0]
                        self.after(0, lambda: self._update_model_menu(models))
            except Exception:
                pass
        threading.Thread(target=_load, daemon=True).start()

    def _update_model_menu(self, models: list[str] | None = None):
        if hasattr(self, "_model_menu"):
            try:
                if models:
                    self._model_menu.configure(values=models)
                self._model_menu.set(self._model)
            except Exception:
                pass


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = BiblioApp()
    app.mainloop()
