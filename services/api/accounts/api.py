from ninja import Router

from accounts.auth import JWTAuth
from accounts.models import UserPreferences
from accounts.schemas import SearchPrefOut

me_router = Router(auth=JWTAuth())


@me_router.get("/preferences/search", response=SearchPrefOut)
def get_search_preferences(request):
    prefs = UserPreferences.objects.filter(user=request.user).first()
    if prefs is None:
        return {"search": None, "updated_at": None}
    return {"search": prefs.search or None, "updated_at": prefs.search_updated_at}
