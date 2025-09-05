from django.urls import reverse_lazy
from dataclasses import dataclass, asdict


@dataclass
class Breadcrumb:
    title: str
    url: str

    def dict(self) -> dict[str, str]:
        return asdict(self)


class BreadcrumbMixin:
    breadcrumbs: list[Breadcrumb] = [Breadcrumb(title="Home", url=reverse_lazy("home"))]

    def get_breadcrumbs(self) -> list[Breadcrumb]:
        return self.breadcrumbs

    def get_context_data(self, **kwargs) -> dict:
        context_data = super().get_context_data(**kwargs)
        context_data["breadcrumbs"] = [breadcrumb.dict() for breadcrumb in self.get_breadcrumbs()]
        return context_data
