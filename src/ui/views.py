from django.db.models.query import QuerySet
from django.views.generic import ListView, DetailView, TemplateView
from django.shortcuts import get_object_or_404, render
from django.db.models import Q

from ui.models import RealtyQuery, RealtyResult
from ui.forms import RealtyQueryForm, TogglePeriodicTaskForm
from django.urls import reverse_lazy
from django.http import HttpRequest, HttpResponse
from django.utils import timezone
from ui.mixins import BreadcrumbMixin, Breadcrumb
from django.views.decorators.http import require_POST


class HomeView(BreadcrumbMixin, TemplateView):
    template_name = "ui/home.html"

    def get_context_data(self, **kwargs) -> dict:
        context_data = super().get_context_data(**kwargs)

        query_list_response = RealtyQueryListView.as_view()(self.request)
        context_data.update(query_list_response.context_data)

        context_data["form"] = RealtyQueryForm()

        return context_data


class RealtyQueryListView(ListView):
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


@require_POST
def query_toggle(request: HttpRequest, pk: int) -> HttpResponse:
    query = get_object_or_404(RealtyQuery, pk=pk)
    form = TogglePeriodicTaskForm(request.POST, instance=query.periodic_task)
    if form.is_valid():
        form.save()

    return render(request, "ui/partials/query-toggle.html", {"query": query})


class RealtyQueryDetailView(BreadcrumbMixin, DetailView):
    model = RealtyQuery
    context_object_name = "query"
    template_name = "ui/detail.html"

    def get_breadcrumbs(self):
        query = self.get_object()
        return [
            Breadcrumb(title="Home", url=reverse_lazy("home")),
            Breadcrumb(title=query.name, url=reverse_lazy("realty-query-detail", kwargs={"pk": query.pk})),
        ]

    def get_context_data(self, **kwargs) -> dict:
        context_data = super().get_context_data(**kwargs)

        result_list_response = RealtyResultsListView.as_view()(self.request, pk=self.object.pk)
        context_data.update(result_list_response.context_data)

        return context_data


class RealtyResultsListView(ListView):
    model = RealtyResult
    context_object_name = "results"
    template_name = "ui/partials/result-list.html"
    paginate_by = 5

    def get_queryset(self) -> QuerySet[RealtyQuery]:
        queryset = super().get_queryset()
        queryset = queryset.filter(query_id=self.kwargs["pk"])

        if search_query := self.request.GET.get("q", ""):
            queryset = queryset.filter(Q(title__icontains=search_query) | Q(price__icontains=search_query))

        return queryset
