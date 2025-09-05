from django.db.models.query import QuerySet
from django.views.generic import ListView, DetailView, TemplateView
from django.views.generic.list import MultipleObjectMixin
from django.shortcuts import get_object_or_404
from django.db.models import Q

from ui.models import RealtyQuery, RealtyResult
from ui.forms import TogglePeriodicTaskForm
from django.urls import reverse_lazy
from django.shortcuts import redirect
from django.http import HttpRequest
from django.utils import timezone
from ui.mixins import BreadcrumbMixin, Breadcrumb

class HomeView(TemplateView):
    template_name = "ui/home.html"

    def get_context_data(self, **kwargs) -> dict:
        context = super().get_context_data(**kwargs)

        query_list_response = RealtyQueryListView.as_view()(self.request)
        context.update(query_list_response.context_data)

        return context


class RealtyQueryListView(BreadcrumbMixin, ListView):
    model = RealtyQuery
    context_object_name = "queries"
    template_name = "ui/partials/query-list.html"
    paginate_by = 10

    def get_queryset(self) -> QuerySet[RealtyQuery]:
        queryset = super().get_queryset()

        if search_query := self.request.GET.get("q", ""):
            queryset = queryset.filter(Q(name__icontains=search_query))

        return queryset

    def get_context_data(self, **kwargs) -> dict:
        context_data = super().get_context_data(**kwargs)

        for query in context_data["queries"]:
            self._annotate_result_counts(query)

        return context_data

    def _annotate_result_counts(self, query: RealtyQuery) -> None:
        today = timezone.now().date()

        query.new_results_count = query.results.filter(created_at__date__gte=today).count()

    def post(self, request: HttpRequest, *args, **kwargs):
        query_id = request.POST.get("query_id")
        query = get_object_or_404(RealtyQuery, id=query_id)
        form = TogglePeriodicTaskForm(request.POST, instance=query.periodic_task)
        if form.is_valid():
            form.save()

        return redirect(reverse_lazy("realty-query-list"))


class RealtyQueryDetailView(BreadcrumbMixin, MultipleObjectMixin, DetailView):
    model = RealtyQuery
    paginate_by = 5

    def get_breadcrumbs(self):
        query = self.get_object()
        return [
            Breadcrumb(title="Home", url=reverse_lazy("realty-query-list")),
            Breadcrumb(title=query.name, url=reverse_lazy("realty-query-detail", kwargs={"pk": query.pk})),
        ]

    def _get_results_queryset(self) -> QuerySet[RealtyResult]:
        query = self.get_object()
        queryset = query.results.all()

        if search_query := self.request.GET.get("q", ""):
            queryset = queryset.filter(Q(title__icontains=search_query) | Q(price__icontains=search_query))

        return queryset

    def get_context_data(self, **kwargs):
        results_queryset = self._get_results_queryset()

        context_data = super().get_context_data(object_list=results_queryset, **kwargs)
        context_data["results"] = context_data["object_list"]

        return context_data
