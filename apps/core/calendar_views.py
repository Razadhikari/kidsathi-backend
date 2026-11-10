from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import api_view
from rest_framework.response import Response

from apps.core.nepali_date import BS_MONTHS_EN, BS_MONTHS_NE, to_bs, today_bs


@extend_schema(responses={200: None})
@api_view(["GET"])
def calendar_today(request):
    """Today in Nepal, in AD and BS – so the apps don't need their own Nepali calendar."""
    ad = timezone.localdate()
    year, month = today_bs()
    return Response(
        {
            "ad": ad.isoformat(),
            "bs": to_bs(ad),
            "bs_year": year,
            "bs_month": month,
            "bs_month_name": BS_MONTHS_EN[month - 1],
            "bs_month_name_ne": BS_MONTHS_NE[month - 1],
        }
    )
