"""
URL configuration for accuflow project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls')).
"""
from django.contrib import admin
from django.urls import path,include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('django-admin/', admin.site.urls),
    path('', include('core.urls')),
    path('customers/', include('customers.urls')),
    path('admin/', include('super_admin.urls')),
    path('suppliers/', include('suppliers.urls')),
    path('expenses/', include('expenses.urls')),
    path('godown/', include('godown.urls')),
    path('cashbank/', include('cashbank.urls')),
    path('collectors/', include('collector.urls')),
    path('purchase/', include('purchase_entry.urls')),
    path('sale/', include('sale_entry.urls')),
    path('nsd/', include('nsd_entry.urls')),
    path('cash/', include('cash_entry.urls')),
    path('commission/', include('commission_entry.urls')),
    path('supplierledger/', include('supplier_ledger.urls')),
    path('customerledger/', include('customer_ledger.urls')),
    path('godownledger/', include('godown_ledger.urls')),
    path('stockview/', include('stock_view.urls')),
    path('stocktransfer/', include('stock_transfer.urls')),
    path('cashbankbalance/', include('cashbank_balance.urls')),
    path('general-ledger/', include('general_ledger.urls')),
    path('viewcollections/', include('view_collections.urls')),
    path('changepass/', include('change_pass.urls')),
    path('newcollection/', include('new_collection.urls')),
    path('pendingapproval/', include('pending_approval.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    
