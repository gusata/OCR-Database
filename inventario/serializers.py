from rest_framework import serializers
from .models import Patrimonio

class PatrimonioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Patrimonio
        fields = "__all__"
