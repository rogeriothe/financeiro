from __future__ import annotations

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from ninja import NinjaAPI

from tarefas.api import router as tarefas_router

from .forms import StyledAuthenticationForm
from .views import dashboard_view, logout_view

api = NinjaAPI(title="Financeiro API", description="Main API for financeiro app")
api.add_router("/tarefas/", tarefas_router)

urlpatterns = [
    path("api/", api.urls),
    path("admin/", admin.site.urls),
    path("entries/", include("entries.urls")),
    path("cartao/", include("cartao.urls")),
    path("tarefas/", include("tarefas.urls")),
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
    path("", dashboard_view, name="dashboard"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
