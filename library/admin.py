from django.contrib import admin
from .models import Book, Author, Category

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'icon']

@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    list_display = ['name']

@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ['title', 'author', 'get_categories', 'available_copies', 'rating']
    list_filter = ['categories', 'language']
    search_fields = ['title', 'author__name']
    filter_horizontal = ['categories']
    fields = ['title', 'author', 'categories', 'description', 'cover_image', 'cover_color',
              'isbn', 'published_year', 'pages', 'language',
              'available_copies', 'total_copies', 'rating']

    @admin.display(description='Categories')
    def get_categories(self, obj):
        return ', '.join(c.name for c in obj.categories.all())
