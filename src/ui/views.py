from urllib.parse import urljoin
from django.db.models.query import QuerySet
from django.views.generic import ListView, DetailView, TemplateView
from django.shortcuts import get_object_or_404, render
from django.db.models import Q

from enums import QueryResultStatus
from notifications import send_a_test_message
from settings import SETTINGS
from ui.models import RealtyQuery, RealtyResult, validate_query_url
from ui.forms import RealtyQueryForm, TogglePeriodicTaskForm
from django.urls import reverse_lazy
from django.http import HttpRequest, HttpResponse
from django.utils import timezone
from ui.mixins import BreadcrumbMixin, Breadcrumb
from django.views.decorators.http import require_POST, require_http_methods
from django.core.exceptions import ValidationError
from requests.exceptions import HTTPError


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


# TODO: write tests
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

        context_data["form"] = RealtyQueryForm()

        return context_data


# TODO: finish this
@require_POST
def create_query(request: HttpRequest) -> HttpResponse:
    form = RealtyQueryForm(request.POST)
    if form.is_valid():
        pass


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


# TODO: write tests
@require_http_methods(["DELETE"])
def archive_result(request: HttpRequest, pk: int) -> HttpResponse:
    """This method won't delete the query result from the database,
    to avoid situations where the same result is being scraped and shown again.
    """
    result = get_object_or_404(RealtyResult, pk=pk)
    result.status = QueryResultStatus.ARCHIVED
    result.save()

    # TODO: implement a sonnet functionality
    context = {
        "message": f"Query result '{result.title}' successfully deleted",
        "results": result.query.results.all(),
    }

    return render(request, "ui/partials/result-list.html", context)


@require_POST
def check_query_name(request: HttpRequest) -> HttpResponse:
    query_name = request.POST.get("name")
    if RealtyQuery.objects.filter(name=query_name).exists():
        return HttpResponse("This query name already exists")
    else:
        return HttpResponse()


@require_POST
def check_query_url(request: HttpRequest) -> HttpResponse:
    if query_url := request.POST.get("query_url"):
        try:
            validate_query_url(query_url)
        except ValidationError as exc:
            return HttpResponse(exc.message)

    return HttpResponse()


@require_POST
def check_ntfy_topic(request: HttpRequest) -> HttpResponse:
    url = urljoin(SETTINGS.ntfy_url, request.POST.get("ntfy_topic"))
    try:
        send_a_test_message(url)
        success = True
    except HTTPError:
        success = False

    return render(request, "ui/partials/success-failure-icon.html", {"success": success})
