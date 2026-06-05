from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import UserCreationForm
from django.utils.http import url_has_allowed_host_and_scheme


def login_view(request):
    if request.user.is_authenticated:
        return redirect('library:home')

    error = None
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            next_url = request.POST.get('next') or request.GET.get('next') or ''
            if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
                return redirect(next_url)
            return redirect('library:home')
        error = 'Invalid username or password.'

    return render(request, 'accounts/login.html', {
        'error': error,
        'next': request.GET.get('next', ''),
    })


def signup_view(request):
    if request.user.is_authenticated:
        return redirect('library:home')

    form = UserCreationForm()
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('library:home')

    return render(request, 'accounts/signup.html', {'form': form})


def logout_view(request):
    if request.method == 'POST':
        logout(request)
    return redirect('accounts:login')
