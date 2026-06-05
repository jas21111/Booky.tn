from django.db import models


class Category(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, default='📚')

    class Meta:
        verbose_name_plural = 'categories'
        ordering = ['name']

    def __str__(self):
        return self.name


class Author(models.Model):
    name = models.CharField(max_length=200)
    bio = models.TextField(blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Book(models.Model):
    title = models.CharField(max_length=300)
    author = models.ForeignKey(Author, on_delete=models.CASCADE, related_name='books')
    categories = models.ManyToManyField(Category, blank=True, related_name='books')
    description = models.TextField()
    isbn = models.CharField(max_length=20, blank=True)
    published_year = models.IntegerField(null=True, blank=True)
    available_copies = models.IntegerField(default=1)
    total_copies = models.IntegerField(default=1)
    cover_color = models.CharField(max_length=20, default='#4F46E5')
    cover_image = models.ImageField(upload_to='book_covers/', blank=True, null=True)
    rating = models.DecimalField(max_digits=3, decimal_places=1, default=4.0)
    pages = models.IntegerField(null=True, blank=True)
    language = models.CharField(max_length=50, default='English')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['title']

    def __str__(self):
        return f"{self.title} by {self.author}"

    @property
    def is_available(self):
        return self.available_copies > 0
