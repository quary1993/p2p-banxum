from __future__ import annotations

from django.urls import path

from backend.apps.smart_invest.api.views import (
    SmartInvestChannelsView,
    SmartInvestPauseView,
    SmartInvestResumeView,
    SmartInvestView,
)

urlpatterns = [
    path("", SmartInvestView.as_view(), name="smart-invest"),
    path("pause/", SmartInvestPauseView.as_view(), name="smart-invest-pause"),
    path("resume/", SmartInvestResumeView.as_view(), name="smart-invest-resume"),
    path(
        "notifications/",
        SmartInvestChannelsView.as_view(),
        name="smart-invest-notifications",
    ),
]
