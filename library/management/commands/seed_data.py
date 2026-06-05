from django.core.management.base import BaseCommand
from library.models import Category, Author, Book


class Command(BaseCommand):
    help = 'Seed the database with sample library data'

    def handle(self, *args, **kwargs):
        self.stdout.write('Seeding database...')

        categories_data = [
            ('Fiction', 'Novels and stories from imagination', '📖'),
            ('Science Fiction', 'Futuristic and speculative stories', '🚀'),
            ('Mystery & Thriller', 'Suspenseful and detective stories', '🔍'),
            ('History', 'Historical accounts and biographies', '🏛️'),
            ('Science', 'Scientific discoveries and concepts', '🔬'),
            ('Philosophy', 'Philosophical thought and ethics', '💭'),
            ('Technology', 'Computing, AI, and digital world', '💻'),
            ('Self-Help', 'Personal development and growth', '🌟'),
        ]

        categories = {}
        for name, desc, icon in categories_data:
            cat, _ = Category.objects.get_or_create(name=name, defaults={'description': desc, 'icon': icon})
            categories[name] = cat

        authors_data = [
            ('George Orwell', 'English novelist and essayist known for dystopian fiction'),
            ('Harper Lee', 'American novelist known for To Kill a Mockingbird'),
            ('F. Scott Fitzgerald', 'American novelist of the Jazz Age'),
            ('Isaac Asimov', 'American author and biochemist known for science fiction'),
            ('Agatha Christie', 'English writer known as the Queen of Crime'),
            ('Yuval Noah Harari', 'Israeli historian and author'),
            ('Carl Sagan', 'American astronomer, cosmologist, and author'),
            ('Marcus Aurelius', 'Roman emperor and Stoic philosopher'),
            ('J.R.R. Tolkien', 'English author of high fantasy works'),
            ('Jane Austen', 'English novelist known for romantic fiction'),
            ('Albert Camus', 'French philosopher and Nobel laureate'),
            ('Stephen Hawking', 'English theoretical physicist and cosmologist'),
        ]

        authors = {}
        for name, bio in authors_data:
            author, _ = Author.objects.get_or_create(name=name, defaults={'bio': bio})
            authors[name] = author

        books_data = [
            ('1984', 'George Orwell', 'Fiction',
             'A dystopian social science fiction novel and cautionary tale about totalitarianism. Winston Smith navigates a world of perpetual war, omnipresent government surveillance, and public manipulation.',
             1949, 3, 3, '#DC2626', 4.7, 328),
            ('Animal Farm', 'George Orwell', 'Fiction',
             'A satirical allegory of Soviet totalitarianism. Farm animals overthrow their human farmer hoping for a better life, only to face a new tyranny.',
             1945, 5, 5, '#DC2626', 4.5, 112),
            ('To Kill a Mockingbird', 'Harper Lee', 'Fiction',
             'A novel about racial injustice and moral growth in the American South, told through the eyes of young Scout Finch as her father defends a Black man wrongly accused of a crime.',
             1960, 2, 3, '#059669', 4.8, 281),
            ('The Great Gatsby', 'F. Scott Fitzgerald', 'Fiction',
             'A portrayal of the Jazz Age, critiquing the American Dream through the story of the mysterious millionaire Jay Gatsby and his obsession with Daisy Buchanan.',
             1925, 4, 4, '#D97706', 4.4, 180),
            ('Foundation', 'Isaac Asimov', 'Science Fiction',
             'The first novel of the Foundation series. A mathematician develops psychohistory, a way to predict the future, and foresees the collapse of the Galactic Empire.',
             1951, 3, 4, '#7C3AED', 4.6, 244),
            ('I, Robot', 'Isaac Asimov', 'Science Fiction',
             'A collection of science fiction short stories exploring the Three Laws of Robotics and the relationship between humans and machines.',
             1950, 5, 5, '#7C3AED', 4.5, 253),
            ('Murder on the Orient Express', 'Agatha Christie', 'Mystery & Thriller',
             'Hercule Poirot investigates the murder of an American businessman aboard the Orient Express. All suspects have alibis — or do they?',
             1934, 3, 3, '#1D4ED8', 4.7, 256),
            ('And Then There Were None', 'Agatha Christie', 'Mystery & Thriller',
             'Ten strangers are lured to an isolated island and begin to be killed off one by one. The most popular mystery novel of all time.',
             1939, 2, 3, '#1D4ED8', 4.8, 264),
            ('Sapiens: A Brief History of Humankind', 'Yuval Noah Harari', 'History',
             'Explores the history of humanity from the emergence of Homo sapiens to the 21st century, examining how biology and history have defined humanity.',
             2011, 4, 5, '#B45309', 4.6, 443),
            ('Cosmos', 'Carl Sagan', 'Science',
             'A personal voyage through the universe, exploring the connections between science, nature, and human history. Companion book to the TV series.',
             1980, 3, 3, '#0369A1', 4.8, 365),
            ('Meditations', 'Marcus Aurelius', 'Philosophy',
             'A series of personal writings by the Roman emperor, recording his private notes on Stoic philosophy and self-discipline. A timeless guide to life.',
             180, 6, 6, '#4B5563', 4.9, 254),
            ('The Lord of the Rings', 'J.R.R. Tolkien', 'Fiction',
             'An epic high-fantasy novel following the Fellowship of the Ring on their quest to destroy the One Ring and defeat the Dark Lord Sauron.',
             1954, 2, 4, '#166534', 4.9, 1178),
            ('Pride and Prejudice', 'Jane Austen', 'Fiction',
             'Elizabeth Bennet navigates issues of manners, upbringing, morality, and marriage in early 19th-century England, sparring with the proud Mr. Darcy.',
             1813, 5, 5, '#BE185D', 4.7, 432),
            ('The Stranger', 'Albert Camus', 'Philosophy',
             'The story of Meursault, an emotionally detached French Algerian who kills an Arab man and faces existential questions about meaning and mortality.',
             1942, 4, 4, '#92400E', 4.4, 159),
            ('A Brief History of Time', 'Stephen Hawking', 'Science',
             'An exploration of the universe from the Big Bang to black holes, written for general audiences. One of the most influential science books ever written.',
             1988, 3, 4, '#1E40AF', 4.7, 212),
        ]

        for title, author_name, cat_name, desc, year, avail, total, color, rating, pages in books_data:
            book, _ = Book.objects.get_or_create(
                title=title,
                defaults={
                    'author': authors[author_name],
                    'description': desc,
                    'published_year': year,
                    'available_copies': avail,
                    'total_copies': total,
                    'cover_color': color,
                    'rating': rating,
                    'pages': pages,
                }
            )
            book.categories.add(categories[cat_name])

        self.stdout.write(self.style.SUCCESS(
            f'Seeded {Book.objects.count()} books, {Author.objects.count()} authors, {Category.objects.count()} categories.'
        ))
