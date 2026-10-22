"""Django 配置。所有可变项从 .env 读取，代码里不写死密码。

说明：本项目刻意保持单一 settings 文件，不为开发/生产拆包。
原因：四人团队都是新手，两个文件比三个文件好排查。
需要区分的项都用 .env 控制（DEBUG、DB_ENGINE 等）。
"""
import os
from pathlib import Path

from dotenv import load_dotenv

# BASE_DIR = .../SmartWorks/backend
BASE_DIR = Path(__file__).resolve().parent.parent
# PROJECT_ROOT = .../SmartWorks
PROJECT_ROOT = BASE_DIR.parent

# .env 放在项目根目录（SmartWorks/.env），不是 backend/ 下。
# 这里依次尝试项目根目录和 backend 目录，两个位置都支持，避免放错位置读不到。
#
# 踩坑记录：最初只找 BASE_DIR / '.env'（也就是 backend/.env），而安装脚本把 .env
# 生成在项目根目录，结果 dotenv 什么都没加载，DB_ENGINE 用了默认值 postgres，
# 于是 Django 去连 PostgreSQL，报 "Error loading psycopg2 or psycopg module"。
_ENV_CANDIDATES = (PROJECT_ROOT / '.env', BASE_DIR / '.env')
for _candidate in _ENV_CANDIDATES:
    if _candidate.exists():
        load_dotenv(_candidate)
        break


def env(key, default=''):
    return os.getenv(key, default)


def env_bool(key, default=False):
    return env(key, '1' if default else '0') in ('1', 'true', 'True', 'yes')


# ---------------------------------------------------------------- 基础
SECRET_KEY = env('DJANGO_SECRET_KEY', 'dev-only-insecure-key-please-change')
DEBUG = env_bool('DJANGO_DEBUG', True)
ALLOWED_HOSTS = [h.strip() for h in env('DJANGO_ALLOWED_HOSTS', '*').split(',') if h.strip()]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # 第三方
    'rest_framework',
    'rest_framework.authtoken',
    'corsheaders',
    'django_filters',
    'drf_spectacular',
    'simple_history',
    'import_export',
    # 自研应用
    'apps.core',
    'apps.masterdata',
    'apps.process',
    'apps.order',
    'apps.planning',
    'apps.inventory',
    'apps.production',
    'apps.quality',
    'apps.equipment',
    'apps.logistics',
    'apps.analytics',
    'apps.integration',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'simple_history.middleware.HistoryRequestMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

# ---------------------------------------------------------------- 数据库
# 默认给 sqlite：这样即使 .env 缺失或写错，项目也能直接跑起来（第一代用 SQLite）。
# 要切 PostgreSQL：在 .env 里显式写 DB_ENGINE=postgres，并额外安装 psycopg[binary]。
if env('DB_ENGINE', 'sqlite') == 'sqlite':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': env('DB_NAME', 'smartworks'),
            'USER': env('DB_USER', 'postgres'),
            'PASSWORD': env('DB_PASSWORD', 'postgres'),
            'HOST': env('DB_HOST', '127.0.0.1'),
            'PORT': env('DB_PORT', '5432'),
            'CONN_MAX_AGE': 60,
        }
    }

# ---------------------------------------------------------------- 认证
AUTH_USER_MODEL = 'core.User'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ---------------------------------------------------------------- 国际化
LANGUAGE_CODE = 'zh-hans'
TIME_ZONE = 'Asia/Shanghai'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ---------------------------------------------------------------- 跨域（仅开发）
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True

# ---------------------------------------------------------------- DRF
REST_FRAMEWORK = {
    # 只保留 JSON 渲染器：统一响应体由 apps.core.renderers 负责
    'DEFAULT_RENDERER_CLASSES': [
        'apps.core.renderers.UnifiedJSONRenderer',
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'apps.core.pagination.StandardPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'EXCEPTION_HANDLER': 'apps.core.exceptions.unified_exception_handler',
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DATETIME_FORMAT': '%Y-%m-%dT%H:%M:%S',
    'DATE_FORMAT': '%Y-%m-%d',
}

# ---------------------------------------------------------------- Swagger
SPECTACULAR_SETTINGS = {
    'TITLE': 'SmartWorks 智能车间管理平台 API',
    'DESCRIPTION': '统一响应体：{"code":0,"message":"ok","data":...}',
    'VERSION': '0.1.0',
    'SERVE_INCLUDE_SCHEMA': False,
    # 文档接口免鉴权，否则未登录时 Swagger 页拿不到 schema
    'SERVE_PERMISSIONS': ['rest_framework.permissions.AllowAny'],
    'SERVE_AUTHENTICATION': [],
    'COMPONENT_SPLIT_REQUEST': True,
}

# ---------------------------------------------------------------- 日志
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'simple': {'format': '[{levelname}] {asctime} {name} {message}', 'style': '{'},
    },
    'handlers': {
        'console': {'class': 'logging.StreamHandler', 'formatter': 'simple'},
    },
    'root': {'handlers': ['console'], 'level': 'INFO'},
    'loggers': {
        'django.db.backends': {'level': 'WARNING'},
        'apps': {'handlers': ['console'], 'level': 'DEBUG', 'propagate': False},
    },
}
