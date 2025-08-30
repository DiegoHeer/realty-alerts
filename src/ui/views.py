from django.db.models.query import QuerySet
from django.views.generic import ListView
from django.shortcuts import get_object_or_404
from django.db.models import Q

from ui.models import RealtyQuery
from ui.forms import TogglePeriodicTaskForm
from django.urls import reverse_lazy
from django.shortcuts import redirect
from django.http import HttpRequest
from django.utils import timezone


class RealtyQueryListView(ListView):
    model = RealtyQuery
    context_object_name = "queries"
    ordering = "-periodic_task__last_run_at"
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
