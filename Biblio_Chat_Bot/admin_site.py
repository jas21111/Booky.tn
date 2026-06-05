from django.contrib import admin


class BookyAdminSite(admin.AdminSite):
    site_header = 'Booky.tn'
    site_title = 'Booky.tn Admin'
    index_title = 'Dashboard'

    def index(self, request, extra_context=None):
        from library.models import Book, Author, Category
        from chat.models import Conversation
        from django.contrib.auth.models import User

        extra_context = extra_context or {}
        extra_context.update({
            'total_books':         Book.objects.count(),
            'available_books':     Book.objects.filter(available_copies__gt=0).count(),
            'borrowed_books':      Book.objects.filter(available_copies=0).count(),
            'total_authors':       Author.objects.count(),
            'total_categories':    Category.objects.count(),
            'total_users':         User.objects.count(),
            'total_conversations': Conversation.objects.count(),
            'recent_books':        Book.objects.select_related('author').order_by('-created_at')[:6],
            'unavailable_books':   Book.objects.select_related('author').filter(available_copies=0)[:5],
        })
        return super().index(request, extra_context)
