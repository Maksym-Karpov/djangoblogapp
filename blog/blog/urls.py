from django.urls import path
from . import views

urlpatterns = [
    # post views
    path('', views.PostListView.as_view(), name='post_list'),
    path('tag/<slug:tag_slug>/',
         views.PostListView.as_view(), name='post_list_by_tag'),
    path('<int:year>/<int:month>/<int:day>/<slug:post>/',
         views.PostDetail.as_view(),
         name='post_detail'),
    path('<int:post_id>/share/',
         views.PostShareFormView.as_view(), name='post_share'),
    path('search/', views.PostSearchFormView.as_view(), name='post_search')
]

app_name = 'blog'
