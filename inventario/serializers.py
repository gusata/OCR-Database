# inventario/serializers.py
from rest_framework import serializers
from .models import Patrimonio            # <-- ADICIONE

class PatrimonioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Patrimonio
        fields = "__all__"
