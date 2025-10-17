from django.db import models

class Patrimonio(models.Model):
    cod_patrimonio = models.CharField(max_length=100, unique=False, null=True, blank=True)

    # já existentes
    data = models.DateField(null=True, blank=True)
    checklist = models.CharField(max_length=255, blank=True, unique=True)
    localizacao = models.CharField(max_length=255, blank=True)
    filial = models.CharField(max_length=255, blank=True)

    # novos campos
    dropbox_link = models.URLField(blank=True)
    ocr_raw = models.TextField(blank=True)

    # coordenadas
    coords_lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    coords_lon = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    coords_raw = models.CharField(max_length=100, blank=True)  # ex.: "-23.55,-46.63"

    # extras
    arquivo = models.CharField(max_length=255, blank=True)
    dropbox_path = models.CharField(max_length=500, blank=True)
    content_hash = models.CharField(max_length=128, blank=True)
    client_modified = models.DateTimeField(null=True, blank=True)
    processado_em = models.DateTimeField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.cod_patrimonio or "<sem patrimônio>"
