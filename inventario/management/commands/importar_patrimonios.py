import json
from uuid import uuid4
from pathlib import Path
from datetime import datetime
from django.core.management.base import BaseCommand
from django.utils.timezone import make_aware, get_default_timezone
from inventario.models import Patrimonio
from django.db import transaction

class Command(BaseCommand):
    help = "Importa patrimônios a partir de um arquivo resultado*.json"

    def add_arguments(self, parser):
        parser.add_argument(
            "--arquivo",
            type=str,
            required=True,
            help="Caminho para o JSON (resultado.json ou resultado_db.json).",
        )

    def _parse_date(self, s: str):
        if not s:
            return None
        try:
            if "-" in s:
                return datetime.strptime(s, "%Y-%m-%d").date()
            if "/" in s:
                return datetime.strptime(s, "%d/%m/%Y").date()
        except Exception:
            return None

    def _parse_dt(self, s: str):
        """Converte string em datetime aware (com timezone)."""
        if not s:
            return None
        s = str(s).strip()

        # ISO com timezone (Z, +00:00, -03:00 etc.)
        try:
            if "Z" in s or "+" in s[10:] or "-" in s[10:]:
                return datetime.fromisoformat(s.replace("Z", "+00:00"))
        except Exception:
            pass

        # ISO sem timezone (2025-09-28T19:55:40 / 2025-09-28 19:55:40)
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
            try:
                dt = datetime.strptime(s, fmt)
                return make_aware(dt, get_default_timezone())
            except Exception:
                continue

        # Só data
        try:
            dt = datetime.strptime(s, "%Y-%m-%d")
            return make_aware(dt, get_default_timezone())
        except Exception:
            return None

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

        # aceita lista ou dict
        if isinstance(dados, list):
            resultados = dados
        elif isinstance(dados, dict):
            resultados = dados.get("resultados") or dados.get("records") or dados.get("results") or []
        else:
            self.stderr.write(self.style.ERROR("JSON em formato inesperado."))
            return

        if not resultados:
            self.stdout.write(self.style.WARNING("Nenhum item encontrado no JSON."))
            return

        novos, atualizados = 0, 0

        for item in resultados:
            # campos de identificação do arquivo
            content_hash = (item.get("content_hash") or "").strip()
            dropbox_path = (item.get("dropbox_path") or "").strip()
            arquivo_nome = (item.get("arquivo") or "").strip()

            # 1) patrimônio vindo do OCR (ou outros fallbacks)
            cod_ocr = (item.get("patrimonio") or "").strip()
            cod_compat = (item.get("cod_patrimonio") or item.get("codigo") or "").strip()
            cod_final = cod_ocr or cod_compat  # pode ficar vazio aqui

            # 2) dados restantes
            data = self._parse_date(item.get("data"))
            checklist = item.get("checklist") or ""
            localizacao = item.get("localizacao") or ""
            filial = item.get("filial") or ""
            dropbox_link = item.get("dropbox_link") or item.get("temporary_link") or ""
            ocr_raw = item.get("ocr_raw") or ""
            client_modified = self._parse_dt(item.get("client_modified"))
            processado_em = self._parse_dt(item.get("processado_em"))

            # 3) defina os "critérios" para achar o mesmo arquivo já salvo
            #    prioridade: content_hash > dropbox_path > arquivo
            lookup = {}
            if content_hash:
                lookup["content_hash"] = content_hash
            elif dropbox_path:
                lookup["dropbox_path"] = dropbox_path
            elif arquivo_nome:
                lookup["arquivo"] = arquivo_nome

            # 4) se não houver NADA para identificar o arquivo, ainda assim crie
            #    (gera um marcador único para não violar unique de cod_patrimonio)
            if not lookup:
                lookup = {"arquivo": arquivo_nome or f"sem-nome-{uuid4().hex[:8]}"}

            # 5) abre transação para evitar corrida
            with transaction.atomic():
                obj = None

                # tente achar por lookup
                qs = Patrimonio.objects.filter(**lookup)
                obj = qs.first()

                if obj:
                    # atualizar o existente
                    if cod_final:  # se agora temos patrimonio real, atualiza
                        obj.cod_patrimonio = str(cod_final)
                    elif not obj.cod_patrimonio or obj.cod_patrimonio.startswith("PEND-"):
                        # mantém/gera provisório se ainda não existe um definitivo
                        base = content_hash or dropbox_path or arquivo_nome or uuid4().hex
                        obj.cod_patrimonio = obj.cod_patrimonio or f"PEND-{base[:24]}"

                    obj.data = data
                    obj.checklist = checklist
                    obj.localizacao = localizacao
                    obj.filial = filial
                    obj.dropbox_link = dropbox_link
                    obj.ocr_raw = ocr_raw
                    obj.arquivo = arquivo_nome
                    obj.dropbox_path = dropbox_path
                    obj.content_hash = content_hash or obj.content_hash  # não perca o hash se já havia
                    obj.client_modified = client_modified
                    obj.processado_em = processado_em
                    obj.save()
                    atualizados += 1
                else:
                    # criar novo
                    if not cod_final:
                        # gerar um código provisório único (respeita unique=True)
                        base = content_hash or dropbox_path or arquivo_nome or uuid4().hex
                        cod_final = f"PEND-{base[:24]}"

                    Patrimonio.objects.create(
                        cod_patrimonio=str(cod_final),
                        data=data,
                        checklist=checklist,
                        localizacao=localizacao,
                        filial=filial,
                        dropbox_link=dropbox_link,
                        ocr_raw=ocr_raw,
                        arquivo=arquivo_nome,
                        dropbox_path=dropbox_path,
                        content_hash=content_hash,
                        client_modified=client_modified,
                        processado_em=processado_em,
                    )
                    novos += 1


        self.stdout.write(self.style.SUCCESS(
            f"Importação concluída. Novos: {novos}, Atualizados: {atualizados}"
        ))
