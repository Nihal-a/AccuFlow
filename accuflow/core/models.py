from django.db import models


class Customers(models.Model):
    name = models.TextField(blank=True,null=True)
    customerId = models.TextField(blank=True,null=True)
    phone = models.TextField(blank=True,null=True)
    address = models.TextField(blank=True,null=True)
    open_credit = models.FloatField(default=0)
    open_debit = models.FloatField(default=0)
    otc_credit = models.FloatField(default=0)
    otc_debit = models.FloatField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return self.name
    