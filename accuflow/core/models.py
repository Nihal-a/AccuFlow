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
    country_code = models.TextField(blank=True,null=True)
    wa = models.TextField(blank=True,null=True)
    
    def __str__(self):
        return self.name
    
class Suppliers(models.Model):
    name = models.TextField(blank=True,null=True)
    supplierId = models.TextField(blank=True,null=True)
    phone = models.TextField(blank=True,null=True)
    address = models.TextField(blank=True,null=True)
    open_credit = models.FloatField(default=0)
    open_debit = models.FloatField(default=0)
    otc_credit = models.FloatField(default=0)
    otc_debit = models.FloatField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    country_code = models.TextField(blank=True,null=True)
    wa = models.TextField(blank=True,null=True)
    
    def __str__(self):
        return self.name
    
class Expenses(models.Model):
    category  = models.TextField(blank=True,null=True)
    expenseId = models.TextField(blank=True,null=True)
    description = models.TextField(blank=True,null=True) 
    amount = models.FloatField(default=0)
    created_at = models.DateTimeField(auto_now_add=True,blank=True,null=True)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return self.category
    

class Godowns(models.Model):
    name = models.TextField(blank=True,null=True)
    godownId = models.TextField(blank=True,null=True)
    phone = models.TextField(blank=True,null=True)
    address = models.TextField(blank=True,null=True)
    open_credit = models.FloatField(default=0)
    open_debit = models.FloatField(default=0)
    otc_credit = models.FloatField(default=0)
    otc_debit = models.FloatField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    country_code = models.TextField(blank=True,null=True)
    wa = models.TextField(blank=True,null=True)
    
    def __str__(self):
        return self.name
    
class CashBanks(models.Model):
    name  = models.TextField(blank=True,null=True)
    cashbankId = models.TextField(blank=True,null=True)
    description = models.TextField(blank=True,null=True) 
    created_at = models.DateTimeField(auto_now_add=True,blank=True,null=True)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return self.name
    
class Collectors(models.Model):
    name = models.TextField(blank=True,null=True)
    collectorId = models.TextField(blank=True,null=True)
    phone = models.TextField(blank=True,null=True)
    address = models.TextField(blank=True,null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    country_code = models.TextField(blank=True,null=True)
    wa = models.TextField(blank=True,null=True)
    
    
class Purchases(models.Model):
    purchase_no = models.TextField(blank=True,null=True)
    supplier = models.ForeignKey(Suppliers, on_delete=models.CASCADE, blank=True, null=True)
    customers = models.ForeignKey(Customers, on_delete=models.CASCADE, blank=True, null=True)
    godown = models.ForeignKey(Godowns, on_delete=models.CASCADE, blank=True, null=True)
    date = models.DateField(blank=True,null=True)
    code = models.TextField(blank=True,null=True)
    qty = models.FloatField(default=0)
    rate = models.FloatField(default=0)
    amount = models.FloatField(default=0)
    created_at = models.DateTimeField(auto_now_add=True,blank=True,null=True)
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True,null=True)
    
    def __str__(self):
        return self.purchase_no
    