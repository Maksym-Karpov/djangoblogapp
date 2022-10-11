from django.conf import settings
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.generic import (
    ListView,
    DetailView,
    TemplateView
)
from django.core.mail import send_mail
from django.contrib.postgres.search import SearchVector
from django.views.generic.detail import SingleObjectMixin
from django.views.generic.edit import FormView
from django.views import View
from django.views.generic.list import MultipleObjectMixin

from taggit.models import Tag
from .models import Post
from .forms import EmailPostForm, CommentForm, SearchForm


class PostListView(ListView):
    template_name = 'blog/post/list.html'
    context_object_name = 'posts'
    model = Post
    paginate_by = 3
    tag = None

    def dispatch(self, request, tag_slug=None, *args, **kwargs):
        if tag_slug:
            self.tag = get_object_or_404(Tag, slug=tag_slug)
        return super(PostListView, self).dispatch(
            request, tag=None, *args, **kwargs
        )

    def get_queryset(self):
        queryset = super(PostListView, self).get_queryset().prefetch_related(
            'tags'
        ).select_related('author')
        if self.tag:
            queryset = queryset.filter(tags=self.tag)
        return queryset

    def get_context_data(self, *, object_list=None, **kwargs):
        context_data = super(PostListView, self).get_context_data(
            object_list=None, **kwargs
        )
        context_data.update({'tag': self.tag})
        return context_data


class PostCommentsMixin:
    template_name = 'blog/post/detail.html'
    slug_url_kwarg = 'post'
    context_object_name = 'post'
    model = Post

    def get_queryset(self):
        queryset = super(PostCommentsMixin, self).get_queryset()
        year, month, day = self.resolve_year_month_date().values()

        return queryset.filter(
            publish__year=year,
            publish__month=month,
            publish__day=day
        )

    def resolve_year_month_date(self):
        return dict(
            year=self.kwargs['year'],
            month=self.kwargs['month'],
            day=self.kwargs['day']
        )


class PostDetailView(PostCommentsMixin, DetailView):
    def get_context_data(self, **kwargs):
        context_data = super(PostDetailView, self).get_context_data(**kwargs)
        comments = self.object.comments.filter(active=True)
        similar_posts = self.object.tags.similar_objects()
        context_data.update({
            'comments': comments,
            'similar_posts': similar_posts,
            'form': CommentForm()
        })
        return context_data


class PostComment(PostCommentsMixin, SingleObjectMixin, FormView):
    def post(self, request, *args, **kwargs):
        form = self.get_form()
        if form.is_valid():
            new_comment = form.save(commit=False)
            new_comment.post = self.get_object()
            new_comment.save()
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def get_success_url(self):
        return reverse(
            'blog:post_detail',
            kwargs={
                **self.resolve_year_month_date(),
                self.slug_url_kwarg: self.kwargs[self.slug_url_kwarg]
            }
        )


class PostDetail(View):
    def get(self, request, *args, **kwargs):
        view = PostDetailView.as_view()
        return view(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        view = PostComment.as_view()
        return view(request, *args, **kwargs)


class PostShareFormView(FormView):
    template_name = 'blog/post/share.html'
    form_class = EmailPostForm
    post_to_sent = None

    def dispatch(self, request, post_id, *args, **kwargs):
        self.post_to_sent = get_object_or_404(Post.published.all(),
                                      id=post_id)
        return super(PostShareFormView, self).dispatch(
            request,
            *args,
            **kwargs
        )

    def get_success_url(self):
        return reverse(
            'blog:post_detail',
            kwargs={
                'year': self.post_to_sent.publish.year,
                'month': self.post_to_sent.publish.month,
                'day': self.post_to_sent.publish.day,
                'post': self.post_to_sent.slug
            }
        )

    def form_valid(self, form):
        post_url = self.request.build_absolute_uri(
            self.post_to_sent.get_absolute_url()
        )
        cleaned_data = form.cleaned_data
        subject = f'{cleaned_data["name"]} ({cleaned_data["email"]}) ' \
                  f'recommends you reading {self.post_to_sent.title}'
        message = f'Read "{self.post_to_sent.title}" at {post_url}\n\n' \
                  f'{cleaned_data["name"]}\'s comments: ' \
                  f'{cleaned_data["comment"]}'

        send_mail(subject, message, settings.EMAIL_HOST_USER,
                  [cleaned_data['to']])

        return super(PostShareFormView, self).form_valid(form=form)

    def get_context_data(self, **kwargs):
        context_data = super(PostShareFormView, self).get_context_data(
            **kwargs
        )
        context_data.update({
            'post': self.post_to_sent,
        })
        return context_data


class PostSearchFormView(MultipleObjectMixin, TemplateView):
    template_name = 'blog/post/search.html'
    model = Post

    def get_queryset(self, query=None):
        queryset = super(PostSearchFormView, self).get_queryset()
        if query:
            queryset = queryset.annotate(search=SearchVector(
                'title', 'body'
            )).filter(search=query)
        return queryset

    def get_context_data(self, *, object_list=None, **kwargs):
        context_data = super().get_context_data(
            object_list=self.get_queryset(),
            **kwargs
        )

        form = SearchForm()
        if self.request.GET.get('query'):
            form = SearchForm(self.request.GET)

        if form.is_valid():
            query = form.cleaned_data['query']
            results = self.get_queryset(query=query)
            context_data.update({
                'query': query,
                'results': results
            })
        context_data['form'] = form
        return context_data
