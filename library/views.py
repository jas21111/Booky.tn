from django.shortcuts import render, get_object_or_404
from django.db.models import Q
from .models import Book, Category, Author


def home(request):
    categories = Category.objects.all()
    featured_books = Book.objects.select_related('author').prefetch_related('categories').order_by('-created_at')[:8]
    total_books = Book.objects.count()
    total_available = Book.objects.filter(available_copies__gt=0).count()
    return render(request, 'library/home.html', {
        'categories': categories,
        'featured_books': featured_books,
        'total_books': total_books,
        'total_available': total_available,
    })


def book_list(request):
    books = Book.objects.select_related('author').prefetch_related('categories').all()
    categories = Category.objects.all()
    query = request.GET.get('q', '')
    category_id = request.GET.get('category', '')
    available_only = request.GET.get('available', '')

    if query:
        books = books.filter(
            Q(title__icontains=query) |
            Q(author__name__icontains=query) |
            Q(description__icontains=query)
        )
    if category_id:
        books = books.filter(categories__id=category_id).distinct()
    if available_only:
        books = books.filter(available_copies__gt=0)

    return render(request, 'library/book_list.html', {
        'books': books,
        'categories': categories,
        'query': query,
        'selected_category': category_id,
        'available_only': available_only,
    })


def book_detail(request, pk):
    book = get_object_or_404(
        Book.objects.select_related('author').prefetch_related('categories'), pk=pk)
    related_books = Book.objects.filter(
        categories__in=book.categories.all()).exclude(pk=pk).distinct()[:4]
    return render(request, 'library/book_detail.html', {
        'book': book,
        'related_books': related_books,
    })


def category_list(request):
    categories = Category.objects.all()
    return render(request, 'library/category_list.html', {'categories': categories})
