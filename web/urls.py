from django.urls import path

from . import views

urlpatterns = [
    path("", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("files/", views.files_view, name="files"),
    path("files/<path:relative_path>/", views.download_view, name="download"),
]
