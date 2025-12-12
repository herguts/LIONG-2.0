from django.db import models
from django.utils import timezone

class Admin(models.Model):
    ROLE_CHOICES = [
        ('super_admin', 'Super Admin'),
        ('department_admin', 'Department Admin'),
        ('inventory_admin', 'Inventory Admin'),
        ('employee', 'Employee'),
    ]

    acc_id = models.AutoField(primary_key=True)  # match your PostgreSQL PK
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=255)
    role = models.CharField(max_length=50, choices=ROLE_CHOICES)
    department = models.CharField(max_length=100, blank=True, null=True)
    is_approved = models.BooleanField(default=False)  # New field
    is_active = models.BooleanField(default=True)     # New field
    created_at = models.DateTimeField(auto_now_add=True)  # New field

    def __str__(self):
        return f"{self.name} ({self.role})"

    class Meta:
        db_table = 'account'


class Employee(models.Model):
    employee_id = models.AutoField(primary_key=True)
    admin = models.ForeignKey(Admin, db_column='acc_id', on_delete=models.CASCADE, related_name='employee_record')
    employee_name = models.CharField(max_length=100)
    contact_type = models.CharField(max_length=10, default="N/A")
    contact_value = models.CharField(max_length=100, default="N/A")
    position = models.CharField(max_length=50, blank=True, null=True)
    department = models.CharField(max_length=50, blank=True, null=True)
    date_joined = models.DateField()
    date_added = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=10, 
        choices=[('active', 'Active'), ('inactive', 'Inactive')], 
        default='active'
    )

    class Meta:
        db_table = "employee"

    def __str__(self):
        return self.employee_name

class Products(models.Model):
    product_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255)
    unit = models.CharField(max_length=50)
    stock = models.IntegerField(default=0)

    class Meta:
        db_table = "products"

    def __str__(self):
        return self.name


class Requisition(models.Model):

    STATUS_CHOICES = [
        ('Pending Approval', 'Pending Approval'),
        ('Approved', 'Approved'),
        ('Partially Approved – Pending Purchase', 'Partially Approved – Pending Purchase'),
        ('Denied', 'Denied'),
        ('Pending Purchase', 'Pending Purchase'),
        ('Purchased', 'Purchased'),
        ('Ready for Pickup', 'Ready for Pickup'),
        ('Received', 'Received'),

    ]

    requisition_id = models.AutoField(primary_key=True)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    date_requested = models.DateTimeField(auto_now_add=True)
    admin_message = models.TextField(blank=True, null=True)
    

    # UPDATED to match your new SQL table
    status = models.CharField(
        max_length=100,
        choices=STATUS_CHOICES,
        default='Pending Approval'
    )

    remarks = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "requisition"

    def __str__(self):
        return f"REQ-{self.requisition_id} | {self.employee.employee_name}"


class Requisition_Item(models.Model):
    id = models.AutoField(primary_key=True)
    requisition = models.ForeignKey(Requisition, on_delete=models.CASCADE)
    product = models.ForeignKey(Products, on_delete=models.CASCADE)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    approved_qty = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    purchase_qty = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    fulfilled_qty = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # ADD THIS LINE
    reserved_qty = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # Reserved when marked ready
    issued_qty = models.DecimalField(max_digits=10, decimal_places=2, default=0)    # Actually issued when received

    class Meta:
        db_table = "requisition_item"

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"


class RequisitionStatusHistory(models.Model):
    history_id = models.AutoField(primary_key=True)
    requisition = models.ForeignKey(
        Requisition,
        on_delete=models.CASCADE,
        db_column='requisition_id'
    )
    old_status = models.CharField(max_length=40, null=True, blank=True)
    new_status = models.CharField(max_length=40)
    changed_by = models.ForeignKey(
        Admin,
        on_delete=models.CASCADE,
        db_column='changed_by'  # matches your table column
    )
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'requisition_status_history'

    def __str__(self):
        return f"REQ-{self.requisition.requisition_id}: {self.old_status} → {self.new_status}"



class InventoryBalance(models.Model):
    balance_id = models.AutoField(primary_key=True)
    product = models.ForeignKey(Products, on_delete=models.CASCADE)
    unit = models.CharField(max_length=20)
    opening_inventory = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    quantity_unit = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    quantity_meters = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    quantity_klg = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    min_stock = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    procurement_suggestion = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.product.name} - {self.unit}"

    class Meta:
        db_table = 'inventory_balance'  

class StockIn(models.Model):
    stock_in_id = models.AutoField(primary_key=True)
    product = models.ForeignKey(Products, on_delete=models.CASCADE)
    unit = models.CharField(max_length=20)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    quantity_meters = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    quantity_klg = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    date_in = models.DateField()
    acc = models.ForeignKey(Admin, on_delete=models.CASCADE, db_column='acc_id', null=True)

    class Meta:
        db_table = 'stock_in'

    def __str__(self):
        return f"{self.product.item_name} - {self.quantity} {self.unit} (In)"

class StockOut(models.Model):
    stock_out_id = models.AutoField(primary_key=True)
    product = models.ForeignKey(Products, on_delete=models.CASCADE)
    unit = models.CharField(max_length=20)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    quantity_meters = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    quantity_klg = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    date_out = models.DateField()
    acc = models.ForeignKey(Admin, on_delete=models.CASCADE, db_column='acc_id', null=True)

    purpose = models.CharField(max_length=255, default="Stock Issuance", blank=True)
    status = models.CharField(
        max_length=20, 
        default="reserved", 
        choices=[
            ('reserved', 'Reserved'),
            ('issued', 'Issued'), 
            ('cancelled', 'Cancelled'),
            ('returned', 'Returned')
        ]
    )
    requisition = models.ForeignKey('Requisition', on_delete=models.SET_NULL, null=True, blank=True)
    notes = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'stock_out'

    def __str__(self):
        return f"{self.product.item_name} - {self.quantity} {self.unit} (Out)"
    










# Add these to your models.py

# Add these to your existing models.py

class Supplier(models.Model):
    supplier_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=200)
    contact_person = models.CharField(max_length=100, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=20)
    address = models.TextField(blank=True, null=True)
    payment_terms = models.CharField(max_length=100, default="Net 30")
    status = models.CharField(
        max_length=20,
        choices=[('active', 'Active'), ('inactive', 'Inactive')],
        default='active'
    )
    date_added = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'supplier'

    def __str__(self):
        return self.name


class PurchaseRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('denied', 'Denied'),
        ('cancelled', 'Cancelled'),
    ]

    PAYMENT_METHODS = [
        ('cash_on_delivery', 'Cash on Delivery'),
        ('bank_transfer', 'Bank Transfer'),
        ('gcash', 'GCash'),
        ('check', 'Check'),
        ('credit', 'Credit'),
    ]

    request_id = models.AutoField(primary_key=True)
    requisition = models.ForeignKey(
        Requisition, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        db_column='requisition_id'  # Explicitly specify column name
    )
    requested_by = models.ForeignKey(
        Admin, 
        on_delete=models.CASCADE, 
        related_name='purchase_requests',
        db_column='requested_by'  # Explicitly specify column name
    )
    request_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='pending')
    total_estimated_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    payment_method = models.CharField(max_length=50, choices=PAYMENT_METHODS, default='cash_on_delivery')
    remarks = models.TextField(blank=True, null=True)
    approved_by = models.ForeignKey(
        Admin, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='approved_purchases',
        db_column='approved_by'  # Explicitly specify column name
    )
    approval_date = models.DateTimeField(null=True, blank=True)
    denial_reason = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'purchase_request'

    def save(self, *args, **kwargs):
        # Auto-calculate total cost when saving
        if self.pk:
            items = self.purchaserequestitem_set.all()
            self.total_estimated_cost = sum(item.total_estimated_price for item in items)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"PR-{self.request_id} ({self.get_status_display()})"


class PurchaseRequestItem(models.Model):
    item_id = models.AutoField(primary_key=True)
    request = models.ForeignKey(
        PurchaseRequest, 
        on_delete=models.CASCADE,
        db_column='request_id'  # Explicitly specify column name
    )
    requisition_item = models.ForeignKey(
        Requisition_Item, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        db_column='requisition_item_id'  # Explicitly specify column name
    )
    product = models.ForeignKey(
        Products, 
        on_delete=models.CASCADE,
        db_column='product_id'  # Explicitly specify column name
    )
    quantity_to_purchase = models.DecimalField(max_digits=10, decimal_places=2)
    estimated_unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_estimated_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        db_table = 'purchase_request_item'

    def save(self, *args, **kwargs):
        from decimal import Decimal
        
        # Ensure both are Decimal objects before multiplication
        if not isinstance(self.quantity_to_purchase, Decimal):
            try:
                self.quantity_to_purchase = Decimal(str(self.quantity_to_purchase))
            except:
                self.quantity_to_purchase = Decimal('0')
        
        if not isinstance(self.estimated_unit_price, Decimal):
            try:
                self.estimated_unit_price = Decimal(str(self.estimated_unit_price))
            except:
                self.estimated_unit_price = Decimal('0')
        
        self.total_estimated_price = self.quantity_to_purchase * self.estimated_unit_price
        super().save(*args, **kwargs)

class PurchaseOrder(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('sent', 'Sent to Supplier'),
        ('ordered', 'Ordered'),
        ('partially_received', 'Partially Received'),
        ('received', 'Fully Received'),
        ('cancelled', 'Cancelled'),
    ]

    po_id = models.AutoField(primary_key=True)
    po_number = models.CharField(max_length=50, unique=True)
    request = models.ForeignKey(
        PurchaseRequest, 
        on_delete=models.CASCADE,
        db_column='request_id'  # Explicitly specify column name
    )
    supplier = models.ForeignKey(
        Supplier, 
        on_delete=models.CASCADE,
        db_column='supplier_id'  # Explicitly specify column name
    )
    created_by = models.ForeignKey(
        Admin, 
        on_delete=models.CASCADE, 
        related_name='created_pos',
        db_column='created_by'  # Explicitly specify column name
    )
    created_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='draft')
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    delivery_date = models.DateField(null=True, blank=True)
    payment_terms = models.CharField(max_length=100, default="Net 30")
    notes = models.TextField(blank=True, null=True)
    sent_date = models.DateTimeField(null=True, blank=True)
    completed_date = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'purchase_order'

    def save(self, *args, **kwargs):
        if not self.po_number:
            year = timezone.now().strftime('%Y')
            last_po = PurchaseOrder.objects.filter(
                po_number__startswith=f'PO-{year}-'
            ).order_by('-po_number').first()
            
            if last_po:
                last_num = int(last_po.po_number.split('-')[-1])
                new_num = last_num + 1
            else:
                new_num = 1
            
            self.po_number = f'PO-{year}-{new_num:04d}'
        
        # Auto-calculate total from items
        if self.pk:
            items = self.purchaseorderitem_set.all()
            self.total_amount = sum(item.total_price for item in items)
        
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.po_number} - {self.get_status_display()}"


class PurchaseOrderItem(models.Model):
    QUALITY_STATUS = [
        ('pending', 'Pending QC'),
        ('passed', 'Passed'),
        ('failed', 'Failed'),
        ('partial', 'Partially Passed'),
    ]

    po_item_id = models.AutoField(primary_key=True)
    po = models.ForeignKey(
        PurchaseOrder, 
        on_delete=models.CASCADE,
        db_column='po_id'  # Explicitly specify column name
    )
    product = models.ForeignKey(
        Products, 
        on_delete=models.CASCADE,
        db_column='product_id'  # Explicitly specify column name
    )
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    supplier_product_code = models.CharField(max_length=100, blank=True, null=True)
    received_quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    quality_status = models.CharField(max_length=20, choices=QUALITY_STATUS, default='pending')

    class Meta:
        db_table = 'purchase_order_item'

    @property
    def remaining_quantity(self):
        return self.quantity - self.received_quantity

    def save(self, *args, **kwargs):
        from decimal import Decimal
        
        # Ensure both are Decimal objects before multiplication
        if not isinstance(self.quantity, Decimal):
            try:
                self.quantity = Decimal(str(self.quantity))
            except:
                self.quantity = Decimal('0')
        
        if not isinstance(self.unit_price, Decimal):
            try:
                self.unit_price = Decimal(str(self.unit_price))
            except:
                self.unit_price = Decimal('0')
        
        # Now calculate total
        self.total_price = self.quantity * self.unit_price
        super().save(*args, **kwargs)

class SupplierQuotation(models.Model):
    quotation_id = models.AutoField(primary_key=True)
    po_item = models.ForeignKey(
        PurchaseOrderItem, 
        on_delete=models.CASCADE,
        db_column='po_item_id'  # Explicitly specify column name
    )
    supplier = models.ForeignKey(
        Supplier, 
        on_delete=models.CASCADE,
        db_column='supplier_id'  # Explicitly specify column name
    )
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    valid_until = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True, null=True)
    submitted_date = models.DateTimeField(auto_now_add=True)
    is_selected = models.BooleanField(default=False)

    class Meta:
        db_table = 'supplier_quotation'


class PurchaseReceiving(models.Model):
    RECEIVING_STATUS = [
        ('pending', 'Pending QC'),
        ('partial', 'Partially Received'),
        ('complete', 'Complete'),
        ('with_rejections', 'Complete with Rejections'),
        ('cancelled', 'Cancelled'),
    ]

    receiving_number = models.CharField(max_length=50, unique=True, blank=True, null=True)


    receiving_id = models.AutoField(primary_key=True)
    po = models.ForeignKey(
        PurchaseOrder, 
        on_delete=models.CASCADE,
        db_column='po_id'  # Explicitly specify column name
    )
    received_by = models.ForeignKey(
        Admin, 
        on_delete=models.CASCADE,
        db_column='received_by'  # Explicitly specify column name
    )
    receive_date = models.DateTimeField(auto_now_add=True)
    invoice_number = models.CharField(max_length=100, blank=True, null=True)
    delivery_note_number = models.CharField(max_length=100, blank=True, null=True)
    carrier = models.CharField(max_length=100, blank=True, null=True)
    quality_check_notes = models.TextField(blank=True, null=True)
    overall_status = models.CharField(max_length=20, choices=RECEIVING_STATUS, default='pending')
    receiving_number = models.CharField(max_length=50, unique=True, blank=True, null=True)

    class Meta:
        db_table = 'purchase_receiving'

    def save(self, *args, **kwargs):
        if not self.receiving_number:
            self.receiving_number = f"REC{timezone.now().strftime('%Y%m%d%H%M%S')}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Receiving #{self.receiving_number}"

class QualityCheck(models.Model):
    REJECTION_DISPOSITION_CHOICES = [
        ('return', 'Return to Supplier'),
        ('keep_as_rejected', 'Keep as Rejected Stock'),
        ('destroy', 'Destroy/Dispose'),
        ('replace', 'Request Replacement'),
    ]
    
    check_id = models.AutoField(primary_key=True)
    receiving = models.ForeignKey(
        PurchaseReceiving, 
        on_delete=models.CASCADE,
        db_column='receiving_id'
    )
    checker = models.ForeignKey(
        Admin,
        on_delete=models.SET_NULL,
        null=True,
        db_column='checker'
    )
    check_date = models.DateTimeField(default=timezone.now)
    overall_status = models.CharField(max_length=20, default='pending')
    notes = models.TextField(blank=True, null=True)
    rejection_disposition = models.CharField(
        max_length=20, 
        choices=REJECTION_DISPOSITION_CHOICES, 
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'quality_check'


class RejectedItem(models.Model):
    REJECTION_REASON_CHOICES = [
        ('damaged', 'Damaged Goods'),
        ('wrong_item', 'Wrong Item'),
        ('expired', 'Expired Product'),
        ('poor_quality', 'Poor Quality'),
        ('shortage', 'Short Quantity'),
        ('wrong_spec', 'Wrong Specifications'),
        ('late_delivery', 'Late Delivery'),
        ('packaging_issue', 'Packaging Issue'),
        ('other', 'Other'),
    ]
    
    rejected_id = models.AutoField(primary_key=True)
    receiving = models.ForeignKey(
        PurchaseReceiving, 
        on_delete=models.CASCADE,
        db_column='receiving_id'
    )
    po_item = models.ForeignKey(
        PurchaseOrderItem, 
        on_delete=models.CASCADE,
        db_column='po_item_id'
    )
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    reason = models.CharField(max_length=20, choices=REJECTION_REASON_CHOICES)
    details = models.TextField(blank=True, null=True)
    disposition = models.CharField(max_length=20)
    disposition_date = models.DateTimeField(null=True, blank=True)
    disposition_notes = models.TextField(blank=True, null=True)
    disposed_by = models.ForeignKey(
        Admin, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        db_column='disposed_by'
    )
    is_resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'rejected_item'

    def __str__(self):
        return f"Rejected {self.quantity} of {self.po_item.product.name}"


class RejectedStock(models.Model):
    STATUS_CHOICES = [
        ('quarantine', 'In Quarantine'),
        ('rework', 'Awaiting Rework'),
        ('scrap', 'For Scrap'),
        ('return_pending', 'Pending Return'),
        ('returned', 'Returned'),
        ('destroyed', 'Destroyed'),
        ('replaced', 'Replaced'),
    ]
    
    rejected_stock_id = models.AutoField(primary_key=True)
    rejected_item = models.ForeignKey(
        RejectedItem, 
        on_delete=models.CASCADE,
        db_column='rejected_id'
    )
    product = models.ForeignKey(
        Products, 
        on_delete=models.CASCADE,
        db_column='product_id'
    )
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    batch_number = models.CharField(max_length=100, blank=True, null=True)
    location = models.CharField(max_length=200)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='quarantine')
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'rejected_stock'


class ReturnRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('shipped', 'Shipped Back'),
        ('received_supplier', 'Received by Supplier'),
        ('cancelled', 'Cancelled'),
    ]
    
    return_id = models.AutoField(primary_key=True)
    rejected_item = models.ForeignKey(
        RejectedItem, 
        on_delete=models.CASCADE,
        db_column='rejected_id'
    )
    request_number = models.CharField(max_length=50, unique=True)
    requested_by = models.ForeignKey(
        Admin, 
        on_delete=models.SET_NULL, 
        null=True,
        db_column='requested_by'
    )
    requested_date = models.DateTimeField(default=timezone.now)
    expected_return_date = models.DateField(null=True, blank=True)
    actual_return_date = models.DateField(null=True, blank=True)
    return_tracking = models.CharField(max_length=100, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'return_request'

    def save(self, *args, **kwargs):
        if not self.request_number:
            self.request_number = f"RTN{timezone.now().strftime('%Y%m%d%H%M%S')}"
        super().save(*args, **kwargs)


class DisposalRecord(models.Model):
    DISPOSAL_METHOD_CHOICES = [
        ('landfill', 'Landfill'),
        ('incineration', 'Incineration'),
        ('recycling', 'Recycling'),
        ('donation', 'Donation'),
        ('other', 'Other'),
    ]
    
    disposal_id = models.AutoField(primary_key=True)
    rejected_item = models.ForeignKey(
        RejectedItem, 
        on_delete=models.CASCADE,
        db_column='rejected_id'
    )
    disposal_number = models.CharField(max_length=50, unique=True)
    method = models.CharField(max_length=20, choices=DISPOSAL_METHOD_CHOICES)
    disposal_date = models.DateField()
    disposed_by = models.ForeignKey(
        Admin, 
        on_delete=models.SET_NULL, 
        null=True,
        db_column='disposed_by'
    )
    witness = models.CharField(max_length=200, blank=True, null=True)
    certificate_number = models.CharField(max_length=100, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'disposal_record'

    def save(self, *args, **kwargs):
        if not self.disposal_number:
            self.disposal_number = f"DISP{timezone.now().strftime('%Y%m%d%H%M%S')}"
        super().save(*args, **kwargs)


class ReplacementRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('ordered', 'Ordered'),
        ('shipped', 'Shipped'),
        ('received', 'Received'),
        ('cancelled', 'Cancelled'),
    ]
    
    replacement_id = models.AutoField(primary_key=True)
    rejected_item = models.ForeignKey(
        RejectedItem, 
        on_delete=models.CASCADE,
        db_column='rejected_id'
    )
    request_number = models.CharField(max_length=50, unique=True)
    requested_by = models.ForeignKey(
        Admin, 
        on_delete=models.SET_NULL, 
        null=True,
        db_column='requested_by'
    )
    requested_date = models.DateTimeField(default=timezone.now)
    expected_delivery_date = models.DateField(null=True, blank=True)
    replacement_po = models.ForeignKey(
        PurchaseOrder, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        db_column='replacement_po_id'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'replacement_request'

    def save(self, *args, **kwargs):
        if not self.request_number:
            self.request_number = f"REP{timezone.now().strftime('%Y%m%d%H%M%S')}"
        super().save(*args, **kwargs)


class ReceivedItem(models.Model):
    received_item_id = models.AutoField(primary_key=True)
    receiving = models.ForeignKey(
        PurchaseReceiving, 
        on_delete=models.CASCADE,
        db_column='receiving_id'  # Explicitly specify column name
    )
    po_item = models.ForeignKey(
        PurchaseOrderItem, 
        on_delete=models.CASCADE,
        db_column='po_item_id'  # Explicitly specify column name
    )
    quantity_received = models.DecimalField(max_digits=10, decimal_places=2)
    quantity_accepted = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    quantity_rejected = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    rejection_reason = models.TextField(blank=True, null=True)
    quality_checker = models.ForeignKey(
        Admin, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        db_column='quality_checker'  # Explicitly specify column name
    )
    quality_check_date = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'received_item'

    def save(self, *args, **kwargs):
        # Auto-calculate accepted quantity
        if not self.quantity_accepted:
            self.quantity_accepted = self.quantity_received - self.quantity_rejected
        super().save(*args, **kwargs)


class PurchaseOrderHistory(models.Model):
    history_id = models.AutoField(primary_key=True)
    po = models.ForeignKey(
        PurchaseOrder, 
        on_delete=models.CASCADE,
        db_column='po_id'  # Explicitly specify column name
    )
    old_status = models.CharField(max_length=30, blank=True, null=True)
    new_status = models.CharField(max_length=30)
    changed_by = models.ForeignKey(
        Admin, 
        on_delete=models.CASCADE,
        db_column='changed_by'  # Explicitly specify column name
    )
    changed_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'purchase_order_history'


