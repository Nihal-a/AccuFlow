from django.contrib import admin
from .models import SubscriptionPayment, SubscriptionPlan, Clients

@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'duration_days', 'is_active')

@admin.register(SubscriptionPayment)
class SubscriptionPaymentAdmin(admin.ModelAdmin):
    list_display = ('client', 'plan', 'amount', 'date')
    search_fields = ('client__name', 'plan__name', 'transaction_id')
    list_filter = ('date', 'plan')
    
    class Media:
        js = ('admin/js/subscription_payment.js',)
