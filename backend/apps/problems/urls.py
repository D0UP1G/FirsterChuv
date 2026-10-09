from django.urls import path

from .views import AdminProblemVersionListView

urlpatterns = [
    path("problems", AdminProblemVersionListView.as_view(), name="problem-catalog"),
]
