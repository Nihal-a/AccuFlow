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
    balance = models.FloatField(default=0)
    
    def __str__(self):
        return self.name
    
    @property
    def get_balance(self):
        return self.open_debit - self.open_credit
    
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
    balance = models.FloatField(default=0)
    
    def __str__(self):
        return self.name
    @property
    def get_balance(self):
        return self.open_debit - self.open_credit
    
    
    
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
    balance = models.FloatField(default=0)
    
    def __str__(self):
        return self.name
    
    @property
    def get_balance(self):
        return self.open_debit - self.open_credit
    
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
    godown = models.ForeignKey(Godowns, on_delete=models.CASCADE, blank=True, null=True)
    customer = models.ForeignKey(Customers, on_delete=models.CASCADE, blank=True, null=True)
    date = models.DateField(blank=True,null=True)
    code = models.TextField(blank=True,null=True)
    qty = models.FloatField(default=0)
    amount = models.FloatField(default=0)
    total_amount = models.FloatField(default=0)
    created_at = models.DateTimeField(auto_now_add=True,blank=True,null=True)
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True,null=True)
    hold = models.BooleanField(default=False)
    type = models.TextField(blank=True,null=True)
    
    
    def __str__(self):
        return self.purchase_no
    
    @property
    def which_type(self):
        if (self.supplier == None) and (self.customer != None):
            return 'customers'
        elif (self.customer == None) and (self.supplier != None):
            return 'suppliers'
        
    @property
    def party(self):
        if self.which_type == 'customers':
            return self.customer
        elif self.which_type == 'suppliers':
            return self.supplier
    
class Sales(models.Model):
    sale_no = models.TextField(blank=True,null=True)
    supplier = models.ForeignKey(Suppliers, on_delete=models.CASCADE, blank=True, null=True)
    godown = models.ForeignKey(Godowns, on_delete=models.CASCADE, blank=True, null=True)
    customer = models.ForeignKey(Customers, on_delete=models.CASCADE, blank=True, null=True)
    date = models.DateField(blank=True,null=True)
    code = models.TextField(blank=True,null=True)
    qty = models.FloatField(default=0)
    amount = models.FloatField(default=0)
    total_amount = models.FloatField(default=0)
    created_at = models.DateTimeField(auto_now_add=True,blank=True,null=True)
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True,null=True)
    hold = models.BooleanField(default=False)
    type = models.TextField(blank=True,null=True)
    
    
    def __str__(self):
        return self.sale_no
    
    @property
    def which_type(self):
        if (self.supplier == None) and (self.customer != None):
            return 'customers'
        elif (self.customer == None) and (self.supplier != None):
            return 'suppliers'
        
    @property
    def party(self):
        if self.which_type == 'customers':
            return self.customer
        elif self.which_type == 'suppliers':
            return self.supplier
    
class NSD(models.Model):
    nsd_no = models.TextField(blank=True,null=True)
    supplier = models.ForeignKey(Suppliers, on_delete=models.CASCADE, blank=True, null=True)
    customer = models.ForeignKey(Customers, on_delete=models.CASCADE, blank=True, null=True)
    date = models.DateField(blank=True,null=True)
    code = models.TextField(blank=True,null=True)
    qty = models.FloatField(default=0)
    sell_rate = models.FloatField(default=0)
    purchase_rate = models.FloatField(default=0)
    sell_amount = models.FloatField(default=0)
    purchase_amount = models.FloatField(default=0)
    created_at = models.DateTimeField(auto_now_add=True,blank=True,null=True)
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True,null=True)
    
    def __str__(self):
        return self.nsd_no   

class Commissions(models.Model):
    commission_no = models.TextField(blank=True,null=True)
    expense = models.ForeignKey(Expenses, on_delete=models.CASCADE, blank=True, null=True)
    godown = models.ForeignKey(Godowns, on_delete=models.CASCADE, blank=True, null=True)
    date = models.DateField(blank=True,null=True)
    code = models.TextField(blank=True,null=True)
    qty = models.FloatField(default=0)
    amount = models.FloatField(default=0)
    total_amount = models.FloatField(default=0)
    created_at = models.DateTimeField(auto_now_add=True,blank=True,null=True)
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True,null=True)
    hold = models.BooleanField(default=False)
    type = models.TextField(blank=True,null=True)
    
    
    def __str__(self):
        return self.commission_no
    
    # @property
    # def which_type(self):
    #     if (self.supplier == None) and (self.customer != None):
    #         return 'customers'
    #     elif (self.customer == None) and (self.supplier != None):
    #         return 'suppliers'
        
    # @property
    # def party(self):
    #     if self.which_type == 'customers':
    #         return self.customer
    #     elif self.which_type == 'suppliers':
    #         return self.supplier