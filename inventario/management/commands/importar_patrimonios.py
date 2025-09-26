import json
from pathlib import Path
from datetime import datetime
from django.core.management.base import BaseCommand
from inventario.models import Patrimonio


class Command(BaseCommand):
    help = "Importa patrimônios a partir de um arquivo resultado.json"

    def add_arguments(self, parser):
        parser.add_argument(
            "--arquivo",
            type=str,
            help="Caminho para o resultado.json. Ex: out/2025-09-26/resultado.json",
            required=True,
        )

    def handle(self, *args, **options):
        arquivo = Path(options["arquivo"])

        if not arquivo.exists():
            self.stderr.write(self.style.ERROR(f"Arquivo não encontrado: {arquivo}"))
            return

        try:
            dados = json.loads(arquivo.read_text(encoding="utf-8"))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Erro ao ler JSON: {e}"))
            return

        resultados = dados.get("resultados") or dados.get("results") or []
        if not resultados:
            self.stdout.write(self.style.WARNING("Nenhum item encontrado no JSON."))
            return

        novos, atualizados = 0, 0

        for item in resultados:
            # Ajuste conforme a saída real do seu JSON
            cod = item.get("cod_patrimonio") or item.get("codigo") or None
            data_raw = item.get("data")
            checklist = item.get("checklist") or ""
            localizacao = item.get("localizacao") or ""
            filial = item.get("filial") or ""

            if not cod:
                continue

            # Normalizar data (aceita 'YYYY-MM-DD' ou 'DD/MM/YYYY')
            data = None
            if data_raw:
                try:
                    if "-" in data_raw:
                        data = datetime.strptime(data_raw, "%Y-%m-%d").date()
                    elif "/" in data_raw:
                        data = datetime.strptime(data_raw, "%d/%m/%Y").date()
                except Exception:
                    self.stderr.write(
                        self.style.WARNING(f"Data inválida para {cod}: {data_raw}")
                    )

            obj, created = Patrimonio.objects.update_or_create(
                cod_patrimonio=str(cod),
                defaults={
                    "data": data,
                    "checklist": checklist,
                    "localizacao": localizacao,
                    "filial": filial,
                },
            )
            if created:
                novos += 1
            else:
                atualizados += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Importação concluída. Novos: {novos}, Atualizados: {atualizados}"
            )
        )
