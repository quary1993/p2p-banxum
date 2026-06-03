from __future__ import annotations

from django.urls import path

from backend.apps.secondary_market.api.views import (
    SecondaryMarketListingApproveView,
    SecondaryMarketListingListCreateView,
    SecondaryMarketListingPurchaseView,
    SecondaryMarketListingRejectView,
    SecondaryMarketListingRemoveView,
)

urlpatterns = [
    path(
        "listings/",
        SecondaryMarketListingListCreateView.as_view(),
        name="secondary-market-listings",
    ),
    path(
        "admin/listings/<uuid:listing_id>/approve/",
        SecondaryMarketListingApproveView.as_view(),
        name="secondary-market-listing-approve",
    ),
    path(
        "listings/<uuid:listing_id>/purchase/",
        SecondaryMarketListingPurchaseView.as_view(),
        name="secondary-market-listing-purchase",
    ),
    path(
        "admin/listings/<uuid:listing_id>/reject/",
        SecondaryMarketListingRejectView.as_view(),
        name="secondary-market-listing-reject",
    ),
    path(
        "admin/listings/<uuid:listing_id>/remove/",
        SecondaryMarketListingRemoveView.as_view(),
        name="secondary-market-listing-remove",
    ),
]
