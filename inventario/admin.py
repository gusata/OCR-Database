from django.contrib import admin
from .models import Patrimonio

@admin.register(Patrimonio)
class PatrimonioAdmin(admin.ModelAdmin):
    list_display = ("cod_patrimonio", "data", "checklist", "localizacao", "filial", "atualizado_em")
    search_fields = ("cod_patrimonio", "localizacao", "filial")
    list_filter = ("filial", "localizacao", "data")
