from __future__ import annotations

from django.urls import path

from backend.apps.communications.api.views import (
    NewsletterConfirmView,
    NewsletterSubscribeView,
    NewsletterUnsubscribeView,
    PublicEnquiryView,
)

urlpatterns = [
    path("enquiries/", PublicEnquiryView.as_view(), name="public-enquiries"),
    path(
        "newsletter/subscribe/",
        NewsletterSubscribeView.as_view(),
        name="public-newsletter-subscribe",
    ),
    path(
        "newsletter/confirm/",
        NewsletterConfirmView.as_view(),
        name="public-newsletter-confirm",
    ),
    path(
        "newsletter/unsubscribe/",
        NewsletterUnsubscribeView.as_view(),
        name="public-newsletter-unsubscribe",
    ),
]
