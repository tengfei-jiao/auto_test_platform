from django.urls import path, include
from test_plt import views


urlpatterns = [
    path('', views.index, name='index'),
]