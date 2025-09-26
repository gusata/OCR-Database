from django.db import models

class Patrimonio(models.Model):
    cod_patrimonio = models.CharField("Código do Patrimônio", max_length=64, unique=True)
    data = models.DateField("Data")
    checklist = models.TextField("Checklist", blank=True)
    localizacao = models.CharField("Localização", max_length=128, blank=True)
    filial = models.CharField("Filial", max_length=128, blank=True)

    atualizado_em = models.DateTimeField(auto_now=True)  # só para saber quando foi atualizado

    def __str__(self):
        return f"{self.cod_patrimonio} - {self.localizacao} ({self.filial})"
