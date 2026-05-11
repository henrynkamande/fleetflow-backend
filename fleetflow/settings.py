import os
from pathlib import Path
from datetime import timedelta

BASE_DIR = Path(__file__).resolve().parent.parent

# Logs directory
LOGS_DIR = BASE_DIR / 'logs'
LOGS_DIR.mkdir(exist_ok=True)

SECRET_KEY = os.environ.get(
    'SECRET_KEY',
    'django-insecure-c2pi1o+*c^z021tsl5(4i5prby(hun)v$8gmt6rrw*+-&#7ps8'
)

DEBUG = os.environ.get('DEBUG', 'True').lower() in ('true', '1', 'yes')

ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1', 'fleetflow-backend-zr0z.onrender.com').split(',')

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party apps
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',

    # Local apps
    'oauth',
    'vehicles',
    'trips'
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
]

ROOT_URLCONF = 'fleetflow.urls'

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

WSGI_APPLICATION = 'fleetflow.wsgi.application'


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# For production, use PostgreSQL:
# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.postgresql',
#         'NAME': os.environ.get('DB_NAME', 'fleetflow'),
#         'USER': os.environ.get('DB_USER', 'fleetflow_user'),
#         'PASSWORD': os.environ.get('DB_PASSWORD', ''),
#         'HOST': os.environ.get('DB_HOST', 'localhost'),
#         'PORT': os.environ.get('DB_PORT', '5432'),
#     }
# }


# ============================================================================
# CUSTOM USER MODEL
# ============================================================================

AUTH_USER_MODEL = 'oauth.User'


# ============================================================================
# PASSWORD VALIDATION
# ============================================================================

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 8,
        }
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# ============================================================================
# AUTHENTICATION BACKENDS
# ============================================================================

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',  # Default
]

# Custom authentication backend for email login
# AUTHENTICATION_BACKENDS = [
#     'oauth.backends.EmailBackend',  # Custom email auth backend
# ]


# ============================================================================
# DJANGO REST FRAMEWORK SETTINGS
# ============================================================================

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.JSONRenderer',
    ),
    'DEFAULT_PARSER_CLASSES': (
        'rest_framework.parsers.JSONParser',
        'rest_framework.parsers.MultiPartParser',
        'rest_framework.parsers.FormParser',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',
        'user': '1000/hour',
        'login': '5/minute',
        'otp': '3/minute',
    },
    'DEFAULT_VERSIONING_CLASS': 'rest_framework.versioning.AcceptHeaderVersioning',
    'DEFAULT_VERSION': '1.0',
    'ALLOWED_VERSIONS': ['1.0'],
    'VERSION_PARAM': 'version',
    'EXCEPTION_HANDLER': 'rest_framework.views.exception_handler',
}

# For development, enable browsable API
if DEBUG:
    REST_FRAMEWORK['DEFAULT_RENDERER_CLASSES'] = (
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    )


# ============================================================================
# SIMPLE JWT SETTINGS
# ============================================================================

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,

    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'VERIFYING_KEY': None,
    'AUDIENCE': None,
    'ISSUER': 'fleet_flow',

    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',

    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'TOKEN_TYPE_CLAIM': 'token_type',

    'JTI_CLAIM': 'jti',

    'SLIDING_TOKEN_REFRESH_EXP_CLAIM': 'refresh_exp',
    'SLIDING_TOKEN_LIFETIME': timedelta(hours=1),
    'SLIDING_TOKEN_REFRESH_LIFETIME': timedelta(days=7),
}


# ============================================================================
# CORS SETTINGS
# ============================================================================

# For development
if DEBUG:
    CORS_ALLOW_ALL_ORIGINS = True
else:
    CORS_ALLOWED_ORIGINS = os.environ.get(
        'CORS_ALLOWED_ORIGINS',
        'http://localhost:3000,http://localhost:5173',
        'https://fleetflow-frontend-72w2.vercel.app/'
    ).split(',')

CORS_ALLOW_CREDENTIALS = True

CORS_ALLOW_METHODS = [
    'DELETE',
    'GET',
    'OPTIONS',
    'PATCH',
    'POST',
    'PUT',
]

CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]


# ============================================================================
# INTERNATIONALIZATION
# ============================================================================

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True


# ============================================================================
# STATIC & MEDIA FILES
# ============================================================================

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

# Media files (User uploads: avatars, KYC documents, company logos)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Create media subdirectories
MEDIA_DIRS = [
    MEDIA_ROOT / 'avatars',
    MEDIA_ROOT / 'kyc_documents',
    MEDIA_ROOT / 'company_logos',
]

for media_dir in MEDIA_DIRS:
    media_dir.mkdir(parents=True, exist_ok=True)

# File upload settings
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10 MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10 MB
FILE_UPLOAD_PERMISSIONS = 0o644
FILE_UPLOAD_DIRECTORY_PERMISSIONS = 0o755


# ============================================================================
# EMAIL SETTINGS
# ============================================================================

if DEBUG:
    # In development, print emails to console
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
else:
    # In production, use SMTP
    EMAIL_BACKEND = os.environ.get(
        'EMAIL_BACKEND',
        'django.core.mail.backends.smtp.EmailBackend'
    )

# SMTP Configuration (Update for production)
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True').lower() in ('true', '1', 'yes')
EMAIL_USE_SSL = os.environ.get('EMAIL_USE_SSL', 'False').lower() in ('true', '1', 'yes')
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
EMAIL_TIMEOUT = int(os.environ.get('EMAIL_TIMEOUT', 30))

DEFAULT_FROM_EMAIL = os.environ.get(
    'DEFAULT_FROM_EMAIL',
    'noreply@fleetflow.com'
)
SERVER_EMAIL = os.environ.get(
    'SERVER_EMAIL',
    'server@fleetflow.com'
)
EMAIL_SUBJECT_PREFIX = '[Fleet Flow] '

# Email templates (optional - for HTML emails)
EMAIL_USE_HTML = os.environ.get('EMAIL_USE_HTML', 'False').lower() in ('true', '1', 'yes')

# Admin emails for error notifications
ADMINS = [
    ('Admin', os.environ.get('ADMIN_EMAIL', 'admin@fleetflow.com')),
]
MANAGERS = ADMINS


# ============================================================================
# SECURITY SETTINGS
# ============================================================================

# HTTPS settings (enable in production)
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    X_FRAME_OPTIONS = 'DENY'

# Session settings
SESSION_COOKIE_AGE = 1209600  # 2 weeks
SESSION_COOKIE_HTTPONLY = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

# CSRF settings
CSRF_COOKIE_HTTPONLY = True
CSRF_TRUSTED_ORIGINS = os.environ.get(
    'CSRF_TRUSTED_ORIGINS',
    'http://localhost:3000,http://localhost:5173'
).split(',')


# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{levelname}] {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '[{levelname}] {asctime} {message}',
            'style': '{',
        },
    },
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse',
        },
        'require_debug_true': {
            '()': 'django.utils.log.RequireDebugTrue',
        },
    },
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
            'filters': ['require_debug_true'],
        },
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': str(LOGS_DIR / 'django.log'),
            'maxBytes': 1024 * 1024 * 10,  # 10 MB
            'backupCount': 10,
            'formatter': 'verbose',
        },
        'error_file': {
            'level': 'ERROR',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': str(LOGS_DIR / 'error.log'),
            'maxBytes': 1024 * 1024 * 10,  # 10 MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
        'mail_admins': {
            'level': 'ERROR',
            'class': 'django.utils.log.AdminEmailHandler',
            'filters': ['require_debug_false'],
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': True,
        },
        'django.request': {
            'handlers': ['error_file', 'mail_admins'],
            'level': 'ERROR',
            'propagate': False,
        },
        'django.security': {
            'handlers': ['error_file', 'mail_admins'],
            'level': 'ERROR',
            'propagate': False,
        },
        'django.db.backends': {
            'handlers': ['console'],
            'level': 'WARNING',  
            'propagate': False,
        },
        'oauth': {  # Your app's logger
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': True,
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
}


# ============================================================================
# DEFAULT PRIMARY KEY FIELD TYPE
# ============================================================================

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# ============================================================================
# APPLICATION-SPECIFIC SETTINGS
# ============================================================================

# Fleet Flow Settings
FLEET_FLOW = {
    # OTP Settings
    'OTP_LENGTH': 6,
    'OTP_VALIDITY_MINUTES': 5,
    'OTP_MAX_ATTEMPTS': 3,
    
    # Driver Settings
    'MAX_DAILY_HOURS': 12.0,
    'MAX_WEEKLY_HOURS': 60.0,
    'MAX_TRIP_DURATION_HOURS': 16,
    
    # File Upload Limits
    'AVATAR_MAX_SIZE_MB': 5,
    'KYC_DOCUMENT_MAX_SIZE_MB': 10,
    'COMPANY_LOGO_MAX_SIZE_MB': 5,
    
    # Allowed File Types
    'AVATAR_ALLOWED_TYPES': ['image/jpeg', 'image/png', 'image/webp'],
    'KYC_ALLOWED_TYPES': ['image/jpeg', 'image/png', 'application/pdf'],
    'LOGO_ALLOWED_TYPES': ['image/jpeg', 'image/png', 'image/svg+xml', 'image/webp'],
    
    # Subscription Plans
    'FREE_PLAN_MAX_DRIVERS': 5,
    'FREE_PLAN_MAX_VEHICLES': 3,
}

# Frontend URL (for email links and redirects)
FRONTEND_URL = os.environ.get('FRONTEND_URL', 'http://localhost:3000')
FRONTEND_VERIFY_EMAIL_URL = f'{FRONTEND_URL}/verify-email'
FRONTEND_RESET_PASSWORD_URL = f'{FRONTEND_URL}/reset-password'
FRONTEND_LOGIN_URL = f'{FRONTEND_URL}/login'
