from __future__ import annotations

from django.urls import path

from backend.apps.smart_invest.api.views import SmartInvestDeactivateView, SmartInvestView

urlpatterns = [
    path("", SmartInvestView.as_view(), name="smart-invest"),
    path("deactivate/", SmartInvestDeactivateView.as_view(), name="smart-invest-deactivate"),
]
