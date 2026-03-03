from django.urls import path
from . import views

app_name = 'whatsapp'

urlpatterns = [
    # Page views
    path('scan/', views.WhatsAppScanView.as_view(), name='whatsapp_scan'),
    path('balance-accounts/', views.BalanceAccountsView.as_view(), name='balance_accounts'),

    # AJAX API endpoints (proxies to Node.js server)
    path('api/qr/', views.whatsapp_proxy_qr, name='whatsapp_qr'),
    path('api/status/', views.whatsapp_status_api, name='whatsapp_status'),
    path('api/unlink/', views.whatsapp_unlink_api, name='whatsapp_unlink'),
    path('api/send-balance/', views.send_balance_api, name='send_balance'),
    path('api/send-address-rows/', views.send_address_rows_api, name='send_address_rows'),
    path('api/job-status/<str:job_id>/', views.job_status_api, name='job_status'),
    path('api/cancel-job/<str:job_id>/', views.cancel_job_api, name='cancel_job'),
    path('api/cancel-all-jobs/', views.cancel_all_jobs_api, name='cancel_all_jobs'),
]
