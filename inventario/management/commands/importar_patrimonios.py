# inventario/management/commands/importar_patrimonios.py
import json
from pathlib import Path
from typing import Any, Dict, Iterable, Tuple
from decimal import Decimal, InvalidOperation
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction
from inventario.models import Patrimonio

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


class Command(BaseCommand):
    help = "Importa patrimônios a partir de um arquivo JSON. Suporta upsert por 'checklist'."

    def add_arguments(self, parser):
        parser.add_argument(
            "--arquivo",
            required=True,
            help="Caminho do JSON (ex.: out\\2025-10-02\\resultado_db.json)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Não grava no banco; apenas simula e imprime o que faria.",
        )
        parser.add_argument(
            "--quiet",
            action="store_true",
            help="Menos saída no console.",
        )
        parser.add_argument(
            "--on-duplicate",
            choices=["update", "skip"],
            default="update",
            help="Se já existir mesmo checklist: update (padrão) ou skip.",
        )

    # ----------------- Utils -----------------

    def _iter_registros(self, payload: Any) -> Iterable[Dict[str, Any]]:
        if isinstance(payload, list):
            yield from payload
        elif isinstance(payload, dict) and isinstance(payload.get("records"), list):
            yield from payload["records"]
        else:
            raise CommandError(
                "Formato do JSON não reconhecido. Use uma lista de objetos ou {'records': [...]}."
            )

    def _allowed_defaults(self) -> set:
        allowed = set()
        for f in Patrimonio._meta.get_fields():
            if getattr(f, "concrete", False) and not getattr(f, "many_to_many", False):
                if f.name not in {"id"}:
                    allowed.add(f.name)
        return allowed

    def _to_decimal(self, v: Any) -> Decimal | None:
        if v in (None, "", "null"):
            return None
        s = str(v).strip().replace(",", ".")
        try:
            return Decimal(s)
        except (InvalidOperation, ValueError):
            return None

    def _to_datetime(self, v: Any) -> datetime | None:
        if not v:
            return None
        if isinstance(v, datetime):
            return v
        s = str(v).strip()
        # tenta ISO 8601; aceita ‘Z’
        s = s.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(s)
        except ValueError:
            return None

    def _normalize_value(self, k: str, v: Any) -> Any:
        # strings vazias → None
        if isinstance(v, str) and v.strip() == "":
            return None

        # normalização de coordenadas
        if k in {"coords_lat", "lat"}:
            return self._to_decimal(v)
        if k in {"coords_lon", "lon"}:
            return self._to_decimal(v)

        # normalização de datetimes
        if k in {"client_modified", "processado_em", "criado_em", "atualizado_em", "data"}:
            # data é DateField no model — se vier "YYYY-MM-DD" ok; se vier datetime, mantém
            if k == "data":
                # aceita "YYYY-MM-DD"; não converte se já estiver nesse formato
                try:
                    if isinstance(v, str) and len(v) == 10:
                        # formato YYYY-MM-DD
                        datetime.strptime(v, "%Y-%m-%d")  # valida
                        return v
                except Exception:
                    pass
                dt = self._to_datetime(v)
                return dt.date().isoformat() if dt else None
            else:
                return self._to_datetime(v)

        return v

    def _coerce_aliases(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Suporta JSONs antigos:
          - 'cords' -> 'coords_raw'
          - 'lat'/'lon' flutuando -> 'coords_lat'/'coords_lon'
        """
        data = dict(item)

        if "coords_raw" not in data and "cords" in data:
            data["coords_raw"] = data.get("cords")

        if "coords_lat" not in data and "lat" in data:
            data["coords_lat"] = data.get("lat")
        if "coords_lon" not in data and "lon" in data:
            data["coords_lon"] = data.get("lon")

        return data

    def _split_fields(self, data: Dict[str, Any], allowed: set) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Separa (key_fields) e (defaults):
        - key: checklist (quando existir)
        - defaults: demais campos permitidos
        """
        data = {k: self._normalize_value(k, v) for k, v in data.items() if k in allowed}

        key: Dict[str, Any] = {}
        if "checklist" in data and data["checklist"]:
            key["checklist"] = data.pop("checklist")

        return key, data

    # ----------------- Handle -----------------

    def handle(self, *args, **options):
        path = Path(options["arquivo"])
        if not path.exists():
            raise CommandError(f"Arquivo não encontrado: {path}")

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise CommandError(f"JSON inválido em {path}: {e}")

        dry = options["dry_run"]
        quiet = options["quiet"]
        on_dup = options["on_duplicate"]

        allowed = self._allowed_defaults()

        total = criados = atualizados = pulados = erros = 0

        for raw_item in self._iter_registros(payload):
            total += 1

            # Aliases e normalização
            item = self._coerce_aliases(raw_item)
            data = {k: self._normalize_value(k, item.get(k)) for k in allowed if k in item}

            key, defaults = self._split_fields(data, allowed)

            if not key:
                # sem checklist (chave), cria “solto”
                if dry:
                    if not quiet:
                        self.stdout.write(f"[DRY] CREATE (sem checklist): {defaults}")
                    continue
                try:
                    obj = Patrimonio.objects.create(**defaults)
                    criados += 1
                    if not quiet:
                        self.stdout.write(self.style.SUCCESS(f"[OK] CRIADO id={obj.pk} (sem checklist)"))
                except IntegrityError as e:
                    erros += 1
                    self.stdout.write(self.style.ERROR(f"[ERRO] INTEGRITY: {e} -> {defaults}"))
                except Exception as e:
                    erros += 1
                    self.stdout.write(self.style.ERROR(f"[ERRO] {type(e).__name__}: {e} -> {defaults}"))
                continue

            # com checklist (chave natural)
            if dry:
                if not quiet:
                    self.stdout.write(f"[DRY] UPSERT {key} defaults={defaults} (on-duplicate={on_dup})")
                continue

            try:
                with transaction.atomic():
                    if on_dup == "update":
                        obj, created = Patrimonio.objects.update_or_create(
                            **key, defaults=defaults
                        )
                        if created:
                            criados += 1
                            if not quiet:
                                self.stdout.write(self.style.SUCCESS(f"[OK] CRIADO id={obj.pk} {key}"))
                        else:
                            atualizados += 1
                            if not quiet:
                                self.stdout.write(self.style.SUCCESS(f"[OK] ATUALIZADO id={obj.pk} {key}"))
                    else:  # skip
                        if Patrimonio.objects.filter(**key).exists():
                            pulados += 1
                            if not quiet:
                                self.stdout.write(self.style.WARNING(f"[SKIP] Já existe {key}"))
                        else:
                            obj = Patrimonio.objects.create(**(key | defaults))
                            criados += 1
                            if not quiet:
                                self.stdout.write(self.style.SUCCESS(f"[OK] CRIADO id={obj.pk} {key}"))

            except IntegrityError as e:
                erros += 1
                self.stdout.write(self.style.ERROR(f"[ERRO] INTEGRITY: {e} -> key={key} defaults={defaults}"))
            except Exception as e:
                erros += 1
                self.stdout.write(self.style.ERROR(f"[ERRO] {type(e).__name__}: {e} -> key={key} defaults={defaults}"))

        # Resumo
        self.stdout.write("")
        self.stdout.write(self.style.NOTICE("===== RESUMO DA IMPORTAÇÃO ====="))
        self.stdout.write(f"Arquivo:         {path}")
        self.stdout.write(f"Total lidos:     {total}")
        self.stdout.write(f"Criados:         {criados}")
        self.stdout.write(f"Atualizados:     {atualizados}")
        self.stdout.write(f"Pulados:         {pulados}")
        self.stdout.write(f"Erros:           {erros}")
        self.stdout.write(self.style.NOTICE("================================"))

        if erros:
            raise CommandError(f"Concluído com {erros} erro(s).")
