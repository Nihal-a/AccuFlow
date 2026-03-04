from django.db import models
from decimal import Decimal
from django.utils import timezone
import uuid
from django.contrib.auth.models import BaseUserManager, AbstractBaseUser, PermissionsMixin, Group, Permission

class SoftDeleteMixin(models.Model):
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True

    def soft_delete(self):
        self.is_active = False
        self.deleted_at = timezone.now()
        self.save()

    def save(self, *args, **kwargs):
        if not self.is_active:
            if self.deleted_at is None:
                self.deleted_at = timezone.now()
        else:
            self.deleted_at = None
        super().save(*args, **kwargs)

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

    last_session_key = models.CharField(max_length=40, null=True, blank=True)

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = []

    objects = UserAccountManager()

    def __str__(self):
        return self.username or "Unnamed User"

    class Meta:
        verbose_name = "User Account"
        verbose_name_plural = "User Accounts"
    

class SubscriptionPlan(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    price = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal('0.00'))
    duration_days = models.IntegerField(default=30, help_text="Duration in days (e.g., 30 for monthly, 365 for yearly)")
    is_trial = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

class Clients(models.Model):
    name = models.TextField(blank=True,null=True)
    user = models.ForeignKey(UserAccount,on_delete=models.CASCADE,blank=True,null=True)
    email = models.TextField(blank=True,null=True)
    is_active= models.BooleanField(default=True)
    phone = models.TextField(blank=True,null=True)
    wa = models.TextField(blank=True,null=True)
    country_code = models.TextField(blank=True,null=True)
    clientId = models.TextField(blank=True,null=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    # Subscription Fields
    subscription_plan = models.ForeignKey(SubscriptionPlan, on_delete=models.SET_NULL, null=True, blank=True)
    subscription_start = models.DateField(null=True, blank=True)
    subscription_end = models.DateField(null=True, blank=True)
    is_trial_active = models.BooleanField(default=False)

    # WhatsApp Integration
    has_whatsapp_access = models.BooleanField(default=False)
    whatsapp_client_id = models.CharField(max_length=50, unique=True, null=True, blank=True, db_index=True)
    whatsapp_status = models.CharField(
        max_length=20, default='inactive', db_index=True,
        choices=[('inactive', 'Inactive'), ('pending', 'Pending'), ('linked', 'Linked')]
    )
    whatsapp_linked_at = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        # Auto-generate whatsapp_client_id when access is first enabled
        if self.has_whatsapp_access and not self.whatsapp_client_id:
            self.whatsapp_client_id = f'wa_{uuid.uuid4().hex[:12]}'
        super().save(*args, **kwargs)
    
    @property
    def is_subscription_active(self):
        # First check if the client record itself is active
        if not self.is_active:
            return False
            
        # Check trial status - if trial is active and not expired (implied by date if set)
        if self.is_trial_active and (not self.subscription_end or self.subscription_end >= timezone.now().date()):
            return True

        if not self.subscription_end:
            return False
            
        return self.subscription_end >= timezone.now().date()
    


class Customers(SoftDeleteMixin):
    name = models.TextField(blank=True,null=True)
    customerId = models.TextField(blank=True,null=True)
    phone = models.TextField(blank=True,null=True)
    address = models.TextField(blank=True,null=True)
    open_credit = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal('0.00'))
    open_debit = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal('0.00'))
    otc_credit = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal('0.00'))
    otc_debit = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal('0.00'))
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    country_code = models.TextField(blank=True,null=True)
    wa = models.TextField(blank=True,null=True)
    balance = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal('0.00'))
    client = models.ForeignKey(Clients,on_delete=models.CASCADE,blank=True,null=True)
    credit = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal('0.00'))
    debit = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal('0.00'))
    open_balance = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal('0.00'))
    otc_balance = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal('0.00'))
    
    def __str__(self):
        return self.name
    
    @property
    def get_balance(self):
        return self.balance 
    
class Suppliers(SoftDeleteMixin):
    name = models.TextField(blank=True,null=True)
    supplierId = models.TextField(blank=True,null=True)
    phone = models.TextField(blank=True,null=True)
    address = models.TextField(blank=True,null=True)
    open_credit = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal('0.00'))
    open_debit = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal('0.00'))
    otc_credit = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal('0.00'))
    otc_debit = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal('0.00'))
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    country_code = models.TextField(blank=True,null=True)
    wa = models.TextField(blank=True,null=True)
    credit = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal('0.00'))
    debit = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal('0.00'))
    balance = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal('0.00'))
    client = models.ForeignKey(Clients,on_delete=models.CASCADE,blank=True,null=True)
    open_balance = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal('0.00'))
    otc_balance = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal('0.00'))
    
    def __str__(self):
        return self.name
    @property
    def get_balance(self):
        return self.balance 
    
    
    
class Expenses(SoftDeleteMixin):
    category  = models.TextField(blank=True,null=True)
    expenseId = models.TextField(blank=True,null=True)
    description = models.TextField(blank=True,null=True) 
    amount = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal('0.00'))
    created_at = models.DateTimeField(auto_now_add=True,blank=True,null=True)
    is_active = models.BooleanField(default=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    client = models.ForeignKey(Clients,on_delete=models.CASCADE,blank=True,null=True)
    
    def __str__(self):
        return self.category
    

class Godowns(SoftDeleteMixin):
    name = models.TextField(blank=True,null=True)
    godownId = models.TextField(blank=True,null=True)
    phone = models.TextField(blank=True,null=True)
    address = models.TextField(blank=True,null=True)
    open_credit = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal('0.00'))
    open_debit = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal('0.00'))
    otc_credit = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal('0.00'))
    otc_debit = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal('0.00'))
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    country_code = models.TextField(blank=True,null=True)
    wa = models.TextField(blank=True,null=True)
    balance = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal('0.00'))
    client = models.ForeignKey(Clients,on_delete=models.CASCADE,blank=True,null=True)
    credit = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal('0.00'))
    debit = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal('0.00'))
    qty = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal('0.00'))
    open_balance = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal('0.00'))
    otc_balance = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal('0.00'))
    
    
    def __str__(self):
        return self.name
    
    @property
    def get_balance(self):
        return self.qty 
    
class CashBanks(SoftDeleteMixin):
    name  = models.TextField(blank=True,null=True)
    cashbankId = models.TextField(blank=True,null=True)
    description = models.TextField(blank=True,null=True) 
    created_at = models.DateTimeField(auto_now_add=True,blank=True,null=True)
    is_active = models.BooleanField(default=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    client = models.ForeignKey(Clients,on_delete=models.CASCADE,blank=True,null=True)
    balance = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal('0.00'))
    
    def __str__(self):
        return self.name
    
class Collectors(SoftDeleteMixin):
    name = models.TextField(blank=True,null=True)
    user = models.ForeignKey(UserAccount,on_delete=models.CASCADE,blank=True,null=True)
    collectorId = models.TextField(blank=True,null=True)
    phone = models.TextField(blank=True,null=True)
    address = models.TextField(blank=True,null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    country_code = models.TextField(blank=True,null=True)
    wa = models.TextField(blank=True,null=True)
    can_collect_directly = models.BooleanField(default=False)
    client = models.ForeignKey(Clients,on_delete=models.CASCADE,blank=True,null=True)
    
    
class Purchases(SoftDeleteMixin):
    purchase_no = models.TextField(blank=True,null=True)
    supplier = models.ForeignKey(Suppliers, on_delete=models.CASCADE, blank=True, null=True)
    godown = models.ForeignKey(Godowns, on_delete=models.CASCADE, blank=True, null=True)
    customer = models.ForeignKey(Customers, on_delete=models.CASCADE, blank=True, null=True)
    date = models.DateField(blank=True,null=True)
    code = models.TextField(blank=True,null=True)
    qty = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal('0.00'))
    amount = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal('0.00'))
    total_amount = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal('0.00'))
    created_at = models.DateTimeField(auto_now_add=True,blank=True,null=True)
    is_active = models.BooleanField(default=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    description = models.TextField(blank=True,null=True)
    hold = models.BooleanField(default=False)
    type = models.TextField(blank=True,null=True)
    client = models.ForeignKey(Clients,on_delete=models.CASCADE,blank=True,null=True)
    seller_balance = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal('0.00'))
    purchaser_balance = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal('0.00'))
    
    
    
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
    
class Sales(SoftDeleteMixin):
    sale_no = models.TextField(blank=True,null=True)
    supplier = models.ForeignKey(Suppliers, on_delete=models.RESTRICT, blank=True, null=True)
    godown = models.ForeignKey(Godowns, on_delete=models.RESTRICT, blank=True, null=True)
    customer = models.ForeignKey(Customers, on_delete=models.RESTRICT, blank=True, null=True)
    date = models.DateField(blank=True,null=True)
    code = models.TextField(blank=True,null=True)
    qty = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal('0.00'))
    amount = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal('0.00'))
    total_amount = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal('0.00'))
    created_at = models.DateTimeField(auto_now_add=True,blank=True,null=True)
    is_active = models.BooleanField(default=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    description = models.TextField(blank=True,null=True)
    hold = models.BooleanField(default=False)
    type = models.TextField(blank=True,null=True)
    client = models.ForeignKey(Clients,on_delete=models.CASCADE,blank=True,null=True)
    seller_balance = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal('0.00'))
    purchaser_balance = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal('0.00'))
    
    
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

class Commissions(SoftDeleteMixin):
    commission_no = models.TextField(blank=True,null=True)
    expense = models.ForeignKey(Expenses, on_delete=models.RESTRICT, blank=True, null=True)
    godown = models.ForeignKey(Godowns, on_delete=models.RESTRICT, blank=True, null=True)
    date = models.DateField(blank=True,null=True)
    code = models.TextField(blank=True,null=True)
    qty = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal('0.00'))
    amount = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal('0.00'))
    total_amount = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal('0.00'))
    created_at = models.DateTimeField(auto_now_add=True,blank=True,null=True)
    is_active = models.BooleanField(default=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    description = models.TextField(blank=True,null=True)
    hold = models.BooleanField(default=False)
    type = models.TextField(blank=True,null=True)
    client = models.ForeignKey(Clients,on_delete=models.CASCADE,blank=True,null=True)
    godown_balance = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal('0.00'))
    
    
    def __str__(self):
        return self.commission_no
    
        

class NSDs(SoftDeleteMixin):
    nsd_no = models.TextField(blank=True,null=True)
    sender_supplier = models.ForeignKey(Suppliers, on_delete=models.RESTRICT, blank=True, null=True,related_name='sender_supplier')
    sender_customer = models.ForeignKey(Customers, on_delete=models.RESTRICT, blank=True, null=True,related_name='sender_customer')
    receiver_supplier = models.ForeignKey(Suppliers, on_delete=models.RESTRICT, blank=True, null=True,related_name='receiver_supplier')
    receiver_customer = models.ForeignKey(Customers, on_delete=models.RESTRICT, blank=True, null=True,related_name='receiver_customer')
    date = models.DateField(blank=True,null=True)
    code = models.TextField(blank=True,null=True)
    qty = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal('0.00'))
    sell_rate = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal('0.00'))
    sell_amount = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal('0.00'))
    purchase_rate = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal('0.00'))
    purchase_amount = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal('0.00'))
    created_at = models.DateTimeField(auto_now_add=True,blank=True,null=True)
    is_active = models.BooleanField(default=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    description = models.TextField(blank=True,null=True)
    hold = models.BooleanField(default=False)
    type = models.TextField(blank=True,null=True)
    client = models.ForeignKey(Clients,on_delete=models.CASCADE,blank=True,null=True)
    sender_balance = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal('0.00'))
    receiver_balance = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal('0.00'))
    
    
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
        
class Cashs(SoftDeleteMixin):
    cash_no = models.TextField(blank=True,null=True)
    cash_bank = models.ForeignKey(CashBanks, on_delete=models.RESTRICT, blank=True, null=True)
    customer = models.ForeignKey(Customers, on_delete=models.RESTRICT, blank=True, null=True)
    supplier = models.ForeignKey(Suppliers, on_delete=models.RESTRICT, blank=True, null=True)
    date = models.DateField(blank=True,null=True)
    amount = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal('0.00'))
    created_at = models.DateTimeField(auto_now_add=True,blank=True,null=True)
    is_active = models.BooleanField(default=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    description = models.TextField(blank=True,null=True)
    hold = models.BooleanField(default=False)
    transaction = models.TextField(blank=True,null=True)
    client = models.ForeignKey(Clients,on_delete=models.CASCADE,blank=True,null=True)
    party_balance = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal('0.00'))
    cash_bank_balance = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal('0.00'))
     
    
    
    
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
        

class StockTransfers(SoftDeleteMixin):
    transfer_no = models.TextField(blank=True, null=True)
    transfer_from = models.ForeignKey(Godowns,on_delete=models.CASCADE,related_name='transfers_from',blank=True, null=True)
    transfer_to = models.ForeignKey(Godowns,on_delete=models.CASCADE,related_name='transfers_to',blank=True,null=True)
    date = models.DateField(blank=True, null=True)
    code = models.TextField(blank=True, null=True)
    qty = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal('0.00'))
    created_at = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    description = models.TextField(blank=True, null=True)
    hold = models.BooleanField(default=False)
    type = models.TextField(blank=True, null=True)
    client = models.ForeignKey(Clients, on_delete=models.CASCADE, blank=True, null=True)

    
    
    def __str__(self):
        return self.transfer_no

class Collection(SoftDeleteMixin):
    collector = models.ForeignKey(Collectors, on_delete=models.CASCADE, null=True, blank=True)
    date = models.DateField(null=True, blank=True)
    total_amount = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal('0.00'))
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    client = models.ForeignKey(Clients, on_delete=models.CASCADE, null=True, blank=True)
    
    STATUS_CHOICES = (
        ('New', 'New'),
        ('Pending', 'Pending Approval'),
        ('Approved', 'Approved'),
        ('Rejected', 'Rejected'),
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='New')
    approved_by = models.ForeignKey(UserAccount, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_collections')
    approval_date = models.DateTimeField(null=True, blank=True)
    is_viewed = models.BooleanField(default=False)

    def __str__(self):
        name = self.collector.name if self.collector else "Unknown"
        return f"Collection {self.id} - {name}"

class CollectionItem(models.Model):
    collection = models.ForeignKey(Collection, on_delete=models.CASCADE, related_name='items')
    transaction_id = models.CharField(max_length=100, null=True, blank=True)
    transaction_type = models.CharField(max_length=50, null=True, blank=True)
    amount = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal('0.00'))
    collected_amount = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal('0.00'))
    is_credit = models.BooleanField(default=False) 
    remark = models.TextField(blank=True, null=True) 
    
    def __str__(self):
        return f"{self.transaction_type} - {self.transaction_id}"

class SubscriptionPayment(models.Model):
    client = models.ForeignKey(Clients, on_delete=models.CASCADE)
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.SET_NULL, null=True)
    amount = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal('0.00'))
    date = models.DateField(auto_now_add=True)
    transaction_id = models.TextField(blank=True, null=True)
    payment_method = models.TextField(blank=True, null=True)
    is_renewal = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.client} - {self.plan} - {self.amount}"

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
import datetime

@receiver(post_save, sender=SubscriptionPayment)
def update_client_subscription(sender, instance, created, **kwargs):
    if created and instance.plan:
        client = instance.client
        plan = instance.plan
        
        # Update client subscription
        client.subscription_plan = plan
        client.subscription_start = timezone.now().date()
        client.subscription_end = client.subscription_start + datetime.timedelta(days=plan.duration_days)
        client.save()

class AdminExpense(models.Model):
    title = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal('0.00'))
    remark = models.TextField(blank=True, null=True)
    date = models.DateField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.title} - {self.amount}"
    
    def soft_delete(self):
        self.is_active = False
        self.deleted_at = timezone.now()
        self.save()

