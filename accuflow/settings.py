from pathlib import Path
import environ
import os
from datetime import timedelta

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env() 
env.read_env()

SECRET_KEY = env('SECRETKEY')
DEBUG = env('DEBUG')

ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'core',
    'super_admin',
    'expenses',
    'nsd_entry',
    'purchase_entry',
    'suppliers',
    'collector',
    'cash_entry',
    'cashbank',
    'sale_entry',
    'commission_entry',
    'general_ledger',
    'collector_view',
    'view_collections',
    'utilities',
    'trial_balance',
    'profit_loss',
    'balance_sheet',
    'axes',
    'whatsapp',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'core.login_required_middleware.LoginRequiredMiddleware',
    'core.middleware.SubscriptionMiddleware',
    'core.middleware.SingleSessionMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'axes.middleware.AxesMiddleware',
]

ROOT_URLCONF = 'accuflow.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'core.context_processors.notifications',
                'whatsapp.context_processors.whatsapp_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'accuflow.wsgi.application'


AUTH_USER_MODEL = 'core.UserAccount'

AUTHENTICATION_BACKENDS = [
    'axes.backends.AxesStandaloneBackend',
    'django.contrib.auth.backends.ModelBackend',
]

AXES_LOCKOUT_TEMPLATE = 'lockout.html'
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = timedelta(minutes=15)
AXES_LOCKOUT_PARAMETERS = ["username", "ip_address"]
AXES_RESET_ON_SUCCESS = True


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': env('DATABASE_NAME'),
        'USER': env('DATABASE_USER'),
        'PASSWORD': env('DATABASE_PASS'),
        'HOST': env('DATABASE_HOST'),
        'PORT': env('DATABASE_PORT'),
        'OPTIONS': {
            'charset': 'utf8',
            'init_command': "SET NAMES 'utf8', innodb_strict_mode=OFF, sql_mode=''",
        },
    }
}



AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]



LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'Asia/Kolkata'

USE_I18N = True

USE_TZ = True




STATIC_URL = '/static/'
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static')
]
STATIC_ROOT = os.path.join(BASE_DIR, 'assets')


MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR,'media')



DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# --- WhatsApp Integration Settings ---
WHATSAPP_ENABLED = env('WHATSAPP_ENABLED', default='True') == 'True'
# WHATSAPP_NODE_URL = env('WHATSAPP_NODE_URL', default='http://localhost:3001')
WHATSAPP_NODE_URL = env('WHATSAPP_NODE_URL', default='http://localhost:3005')
WHATSAPP_API_KEY = env('WHATSAPP_API_KEY', default='accuflow-wa-dev-key-2024')
WHATSAPP_TIMEOUT = int(env('WHATSAPP_TIMEOUT', default='30'))
ADMIN_ACTION_PASSWORD = env('ADMIN_ACTION_PASSWORD', default='accuflow@2024')


# Logging for WhatsApp
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{asctime}] {levelname} {name}: {message}',
            'style': '{',
        },
    },
    'handlers': {
        'whatsapp_file': {
            'level': 'DEBUG' if DEBUG == 'True' else 'INFO',
            'class': 'logging.FileHandler',
            'filename': os.path.join(BASE_DIR, 'whatsapp.log'),
            'formatter': 'verbose',
        },
        'console': {
            'level': 'DEBUG' if DEBUG == 'True' else 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'whatsapp': {
            'handlers': ['whatsapp_file', 'console'],
            'level': 'DEBUG' if DEBUG == 'True' else 'INFO',
            'propagate': False,
        },
    },
}
