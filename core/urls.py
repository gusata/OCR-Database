from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from inventario.views import PatrimonioViewSet

router = DefaultRouter()
router.register(r'patrimonios', PatrimonioViewSet, basename='patrimonio')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include(router.urls)),
]
