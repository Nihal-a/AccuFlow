from django.db import models

from django.contrib.auth.models import BaseUserManager, AbstractBaseUser, PermissionsMixin, Group, Permission

class UserAccountManager(BaseUserManager):
    def create_user(self, username, password=None, **extra_fields):
        """
        Base user creation method for all user types.
        """
        if not username:
            raise ValueError('The username field is required')

        user = self.model(username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_collector(self, username, password=None):
        user = self.create_user(
            username=username,
            password=password,
            is_client=False,
            is_collector=True
        )
        return user

    def create_client(self, username, password=None):
        user = self.create_user(
            username=username,
            password=password,
            is_client=True,
            is_collector=False
        )
        return user

    def create_superuser(self, username, password):
        user = self.create_user(
            username=username,
            password=password,
            is_admin=True,
            is_staff=True,
            is_client=False,
            is_collector=False,
            is_superuser=True,
        )
        user.save(using=self._db)
        return user


class UserAccount(AbstractBaseUser, PermissionsMixin):
    username = models.CharField(max_length=200, unique=True) 
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_admin = models.BooleanField(default=False)
    is_client = models.BooleanField(default=True)
    is_collector = models.BooleanField(default=False)

    groups = models.ManyToManyField(
        Group,
        related_name='user_accounts',
        blank=True,
        help_text='The groups this user belongs to.',
    )

    user_permissions = models.ManyToManyField(
        Permission,
        related_name='user_accounts',
        blank=True,
        help_text='Specific permissions for this user.',
    )

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = []

    objects = UserAccountManager()

    def __str__(self):
        return self.username or "Unnamed User"

    class Meta:
        verbose_name = "User Account"
        verbose_name_plural = "User Accounts"
    

class Clients(models.Model):
    name = models.TextField(blank=True,null=True)
    user = models.ForeignKey(UserAccount,on_delete=models.CASCADE,blank=True,null=True)
    email = models.TextField(blank=True,null=True)
    is_active= models.BooleanField(default=True)
    phone = models.TextField(blank=True,null=True)
    wa = models.TextField(blank=True,null=True)
    country_code = models.TextField(blank=True,null=True)
    clientId = models.TextField(blank=True,null=True)
    


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
    client = models.ForeignKey(Clients,on_delete=models.CASCADE,blank=True,null=True)
    credit = models.FloatField(default=0)
    debit = models.FloatField(default=0)
    open_balance = models.FloatField(default=0)
    otc_balance = models.FloatField(default=0)
    
    def __str__(self):
        return self.name
    
    @property
    def get_balance(self):
        return self.balance 
    
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
    credit = models.FloatField(default=0)
    debit = models.FloatField(default=0)
    balance = models.FloatField(default=0)
    client = models.ForeignKey(Clients,on_delete=models.CASCADE,blank=True,null=True)
    open_balance = models.FloatField(default=0)
    otc_balance = models.FloatField(default=0)
    
    def __str__(self):
        return self.name
    @property
    def get_balance(self):
        return self.balance 
    
    
    
class Expenses(models.Model):
    category  = models.TextField(blank=True,null=True)
    expenseId = models.TextField(blank=True,null=True)
    description = models.TextField(blank=True,null=True) 
    amount = models.FloatField(default=0)
    created_at = models.DateTimeField(auto_now_add=True,blank=True,null=True)
    is_active = models.BooleanField(default=True)
    client = models.ForeignKey(Clients,on_delete=models.CASCADE,blank=True,null=True)
    
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
    client = models.ForeignKey(Clients,on_delete=models.CASCADE,blank=True,null=True)
    credit = models.FloatField(default=0)
    debit = models.FloatField(default=0)
    qty = models.IntegerField(default=0)
    open_balance = models.FloatField(default=0)
    otc_balance = models.FloatField(default=0)
    
    
    def __str__(self):
        return self.name
    
    @property
    def get_balance(self):
        return self.qty 
    
class CashBanks(models.Model):
    name  = models.TextField(blank=True,null=True)
    cashbankId = models.TextField(blank=True,null=True)
    description = models.TextField(blank=True,null=True) 
    created_at = models.DateTimeField(auto_now_add=True,blank=True,null=True)
    is_active = models.BooleanField(default=True)
    client = models.ForeignKey(Clients,on_delete=models.CASCADE,blank=True,null=True)
    
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
    client = models.ForeignKey(Clients,on_delete=models.CASCADE,blank=True,null=True)
    
    
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
    client = models.ForeignKey(Clients,on_delete=models.CASCADE,blank=True,null=True)
    seller_balance = models.FloatField(default=0)
    purchaser_balance = models.FloatField(default=0)
    
    
    
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
    client = models.ForeignKey(Clients,on_delete=models.CASCADE,blank=True,null=True)
    seller_balance = models.FloatField(default=0)
    purchaser_balance = models.FloatField(default=0)
    
    
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
    client = models.ForeignKey(Clients,on_delete=models.CASCADE,blank=True,null=True)
    godown_balance = models.FloatField(default=0)
    
    
    def __str__(self):
        return self.commission_no
    
        

class NSDs(models.Model):
    nsd_no = models.TextField(blank=True,null=True)
    sender_supplier = models.ForeignKey(Suppliers, on_delete=models.CASCADE, blank=True, null=True,related_name='sender_supplier')
    sender_customer = models.ForeignKey(Customers, on_delete=models.CASCADE, blank=True, null=True,related_name='sender_customer')
    receiver_supplier = models.ForeignKey(Suppliers, on_delete=models.CASCADE, blank=True, null=True,related_name='receiver_supplier')
    receiver_customer = models.ForeignKey(Customers, on_delete=models.CASCADE, blank=True, null=True,related_name='receiver_customer')
    date = models.DateField(blank=True,null=True)
    code = models.TextField(blank=True,null=True)
    qty = models.FloatField(default=0)
    sell_rate = models.FloatField(default=0)
    sell_amount = models.FloatField(default=0)
    purchase_rate = models.FloatField(default=0)
    purchase_amount = models.FloatField(default=0)
    created_at = models.DateTimeField(auto_now_add=True,blank=True,null=True)
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True,null=True)
    hold = models.BooleanField(default=False)
    type = models.TextField(blank=True,null=True)
    client = models.ForeignKey(Clients,on_delete=models.CASCADE,blank=True,null=True)
    sender_balance = models.FloatField(default=0)
    receiver_balance = models.FloatField(default=0)
    
    
    def __str__(self):
        return self.nsd_no
    
    @property
    def which_sender_type(self):
        if (self.sender_supplier == None) and (self.sender_customer != None):
            return 'customers'
        elif (self.sender_customer == None) and (self.sender_supplier != None):
            return 'suppliers'
    
    @property
    def which_receiver_type(self):
        if (self.receiver_supplier == None) and (self.receiver_customer != None):
            return 'customers'
        elif (self.receiver_customer == None) and (self.receiver_supplier != None):
            return 'suppliers'
    @property
    def sender(self):
        if (self.sender_supplier == None) and (self.sender_customer != None):
            return self.sender_customer
        elif (self.sender_customer == None) and (self.sender_supplier != None):
            return self.sender_supplier
    
    @property
    def receiver(self):
        if (self.receiver_supplier == None) and (self.receiver_customer != None):
            return self.receiver_customer
        elif (self.receiver_customer == None) and (self.receiver_supplier != None):
            return self.receiver_supplier 
        
    @property
    def party(self):
        if self.which_type == 'customers':
            return self.customer
        elif self.which_type == 'suppliers':
            return self.supplier
        
class Cashs(models.Model):
    cash_no = models.TextField(blank=True,null=True)
    cash_bank = models.ForeignKey(CashBanks, on_delete=models.CASCADE, blank=True, null=True)
    customer = models.ForeignKey(Customers, on_delete=models.CASCADE, blank=True, null=True)
    supplier = models.ForeignKey(Suppliers, on_delete=models.CASCADE, blank=True, null=True)
    date = models.DateField(blank=True,null=True)
    amount = models.FloatField(default=0)
    created_at = models.DateTimeField(auto_now_add=True,blank=True,null=True)
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True,null=True)
    hold = models.BooleanField(default=False)
    transaction = models.TextField(blank=True,null=True)
    client = models.ForeignKey(Clients,on_delete=models.CASCADE,blank=True,null=True)
    party_balance = models.FloatField(default=0)
     
    
    
    
    def __str__(self):
        return self.cash_no 
    
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
        

class StockTransfers(models.Model):
    transfer_no = models.TextField(blank=True, null=True)
    transfer_from = models.ForeignKey(Godowns,on_delete=models.CASCADE,related_name='transfers_from',blank=True, null=True)
    transfer_to = models.ForeignKey(Godowns,on_delete=models.CASCADE,related_name='transfers_to',blank=True,null=True)
    date = models.DateField(blank=True, null=True)
    code = models.TextField(blank=True, null=True)
    qty = models.FloatField(default=0)
    created_at = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True, null=True)
    hold = models.BooleanField(default=False)
    type = models.TextField(blank=True, null=True)
    client = models.ForeignKey(Clients, on_delete=models.CASCADE, blank=True, null=True)

    
    
    def __str__(self):
        return self.transfer_no
    
        