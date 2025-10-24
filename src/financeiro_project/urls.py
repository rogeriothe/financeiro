from __future__ import annotations

from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from django.views.generic import RedirectView

from .forms import StyledAuthenticationForm
from .views import logout_view

urlpatterns = [
    path("admin/", admin.site.urls),
    path("entries/", include("entries.urls")),
    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="registration/login.html",
            redirect_authenticated_user=True,
            authentication_form=StyledAuthenticationForm,
        ),
        name="login",
    ),
    path("logout/", logout_view, name="logout"),
    path("", RedirectView.as_view(pattern_name="entries:list", permanent=False)),
]
