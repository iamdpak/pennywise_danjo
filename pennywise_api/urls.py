from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import RedirectView, SpectacularAPIView, SpectacularSwaggerView
urlpatterns = [
    path("", RedirectView.as_view(url="/api/docs/", permanent=False)),
    path("admin/", admin.site.urls),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
    path("api/v1/", include("apps.receipts.urls")),
]
