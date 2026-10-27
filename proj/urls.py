from django.contrib import admin
from django.urls import path

from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from proj.swagger import schema_view


class Redirect(RedirectView):
    pattern_name = 'schema-swagger-ui'

urlpatterns = [
    path('admin/', admin.site.urls),
    path('library/', include('app.urls')),
    path('users/', include('users.urls')),
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui')
]
