from rest_framework import viewsets, filters
from .models import Patrimonio
from .serializers import PatrimonioSerializer

class PatrimonioViewSet(viewsets.ModelViewSet):
    queryset = Patrimonio.objects.all().order_by('-atualizado_em')
    serializer_class = PatrimonioSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['codigo', 'localizacao', 'checklist']
    ordering_fields = ['atualizado_em', 'codigo', 'valor']
