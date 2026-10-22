from django.apps import AppConfig


class ProcessConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.process'
    label = 'process'
    verbose_name = '工艺配置'
