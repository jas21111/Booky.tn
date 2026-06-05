import time
import warnings
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from library.models import Book

warnings.filterwarnings('ignore', category=InsecureRequestWarning)

COVER_BY_ISBN  = "https://covers.openlibrary.org/b/isbn/{isbn}-L.jpg"
SEARCH_BY_TITLE = "https://openlibrary.org/search.json?title={title}&limit=1&fields=cover_i"
COVER_BY_ID    = "https://covers.openlibrary.org/b/id/{id}-L.jpg"


def fetch_bytes(url):
    try:
        r = requests.get(url, timeout=12, verify=False)
        if r.status_code == 200 and len(r.content) > 2000:
            return r.content
    except Exception:
        pass
    return None


def find_cover(isbn, title):
    if isbn:
        data = fetch_bytes(COVER_BY_ISBN.format(isbn=isbn))
        if data:
            return data

    try:
        r = requests.get(
            SEARCH_BY_TITLE.format(title=requests.utils.quote(title)),
            timeout=10, verify=False
        )
        if r.status_code == 200:
            docs = r.json().get('docs', [])
            if docs and docs[0].get('cover_i'):
                data = fetch_bytes(COVER_BY_ID.format(id=docs[0]['cover_i']))
                if data:
                    return data
    except Exception:
        pass
    return None


class Command(BaseCommand):
    help = 'Fetch book cover images from Open Library'

    def handle(self, *args, **kwargs):
        books = Book.objects.filter(cover_image='')
        total = books.count()
        self.stdout.write(f"Fetching covers for {total} books via Open Library...")

        success = 0
        failed = 0

        for i, book in enumerate(books, 1):
            self.stdout.write(f"[{i}/{total}] {book.title[:50]}", ending=' ... ')
            self.stdout.flush()

            data = find_cover(book.isbn, book.title)

            if data:
                filename = f"{book.isbn or book.pk}.jpg"
                book.cover_image.save(filename, ContentFile(data), save=True)
                self.stdout.write(self.style.SUCCESS("saved"))
                success += 1
            else:
                self.stdout.write(self.style.WARNING("not found"))
                failed += 1

            time.sleep(0.25)

        self.stdout.write(self.style.SUCCESS(
            f"\nDone: {success} covers saved, {failed} not found."
        ))
