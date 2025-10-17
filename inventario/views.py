from django.db.models import Count, Q, Case, When, IntegerField
from django.db.models.functions import TruncDay, TruncWeek
from rest_framework.decorators import api_view
from rest_framework.response import Response
from datetime import date, timedelta
from .models import Patrimonio
from rest_framework import viewsets
from .models import Patrimonio            # ⬅️ se seu modelo tiver outro nome, troque aqui
from .serializers import PatrimonioSerializer


class PatrimonioViewSet(viewsets.ModelViewSet):
    queryset = Patrimonio.objects.all().order_by("-id")
    serializer_class = PatrimonioSerializer

def not_pend_q():                                       
    return ~Q(cod_patrimonio__iregex=r'^PEND')

@api_view(["GET"])
def metrics_overview(request):
    """
    Resumo para cards: hoje, semana.
    """
    from django.utils.timezone import now
    today = now().date()
    start_week = today - timedelta(days=today.weekday())  # segunda
    prev_week_start = start_week - timedelta(days=7)
    prev_week_end   = start_week - timedelta(days=1)

    qs = Patrimonio.objects.all()

    # HOJE
    hoje_qs = qs.filter(processado_em__date=today)
    hoje_total = hoje_qs.count()
    hoje_lidos = hoje_qs.filter(not_pend_q()).count()
    hoje_pct   = round(100 * (hoje_lidos / hoje_total), 1) if hoje_total else 0

    # SEMANA ATUAL
    sem_qs = qs.filter(processado_em__date__gte=start_week)
    sem_total = sem_qs.count()
    sem_lidos = sem_qs.filter(not_pend_q()).count()
    sem_pct   = round(100 * (sem_lidos / sem_total), 1) if sem_total else 0

    # SEMANA ANTERIOR (para variação)
    prev_qs = qs.filter(processado_em__date__gte=prev_week_start,
                        processado_em__date__lte=prev_week_end)
    prev_total = prev_qs.count()

    def delta_pct(curr, prev):
        if not prev: return 0
        return round(100 * (curr - prev) / prev)

    return Response({
        "today":   {"total": hoje_total, "ok": hoje_lidos, "pct": hoje_pct, "delta_vs_yesterday": delta_pct(hoje_total, qs.filter(processado_em__date=today - timedelta(days=1))).__int__()},
        "week":    {"total": sem_total,  "ok": sem_lidos,  "pct": sem_pct,  "delta_vs_prevweek": delta_pct(sem_total, prev_total)},
    })

@api_view(["GET"])
def metrics_timeseries(request):
    """
    Série temporal para o gráfico (por dia).
    Query params opcionais: ?from=YYYY-MM-DD&to=YYYY-MM-DD
    """
    from django.utils.dateparse import parse_date
    from_param = parse_date(request.GET.get("from") or "")
    to_param   = parse_date(request.GET.get("to") or "")

    qs = Patrimonio.objects.all()
    if from_param:
        qs = qs.filter(processado_em__date__gte=from_param)
    if to_param:
        qs = qs.filter(processado_em__date__lte=to_param)

    agg = (
        qs.annotate(day=TruncDay("processado_em"))
          .values("day")
          .annotate(
              total=Count("id"),
              ok=Count("id", filter=not_pend_q()),
              pend=Count("id", filter=Q(cod_patrimonio__iregex=r'^PEND')),
          )
          .order_by("day")
    )

    # monta arrays para MUI X Charts
    labels = []
    total  = []
    lidos  = []
    pend   = []
    pct_ok = []
    for row in agg:
        labels.append(row["day"].date().isoformat())
        total.append(row["total"])
        lidos.append(row["ok"])
        pend.append(row["pend"])
        pct_ok.append( round(100*row["ok"]/row["total"]) if row["total"] else 0 )

    return Response({
        "labels": labels,
        "series": {
            "total": total,
            "lidos": lidos,
            "pend": pend,
            "pct_ok": pct_ok
        }
    })
