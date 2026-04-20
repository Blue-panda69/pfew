"""
URL configuration for backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from core import views as core_views
from core.urls import admin_report_patterns

urlpatterns = [
    path('admin/', include((admin_report_patterns, 'core'), namespace='core')),
    path('admin/', admin.site.urls),
    path('api/', include('core.urls')),
    path('landing-page/<slug:slug>/', core_views.landing_page_view, name='landing_page'),
    path('landing-page/<slug:slug>/submit/', core_views.landing_page_form_submit, name='landing_page_submit'),
    path('phishing-blog-fr.html', core_views.phishing_blog_fr, name='phishing_blog_fr'),
    path('ckeditor/', include('ckeditor_uploader.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

