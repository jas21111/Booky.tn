import csv
import os
from django.core.management.base import BaseCommand
from django.db import transaction
from library.models import Book, Author

CSV_PATH = os.path.join(
    os.path.expanduser("~"), "Downloads", "archive", "books.csv"
)

COVER_COLORS = [
    "#C4778A", "#9A4D62", "#7D7D8D", "#8B6340",
    "#5B6A8A", "#6A7D5B", "#8A5B7D", "#5B7D8A",
]


def _parse_year(date_str: str) -> int | None:
    """Extract year from M/D/YYYY or YYYY."""
    date_str = date_str.strip()
    if not date_str:
        return None
    try:
        parts = date_str.split("/")
        if len(parts) == 3:
            return int(parts[2])
        return int(date_str[:4])
    except (ValueError, IndexError):
        return None


def _parse_pages(val: str) -> int | None:
    try:
        n = int(str(val).strip())
        return n if n > 0 else None
    except ValueError:
        return None


def _parse_rating(val: str) -> float:
    try:
        r = float(str(val).strip())
        return round(min(max(r, 0.0), 5.0), 1)
    except ValueError:
        return 4.0


def _language(code: str) -> str:
    mapping = {
        "eng": "English", "en-US": "English", "en-GB": "English",
        "fre": "French",  "spa": "Spanish",    "ger": "German",
        "ita": "Italian", "por": "Portuguese", "ara": "Arabic",
        "jpn": "Japanese","chi": "Chinese",     "rus": "Russian",
    }
    return mapping.get(code.strip(), code.strip().capitalize() or "English")


class Command(BaseCommand):
    help = "Import books from the Kaggle GoodReads CSV"

    def add_arguments(self, parser):
        parser.add_argument(
            "--file", default=CSV_PATH,
            help="Path to books.csv (default: ~/Downloads/archive/books.csv)",
        )
        parser.add_argument(
            "--limit", type=int, default=0,
            help="Max books to import (0 = all)",
        )
        parser.add_argument(
            "--skip-existing", action="store_true", default=True,
            help="Skip books whose title+author already exists (default: on)",
        )

    def handle(self, *args, **options):
        filepath = options["file"]
        limit    = options["limit"]

        if not os.path.exists(filepath):
            self.stderr.write(f"File not found: {filepath}")
            return

        self.stdout.write(f"Reading {filepath} ...")

        with open(filepath, encoding="utf-8", errors="replace") as f:
            # Strip leading/trailing spaces from column names
            reader = csv.DictReader(f)
            reader.fieldnames = [h.strip() for h in reader.fieldnames]
            rows = list(reader)

        if limit:
            rows = rows[:limit]

        self.stdout.write(f"Importing {len(rows)} books...")

        created = skipped = errors = 0
        author_cache: dict[str, Author] = {}

        with transaction.atomic():
            for i, row in enumerate(rows, 1):
                try:
                    title = row.get("title", "").strip()
                    if not title:
                        skipped += 1
                        continue

                    # First author only (some entries have "Author1/Author2")
                    raw_authors = row.get("authors", "Unknown").strip()
                    author_name = raw_authors.split("/")[0].strip() or "Unknown"

                    # Get or create author
                    if author_name not in author_cache:
                        author_obj, _ = Author.objects.get_or_create(
                            name=author_name,
                            defaults={"bio": ""}
                        )
                        author_cache[author_name] = author_obj
                    author_obj = author_cache[author_name]

                    # Skip duplicate title+author
                    if Book.objects.filter(title=title, author=author_obj).exists():
                        skipped += 1
                        continue

                    year  = _parse_year(row.get("publication_date", ""))
                    pages = _parse_pages(row.get("num_pages", ""))
                    isbn  = row.get("isbn", "").strip()[:20]
                    lang  = _language(row.get("language_code", "eng"))
                    rating = _parse_rating(row.get("average_rating", "4.0"))
                    color  = COVER_COLORS[i % len(COVER_COLORS)]

                    Book.objects.create(
                        title=title,
                        author=author_obj,
                        description="",
                        isbn=isbn,
                        published_year=year,
                        pages=pages,
                        language=lang,
                        rating=rating,
                        cover_color=color,
                        available_copies=1,
                        total_copies=1,
                    )
                    created += 1

                    if i % 500 == 0:
                        self.stdout.write(f"  ... {i}/{len(rows)} processed")

                except Exception as exc:
                    errors += 1
                    if errors <= 5:
                        self.stderr.write(f"  Row {i} error: {exc}")

        self.stdout.write(self.style.SUCCESS(
            f"\nDone -- {created} imported, {skipped} skipped, {errors} errors."
        ))
