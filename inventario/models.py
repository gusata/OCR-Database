# inventario/models.py
from django.db import models

class Patrimonio(models.Model):
    cod_patrimonio = models.CharField(max_length=100, unique=True)

    # já existentes
    data = models.DateField(null=True, blank=True)
    checklist = models.CharField(max_length=255, blank=True)
    localizacao = models.CharField(max_length=255, blank=True)
    filial = models.CharField(max_length=255, blank=True)

    # novos campos
    dropbox_link = models.URLField(blank=True)
    ocr_raw = models.TextField(blank=True)

    # extras (se quiser rastrear)
    arquivo = models.CharField(max_length=255, blank=True)
    dropbox_path = models.CharField(max_length=500, blank=True)
    content_hash = models.CharField(max_length=128, blank=True)
    client_modified = models.DateTimeField(null=True, blank=True)
    processado_em = models.DateTimeField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.cod_patrimonio
