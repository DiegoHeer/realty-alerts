from django.views.generic import ListView

from ui.models import RealtyQuery


class RealtyQueryListView(ListView):
    model = RealtyQuery
    ordering = "updated_at"
    paginate_by = 25
