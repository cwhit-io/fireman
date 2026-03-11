from django.shortcuts import render


def index(request):
    return render(request, "core/index.html")


def homepage(request):
    return render(request, "home.html")
