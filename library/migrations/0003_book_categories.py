from django.db import migrations, models


def copy_category_to_categories(apps, schema_editor):
    """Copy each book's single category FK into the new M2M field."""
    Book = apps.get_model('library', 'Book')
    for book in Book.objects.all():
        if book.category_id:
            book.categories.add(book.category_id)


class Migration(migrations.Migration):

    dependencies = [
        ('library', '0002_book_cover_image'),
    ]

    operations = [
        # 1. Add M2M with a temporary related_name (avoids clash with the FK's 'books')
        migrations.AddField(
            model_name='book',
            name='categories',
            field=models.ManyToManyField(
                blank=True,
                related_name='books_temp',
                to='library.category',
            ),
        ),
        # 2. Copy existing single-category assignments into the new M2M table
        migrations.RunPython(copy_category_to_categories, migrations.RunPython.noop),
        # 3. Drop the old FK column
        migrations.RemoveField(model_name='book', name='category'),
        # 4. Rename related_name to the final 'books' (FK is gone, no clash)
        migrations.AlterField(
            model_name='book',
            name='categories',
            field=models.ManyToManyField(
                blank=True,
                related_name='books',
                to='library.category',
            ),
        ),
    ]
