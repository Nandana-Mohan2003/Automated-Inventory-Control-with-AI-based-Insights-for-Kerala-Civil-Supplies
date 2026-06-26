from django.contrib import admin
from django.urls import path, include
from django.http import FileResponse
import os

BASE = os.path.dirname(os.path.dirname(__file__))

def serve_sw(request):
    path_ = os.path.join(BASE, 'mainapp', 'static', 'sw.js')
    return FileResponse(open(path_, 'rb'), content_type='application/javascript')

def serve_manifest(request):
    path_ = os.path.join(BASE, 'mainapp', 'static', 'manifest.json')
    return FileResponse(open(path_, 'rb'), content_type='application/json')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('sw.js', serve_sw),
    path('manifest.json', serve_manifest),
    path('', include('mainapp.urls')),
]
