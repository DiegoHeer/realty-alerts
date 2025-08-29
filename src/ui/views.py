from django.db.models.query import QuerySet
from django.views.generic import ListView
from django.shortcuts import get_object_or_404
from django.db.models import Q

from ui.models import RealtyQuery
from ui.forms import ToggleQueryForm
from django.urls import reverse_lazy
from django.shortcuts import redirect
from django.http import HttpRequest


class RealtyQueryListView(ListView):
    model = RealtyQuery
    context_object_name = "queries"
    ordering = "updated_at"
    paginate_by = 10

    def get_queryset(self) -> QuerySet[RealtyQuery]:
        queryset = super().get_queryset()

        if search_query := self.request.GET.get("q", ""):
            queryset = queryset.filter(Q(name__icontains=search_query))

        return queryset

    def post(self, request: HttpRequest, *args, **kwargs):
        query_id = request.POST.get("query_id")
        query = get_object_or_404(RealtyQuery, id=query_id)
        form = ToggleQueryForm(request.POST, instance=query)
        if form.is_valid():
            form.save()

        return redirect(reverse_lazy("realty-query-list"))
