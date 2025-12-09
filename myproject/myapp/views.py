from django.shortcuts import redirect, render
from myapp.models import Admin, Employee, Requisition, Requisition_Item, Products, InventoryBalance,StockIn, StockOut, RequisitionStatusHistory, PurchaseRequest, PurchaseRequestItem, Supplier, PurchaseOrder, PurchaseOrderItem, PurchaseOrderHistory, PurchaseReceiving, ReceivedItem, models
from django.contrib import messages
from django.utils.timezone import now
from django.utils.crypto import get_random_string
from datetime import date
from django.utils import timezone
from django.shortcuts import render, get_object_or_404
from django.db import transaction
from decimal import Decimal
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.db import IntegrityError
from django.http import HttpResponseRedirect
from django.urls import reverse


# Create your views here.
def dashboard(request):
    return render(request, "liong/dashBoard.html")



def admin_login(request):
    if request.method == 'POST':
        # Handle login
        if request.POST.get('form_type') == 'login':
            email = request.POST.get('email')
            password = request.POST.get('password')
            
            try:
                admin = Admin.objects.get(email=email)
                
                # Check if account is approved
                if not admin.is_approved:
                    messages.error(request, 'Your account is pending approval. Please contact administrator.')
                    return render(request, 'liong/login.html')
                
                # Check if account is active
                if not admin.is_active:
                    messages.error(request, 'Your account has been deactivated. Please contact administrator.')
                    return render(request, 'liong/login.html')
                
                # Plain-text password comparison
                if password == admin.password:
                    # For employee accounts, also check employee status
                    if admin.role == 'employee':
                        try:
                            employee = Employee.objects.get(admin=admin)
                            if employee.status != 'active':
                                messages.error(request, 'Your employee account is inactive.')
                                return render(request, 'liong/login.html')
                        except Employee.DoesNotExist:
                            # Employee record doesn't exist yet (might be pending creation by admin)
                            pass

                    # Set session
                    request.session['acc_id'] = admin.acc_id
                    request.session['admin_role'] = admin.role
                    request.session['admin_name'] = admin.name

                    messages.success(request, 'Login successful!')
                    
                    # Redirect based on role
                    if admin.role == 'super_admin':
                        return redirect('adminDashboard')
                    elif admin.role == 'department_admin':
                        return redirect('department_dashboard')
                    elif admin.role == 'inventory_admin':
                        return redirect('inventory_dashboard')
                    elif admin.role == 'employee':
                        return redirect('employeeDashboard')
                    else:
                        return redirect('admin_login')
                else:
                    messages.error(request, 'Incorrect password')

            except Admin.DoesNotExist:
                messages.error(request, 'Account not found')
                
    return render(request, 'liong/login.html')


def add_as_employee(request, acc_id):
    """Add an approved account as an employee - ONLY FOR EMPLOYEE ROLE"""
    if not request.session.get('acc_id'):
        messages.error(request, 'Please login first')
        return redirect('admin_login')
    
    if request.session.get('admin_role') != 'super_admin':
        messages.error(request, 'Access denied')
        return redirect('admin_login')
    
    try:
        account = Admin.objects.get(acc_id=acc_id)
        
        # CHECK: Only allow employee role accounts
        if account.role != 'employee':
            messages.error(request, f'{account.name} is not an employee account. Cannot add as employee.')
            return redirect('manage_accounts')
        
        # Check if account is approved
        if not account.is_approved:
            messages.error(request, 'Account must be approved first')
            return redirect('manage_accounts')
        
        # Check if employee record already exists
        if Employee.objects.filter(admin=account).exists():
            messages.error(request, f'Employee record already exists for {account.name}')
            return redirect('manage_accounts')
        
        # Create employee record
        Employee.objects.create(
            admin=account,
            employee_name=account.name,
            contact_value=account.email,
            contact_type='email',
            department=account.department,
            date_joined=date.today(),
            status='active'
        )
        
        messages.success(request, f'{account.name} has been added as an employee')
        return redirect('manage_accounts')
        
    except Admin.DoesNotExist:
        messages.error(request, 'Account not found')
        return redirect('manage_accounts')



def register(request):
    if request.method == 'POST':
        # Handle registration
        name = request.POST.get('name')
        email = request.POST.get('email')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        role = request.POST.get('role')
        department = request.POST.get('department')
        
        # Validation
        if not all([name, email, password, confirm_password, role]):
            messages.error(request, 'All fields are required')
            return HttpResponseRedirect(reverse('admin_login') + '?show=register')
            
        if password != confirm_password:
            messages.error(request, 'Passwords do not match')
            return HttpResponseRedirect(reverse('admin_login') + '?show=register')
            
        if len(password) < 6:
            messages.error(request, 'Password must be at least 6 characters')
            return HttpResponseRedirect(reverse('admin_login') + '?show=register')
            
        # Check if email already exists
        if Admin.objects.filter(email=email).exists():
            messages.error(request, 'Email already registered')
            return HttpResponseRedirect(reverse('admin_login') + '?show=register')
            
        # Create new account
        try:
            # For security, only allow employee role for self-registration
            allowed_roles = ['employee']  # Only employees can self-register
            
            if role not in allowed_roles:
                messages.error(request, 'Invalid role selection')
                return HttpResponseRedirect(reverse('admin_login') + '?show=register')
                
            # Create the admin account
            admin = Admin.objects.create(
                name=name,
                email=email,
                password=password,  # Note: In production, use proper password hashing!
                role=role,
                department=department if department else None,
                is_approved=False,  # Not approved yet
                is_active=True     # Active but pending approval
            )
            
            messages.success(request, f'Account created successfully! Please wait for administrator approval.')
            return HttpResponseRedirect(reverse('admin_login') + f'?email={email}')
            
        except IntegrityError as e:
            messages.error(request, 'Error creating account. Please try again.')
            return HttpResponseRedirect(reverse('admin_login') + '?show=register')
            
    return redirect('admin_login')


def pending_accounts(request):
    # Check if user is super admin
    if not request.session.get('acc_id'):
        messages.error(request, 'Please login first')
        return redirect('admin_login')
    
    if request.session.get('admin_role') != 'super_admin':
        messages.error(request, 'Access denied')
        return redirect('admin_login')
    
    # Get all pending accounts
    pending_accounts = Admin.objects.filter(is_approved=False, is_active=True)
    
    return render(request, 'liong/pending_accounts.html', {
        'pending_accounts': pending_accounts,
        'pending_count': pending_accounts.count()
    })


def approve_account(request, acc_id):
    # Check if user is super admin
    if not request.session.get('acc_id'):
        messages.error(request, 'Please login first')
        return redirect('admin_login')
    
    if request.session.get('admin_role') != 'super_admin':
        messages.error(request, 'Access denied')
        return redirect('admin_login')
    
    try:
        account = Admin.objects.get(acc_id=acc_id)
        
        if request.method == 'POST':
            action = request.POST.get('action')
            
            if action == 'approve':
                account.is_approved = True
                account.save()
                
                # REMOVED THE AUTO-EMPLOYEE CREATION
                # Just approve the account, don't create employee record
                
                messages.success(request, f'Account for {account.name} has been approved.')
                
                # Send notification to user (you can implement email notification here)
                
            elif action == 'reject':
                account.is_active = False  # Deactivate instead of deleting
                account.save()
                messages.success(request, f'Account for {account.name} has been rejected and deactivated.')
        
        return redirect('pending_accounts')
        
    except Admin.DoesNotExist:
        messages.error(request, 'Account not found')
        return redirect('pending_accounts')
    

def edit_my_account(request):
    """Allow users to edit their own account information"""
    if not request.session.get('acc_id'):
        messages.error(request, 'Please login first')
        return redirect('admin_login')
    
    try:
        # Get the logged-in user's account
        account = Admin.objects.get(acc_id=request.session.get('acc_id'))
        
        if request.method == 'POST':
            # Get form data
            name = request.POST.get('name')
            email = request.POST.get('email')
            current_password = request.POST.get('current_password')
            new_password = request.POST.get('new_password')
            confirm_password = request.POST.get('confirm_password')
            
            # Validation
            if not all([name, email]):
                messages.error(request, 'Name and email are required')
                return render(request, 'liong/edit_my_account.html', {'account': account})
            
            # Check if email already exists (excluding current account)
            if email != account.email and Admin.objects.filter(email=email).exists():
                messages.error(request, 'Email already registered to another account')
                return render(request, 'liong/edit_my_account.html', {'account': account})
            
            # Update basic info
            account.name = name
            account.email = email
            
            # Password change (optional)
            if current_password:
                # Verify current password
                if current_password != account.password:  # Note: In production, use proper password checking
                    messages.error(request, 'Current password is incorrect')
                    return render(request, 'liong/edit_my_account.html', {'account': account})
                
                if new_password and confirm_password:
                    if new_password != confirm_password:
                        messages.error(request, 'New passwords do not match')
                        return render(request, 'liong/edit_my_account.html', {'account': account})
                    
                    if len(new_password) < 6:
                        messages.error(request, 'Password must be at least 6 characters')
                        return render(request, 'liong/edit_my_account.html', {'account': account})
                    
                    account.password = new_password  # Note: Use proper hashing in production
                    messages.success(request, 'Password changed successfully')
            
            account.save()
            
            # Update session with new name
            request.session['admin_name'] = account.name
            
            messages.success(request, 'Your account information has been updated successfully')
            return redirect('edit_my_account')
        
        return render(request, 'liong/edit_my_account.html', {'account': account})
        
    except Admin.DoesNotExist:
        messages.error(request, 'Account not found')
        return redirect('admin_login')


def manage_accounts(request):
    """Integrated view for managing both accounts and employees"""
    # Check if user is super admin
    if not request.session.get('acc_id'):
        messages.error(request, 'Please login first')
        return redirect('admin_login')
    
    if request.session.get('admin_role') != 'super_admin':
        messages.error(request, 'Access denied')
        return redirect('admin_login')
    
    # Get all data
    accounts = Admin.objects.all().order_by('-created_at')
    employees = Employee.objects.all().select_related('admin')
    
    # Get unique departments for filter
    departments = Employee.objects.exclude(department__isnull=True).exclude(department='')\
        .values_list('department', flat=True).distinct()
    
    context = {
        'accounts': accounts,
        'employees': employees,
        'departments': departments,
        'total_accounts': accounts.count(),
        'active_accounts': accounts.filter(is_active=True).count(),
        'pending_count': accounts.filter(is_approved=False, is_active=True).count(),
        'employee_count': employees.count(),
    }
    
    return render(request, 'liong/manage_accounts.html', context)


def add_employee_account(request):
    """Create both account and employee record at once"""
    if not request.session.get('acc_id'):
        messages.error(request, 'Please login first')
        return redirect('admin_login')
    
    if request.session.get('admin_role') != 'super_admin':
        messages.error(request, 'Access denied')
        return redirect('admin_login')
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                # Get form data
                employee_name = request.POST.get('employee_name')
                email = request.POST.get('email')
                password = request.POST.get('password')
                confirm_password = request.POST.get('confirm_password')
                role = request.POST.get('role')
                contact_type = request.POST.get('contact_type', 'email')
                contact_value = request.POST.get('contact_value', email)
                position = request.POST.get('position', '')
                department = request.POST.get('department', '')
                date_joined = request.POST.get('date_joined')
                
                # Validation
                if not all([employee_name, email, password, confirm_password, role, date_joined]):
                    messages.error(request, 'All required fields must be filled')
                    return redirect('manage_accounts')
                
                if password != confirm_password:
                    messages.error(request, 'Passwords do not match')
                    return redirect('manage_accounts')
                
                if Admin.objects.filter(email=email).exists():
                    messages.error(request, 'Email already registered')
                    return redirect('manage_accounts')
                
                # Create account
                account = Admin.objects.create(
                    name=employee_name,
                    email=email,
                    password=password,  # Note: Use proper hashing in production
                    role=role,
                    department=department,
                    is_approved=True,  # Auto-approve when created by admin
                    is_active=True
                )
                
                # Create employee record
                Employee.objects.create(
                    admin=account,
                    employee_name=employee_name,
                    contact_type=contact_type,
                    contact_value=contact_value,
                    position=position,
                    department=department,
                    date_joined=date_joined,
                    status='active'
                )
                
                messages.success(request, f'Employee account created successfully for {employee_name}')
                return redirect('manage_accounts') + '?tab=employees'
                
        except IntegrityError as e:
            messages.error(request, f'Error creating account: {str(e)}')
            return redirect('manage_accounts')
    
    return redirect('manage_accounts')


def toggle_employee_status(request, employee_id):
    """Activate/deactivate employee"""
    if not request.session.get('acc_id'):
        messages.error(request, 'Please login first')
        return redirect('admin_login')
    
    if request.session.get('admin_role') != 'super_admin':
        messages.error(request, 'Access denied')
        return redirect('admin_login')
    
    try:
        employee = Employee.objects.get(employee_id=employee_id)
        
        if request.method == 'POST':
            action = request.POST.get('action')
            
            if action == 'deactivate':
                employee.status = 'inactive'
                employee.save()
                
                # Also deactivate the associated account
                if employee.admin:
                    employee.admin.is_active = False
                    employee.admin.save()
                    messages.success(request, f'Employee {employee.employee_name} and their account have been deactivated')
                else:
                    messages.success(request, f'Employee {employee.employee_name} has been deactivated')
                
            elif action == 'activate':
                employee.status = 'active'
                employee.save()
                
                # Activate the associated account
                if employee.admin:
                    employee.admin.is_active = True
                    employee.admin.save()
                    messages.success(request, f'Employee {employee.employee_name} and their account have been activated')
                else:
                    messages.success(request, f'Employee {employee.employee_name} has been activated')
        
        return redirect('manage_accounts') + '?tab=employees'
        
    except Employee.DoesNotExist:
        messages.error(request, 'Employee not found')
        return redirect('manage_accounts')

def toggle_account_status(request, acc_id):
    # Check if user is super admin
    if not request.session.get('acc_id'):
        messages.error(request, 'Please login first')
        return redirect('admin_login')
    
    if request.session.get('admin_role') != 'super_admin':
        messages.error(request, 'Access denied')
        return redirect('admin_login')
    
    try:
        account = Admin.objects.get(acc_id=acc_id)
        
        if account.acc_id == request.session.get('acc_id'):
            messages.error(request, 'You cannot deactivate your own account')
            return redirect('manage_accounts')
        
        if request.method == 'POST':
            action = request.POST.get('action')
            
            if action == 'deactivate':
                # Deactivate account
                account.is_active = False
                account.save()
                
                # Find and deactivate ALL associated employee records
                # Method 1: By direct foreign key
                employees_by_admin = Employee.objects.filter(admin=account)
                
                # Method 2: By email match (fallback)
                employees_by_email = Employee.objects.filter(contact_value=account.email)
                
                # Combine both
                all_employees = employees_by_admin | employees_by_email
                all_employees = all_employees.distinct()
                
                if all_employees.exists():
                    updated_count = all_employees.update(status='inactive')
                    messages.success(request, f'Account for {account.name} and {updated_count} employee record(s) have been deactivated.')
                else:
                    messages.success(request, f'Account for {account.name} has been deactivated.')
            
            elif action == 'activate':
                # Activate account
                account.is_active = True
                account.save()
                
                # Find and activate ALL associated employee records
                employees_by_admin = Employee.objects.filter(admin=account)
                employees_by_email = Employee.objects.filter(contact_value=account.email)
                
                all_employees = employees_by_admin | employees_by_email
                all_employees = all_employees.distinct()
                
                if all_employees.exists():
                    updated_count = all_employees.update(status='active')
                    messages.success(request, f'Account for {account.name} and {updated_count} employee record(s) have been activated.')
                else:
                    messages.success(request, f'Account for {account.name} has been activated.')
        
        return redirect('manage_accounts')
        
    except Admin.DoesNotExist:
        messages.error(request, 'Account not found')
        return redirect('manage_accounts')


def adminDashboard(request):
    # Check if user is logged in
    if not request.session.get('acc_id'):
        return redirect('admin_login')
    
    # Get user's role
    role = request.session.get('admin_role')
    
    # Prepare context based on role
    context = {
        'admin_name': request.session.get('admin_name'),
        'admin_role': role,
    }
    
    # Add super admin specific stats
    if role == 'super_admin':
        from .models import Admin
        context['total_accounts'] = Admin.objects.count()
        context['active_accounts'] = Admin.objects.filter(is_active=True).count()
        context['pending_count'] = Admin.objects.filter(is_approved=False, is_active=True).count()
    
    # Render dashboard
    return render(request, 'liong/adminDashboard.html', context)
    

def index(request):
    return render(request, "liong/index.html")



def normalRequest(request):
    return render(request, "liong/normalRequest.html")



def addEmployees(request):
    if 'acc_id' not in request.session:
        return redirect('admin_login')

    admin = Admin.objects.get(acc_id=request.session['acc_id'])

    if request.method == "POST":
        name = request.POST.get("employeeName")
        contact_type = request.POST.get("contactType")
        contact_value = request.POST.get("employeeContact")
        role = request.POST.get("employeeRole")
        date_joined = request.POST.get("employeeDate")

        role_in_db = request.POST.get("employeeRole") 
        # Create employee first
        employee = Employee.objects.create(
            admin=admin,  # This links the employee to the current admin
            employee_name=name,
            contact_type=contact_type,
            contact_value=contact_value,
            position=role_in_db,
            date_joined=date_joined,
            status='active'
        )

        # Only create admin account if we have valid credentials
        if contact_type == 'email' or (contact_type == 'phone' and '@' not in contact_value):
            # Check if login already exists
            if not Admin.objects.filter(email=contact_value).exists():
                default_password = get_random_string(length=8)
                
                admin_account = Admin.objects.create(
                    name=employee.employee_name,
                    email=contact_value,  # Use the contact value as email
                    password=default_password,
                    role=role_in_db,
                    department=employee.department
                )

                messages.success(
                    request,
                    f"Employee added successfully! Login: {contact_value}, Temp password: {default_password}"
                )
            else:
                messages.warning(
                    request,
                    f"Employee added but login already exists for: {contact_value}"
                )
        else:
            messages.success(request, "Employee added successfully! (No login account created)")

        return redirect("addEmployees")

    employees = Employee.objects.filter(admin=admin, status='active')
    return render(request, "liong/addEmployees.html", {"employees": employees})





def removeEmployee(request, employee_id):
    """Remove employee and their account"""
    if not request.session.get('acc_id'):
        messages.error(request, 'Please login first')
        return redirect('admin_login')
    
    if request.session.get('admin_role') != 'super_admin':
        messages.error(request, 'Access denied')
        return redirect('admin_login')
    
    try:
        employee = Employee.objects.get(employee_id=employee_id)
        employee_name = employee.employee_name
        
        # Delete associated account if exists
        if employee.admin:
            # Check if we're trying to delete our own account
            if employee.admin.acc_id == request.session.get('acc_id'):
                messages.error(request, 'You cannot delete your own account')
                return redirect('manage_accounts') + '?tab=employees'
            
            account_email = employee.admin.email
            employee.admin.delete()
            messages.success(request, f'Employee {employee_name} and their account ({account_email}) have been removed')
        else:
            employee.delete()
            messages.success(request, f'Employee {employee_name} has been removed')
        
    except Employee.DoesNotExist:
        messages.error(request, 'Employee not found')
    
    return redirect('manage_accounts') + '?tab=employees'







def request(request):
    if 'acc_id' not in request.session:
        return redirect('admin_login')

    current_admin = Admin.objects.get(acc_id=request.session['acc_id'])
    
    # Get products from stock_in (InventoryBalance)
    inventory_products = InventoryBalance.objects.select_related('product').all()
    
    products = []
    for inv in inventory_products:
        products.append({
            "product_id": inv.product.product_id,
            "name": inv.product.name,
            "unit": inv.unit,
            "available_qty": inv.quantity_unit
        })
    
    # Get employee
    employee = Employee.objects.filter(contact_value=current_admin.email).first()
    if employee:
        requisitions = Requisition.objects.filter(employee=employee).order_by('-date_requested')
    else:
        requisitions = Requisition.objects.none()

    # Handle POST (form submission)
    if request.method == "POST":
        product_ids = request.POST.getlist('product_id[]')
        quantities = request.POST.getlist('quantity[]')
        remarks = request.POST.get('remarks', '')
        
        if not employee:
            messages.error(request, "Employee record not found. Please contact administrator.")
            return redirect('request')
        
        try:
            with transaction.atomic():
                # Collect new items data
                new_items_data = []
                
                # Extract new items from form data
                for key in request.POST:
                    if key.startswith('new_items[') and '][name]' in key:
                        # Get the item ID from the key
                        item_id = key.split('[')[1].split(']')[0]
                        
                        item_name = request.POST.get(f'new_items[{item_id}][name]')
                        item_unit = request.POST.get(f'new_items[{item_id}][unit]')
                        item_quantity = request.POST.get(f'new_items[{item_id}][quantity]')
                        
                        if item_name and item_quantity and float(item_quantity) > 0:
                            new_items_data.append({
                                'name': item_name,
                                'unit': item_unit,
                                'quantity': item_quantity
                            })
                
                # Check if we have at least one item
                if not product_ids and not new_items_data:
                    messages.error(request, "Please select at least one product or add a new item.")
                    return redirect('request')
                
                # Create requisition (status will default to 'Pending Approval' from model)
                requisition = Requisition.objects.create(
                    employee=employee,
                    remarks=remarks
                    # date_requested will be auto-set by default CURRENT_TIMESTAMP
                    # status will be 'Pending Approval' from model default
                )
                
                # Process existing products from inventory
                for i, pid in enumerate(product_ids):
                    if pid and i < len(quantities):
                        qty = quantities[i]
                        if qty and float(qty) > 0:
                            try:
                                product = Products.objects.get(product_id=pid)
                                # Create requisition item
                                Requisition_Item.objects.create(
                                    requisition=requisition,
                                    product=product,
                                    quantity=qty
                                )
                            except Products.DoesNotExist:
                                messages.error(request, f"Product with ID {pid} not found.")
                                return redirect('request')
                
                # Process new items (not in inventory)
                for new_item in new_items_data:
                    # Create new product in products table
                    new_product = Products.objects.create(
                        name=new_item['name'],
                        unit=new_item['unit'],
                        stock=0  # Initial stock is 0 since it's a request
                    )
                    
                    # Create requisition item linking to the new product
                    Requisition_Item.objects.create(
                        requisition=requisition,
                        product=new_product,
                        quantity=new_item['quantity']
                    )
                
             
                # Success message
                success_msg = f"Requisition #{requisition.requisition_id} submitted successfully!"
                if new_items_data:
                    success_msg += f" {len(new_items_data)} new item(s) have been added to the catalog."
                
                messages.success(request, success_msg)
                return redirect('request')
                
        except Exception as e:
            messages.error(request, f"An error occurred while submitting the request: {str(e)}")
            return redirect('request')

    return render(request, "liong/request.html", {
        "products": products,
        "requisitions": requisitions,
        "today": timezone.now().date(),
        "current_user": current_admin
    })





def employeeDashboard(request):
    return render(request, "liong/employeeDashboard.html")




# ---------------------------------------------------------------
# ADMIN DASHBOARD - SIMPLE APPROVE/DENY ONLY (NO STOCK CHECK)
# ---------------------------------------------------------------
def requestApproval(request):
    """Admin view - shows all requisitions, only Approve/Deny actions"""
    if 'acc_id' not in request.session:
        return redirect('admin_login')

    current_admin = Admin.objects.get(acc_id=request.session['acc_id'])
    
    # For admin, show ALL requisitions
    requisitions = (
        Requisition.objects
        .select_related('employee')
        .prefetch_related('requisition_item_set__product')
        .order_by('-date_requested')
    )

    # Counts for admin dashboard
    status_counts = {
        'pending_approval': requisitions.filter(status='Pending Approval').count(),
        'partially_approved_pending_purchase': requisitions.filter(status='Partially Approved – Pending Purchase').count(),
        'pending_purchase': requisitions.filter(status='Pending Purchase').count(),
        'approved': requisitions.filter(status='Approved').count(),
        'denied': requisitions.filter(status='Denied').count(),
    }

    return render(request, "liong/requestApproval.html", {
        "requisitions": requisitions,
        "status_counts": status_counts,
        "current_admin": current_admin
    })


@require_POST
@transaction.atomic
def approve_requisition(request, requisition_id):
    """ADMIN ACTION: Simple approve - NO STOCK CHECK, always approves"""
    if 'acc_id' not in request.session:
        messages.error(request, "Please log in first.")
        return redirect('admin_login')

    current_admin = Admin.objects.get(acc_id=request.session['acc_id'])
    
    # Only super_admin can approve
    if current_admin.role != 'super_admin':
        messages.error(request, "You are not authorized to approve requisitions.")
        return redirect('requestApproval')

    requisition = get_object_or_404(Requisition, pk=requisition_id)
    
    # Can only approve Pending Approval requisitions
    if requisition.status != 'Pending Approval':
        messages.error(request, f"Requisition #{requisition.requisition_id} is already processed.")
        return redirect('requestApproval')

    old_status = requisition.status
    
    # ADMIN RULE: Always approve, NO stock check
    requisition.status = "Approved"
    
    # Set approved quantities equal to requested quantities
    items = Requisition_Item.objects.filter(requisition=requisition)
    for item in items:
        item.approved_quantity = item.quantity
        item.save()
    
    # DO NOT deduct from inventory here - inventory will handle that
    
    # Log status change
    log_status_change(requisition, old_status, requisition.status, request)
    requisition.save()

    messages.success(request, f"Requisition #{requisition.requisition_id} approved.")
    return redirect('requestApproval')


@require_POST
def deny_requisition(request, requisition_id):
    """ADMIN ACTION: Simple deny"""
    if 'acc_id' not in request.session:
        messages.error(request, "Please log in first.")
        return redirect('admin_login')

    current_admin = Admin.objects.get(acc_id=request.session['acc_id'])
    
    # Only super_admin can deny
    if current_admin.role != 'super_admin':
        messages.error(request, "You are not authorized to deny requisitions.")
        return redirect('requestApproval')

    requisition = get_object_or_404(Requisition, pk=requisition_id)
    
    # Can only deny Pending Approval requisitions
    if requisition.status != 'Pending Approval':
        messages.error(request, f"Requisition #{requisition.requisition_id} is already processed.")
        return redirect('requestApproval')

    old_status = requisition.status
    requisition.status = "Denied"
    requisition.save()

    # Log status change
    log_status_change(requisition, old_status, requisition.status, request)

    messages.success(request, f"Requisition #{requisition.requisition_id} denied.")
    return redirect('requestApproval')


def admin_requisition_view(request, req_id):
    """ADMIN VIEW: Modal for admin dashboard (simple view)"""
    req = get_object_or_404(Requisition, pk=req_id)
    items = Requisition_Item.objects.filter(requisition=req).select_related('product')

    # Show items without stock check
    for item in items:
        item.requested_qty = item.quantity

    return render(request, "liong/partials/admin_requisition_modal.html", {
        "req": req,
        "items": items
    })


# ---------------------------------------------------------------
# INVENTORY DASHBOARD - HANDLES STOCK MANAGEMENT
# ---------------------------------------------------------------
def inventory_approved_requisitions(request):
    """Inventory view - shows ONLY approved requisitions for stock management"""
    if 'acc_id' not in request.session:
        return redirect('admin_login')

    current_admin = Admin.objects.get(acc_id=request.session['acc_id'])

    # Inventory sees ONLY approved requisitions
    requisitions = (
        Requisition.objects
        .filter(status='Approved')  # ONLY approved ones
        .select_related('employee')
        .prefetch_related('requisition_item_set__product')
        .order_by('-date_requested')
    )

    return render(request, "liong/inventory_approved_requisitions.html", {
        "requisitions": requisitions,
        "current_admin": current_admin
    })


@require_POST
@transaction.atomic
def inventory_partial_approve(request, requisition_id):
    """INVENTORY ACTION: Check stock and approve partially if needed"""
    if 'acc_id' not in request.session:
        messages.error(request, "Please log in first.")
        return redirect('admin_login')

    current_admin = Admin.objects.get(acc_id=request.session['acc_id'])
    
    # Only super_admin (acting as inventory) can do this
    if current_admin.role != 'super_admin':
        messages.error(request, "You are not authorized for inventory actions.")
        return redirect('inventory_approved_requisitions')

    requisition = get_object_or_404(Requisition, pk=requisition_id)
    
    # Can only process Approved requisitions
    if requisition.status != 'Approved':
        messages.error(request, f"Requisition #{requisition.requisition_id} is not approved.")
        return redirect('inventory_approved_requisitions')

    old_status = requisition.status
    items = Requisition_Item.objects.filter(requisition=requisition).select_related('product')
    partial = False
    recommendation = ""
    total_deducted = 0

    for item in items:
        product = item.product
        requested_qty = item.quantity

        # Get inventory
        try:
            inv_balance = InventoryBalance.objects.get(product=product)
            available_stock = inv_balance.quantity_unit
        except InventoryBalance.DoesNotExist:
            available_stock = 0

        if available_stock <= 0:
            # No stock at all
            partial = True
            item.approved_quantity = 0  # Can't give any
            recommendation += f"{product.name}: No stock available. Need to purchase {requested_qty}. "
        
        elif requested_qty > available_stock:
            # Partial stock available
            partial = True
            item.approved_quantity = available_stock  # Give what we have
            remaining = requested_qty - available_stock
            recommendation += f"{product.name}: Only {available_stock} available. Need to purchase {remaining}. "
            
            # Deduct available stock
            inv_balance.quantity_unit = 0
            inv_balance.save()
            total_deducted += available_stock
        
        else:
            # Full stock available
            item.approved_quantity = requested_qty  # Give full amount
            
            # Deduct from inventory
            inv_balance.quantity_unit -= requested_qty
            inv_balance.save()
            total_deducted += requested_qty

        item.save()

    # Update requisition status based on inventory check
    if partial:
        requisition.status = "Partially Approved – Pending Purchase"
        requisition.recommendation = recommendation
        messages.warning(request, f"Requisition #{requisition.requisition_id} partially fulfilled. Stock deducted: {total_deducted}. Purchase needed.")
    else:
        # Fully fulfilled from stock
        requisition.status = "Approved"  # Still approved, but now fulfilled
        messages.success(request, f"Requisition #{requisition.requisition_id} fully fulfilled from stock. Total deducted: {total_deducted}.")

    # Log status change
    log_status_change(requisition, old_status, requisition.status, request)
    requisition.save()

    return redirect('inventory_approved_requisitions')


@require_POST
@transaction.atomic
def inventory_fulfill_from_stock(request, requisition_id):
    """INVENTORY ACTION: Try to fulfill from available stock"""
    if 'acc_id' not in request.session:
        messages.error(request, "Please log in first.")
        return redirect('admin_login')

    current_admin = Admin.objects.get(acc_id=request.session['acc_id'])
    
    if current_admin.role != 'super_admin':
        messages.error(request, "You are not authorized for inventory actions.")
        return redirect('inventory_approved_requisitions')

    requisition = get_object_or_404(Requisition, pk=requisition_id)
    
    # Can only process approved or partially approved requisitions
    if requisition.status not in ['Approved', 'Partially Approved – Pending Purchase']:
        messages.error(request, f"Requisition #{requisition.requisition_id} cannot be fulfilled.")
        return redirect('inventory_approved_requisitions')

    old_status = requisition.status
    items = Requisition_Item.objects.filter(requisition=requisition).select_related('product')
    can_fully_fulfill = True
    total_deducted = 0

    # First check if we can fully fulfill
    for item in items:
        try:
            inv_balance = InventoryBalance.objects.get(product=item.product)
            if inv_balance.quantity_unit < item.quantity:
                can_fully_fulfill = False
                break
        except InventoryBalance.DoesNotExist:
            can_fully_fulfill = False
            break

    if can_fully_fulfill:
        # Fully fulfill from stock
        for item in items:
            inv_balance = InventoryBalance.objects.get(product=item.product)
            inv_balance.quantity_unit -= item.quantity
            inv_balance.save()
            total_deducted += item.quantity
            item.approved_quantity = item.quantity
            item.save()
        
        requisition.status = "Approved"
        messages.success(request, f"Requisition #{requisition.requisition_id} fully fulfilled from stock. Total deducted: {total_deducted}.")
    else:
        # Mark for purchase
        requisition.status = "Pending Purchase"
        messages.info(request, f"Requisition #{requisition.requisition_id} marked for purchase (insufficient stock).")

    # Log status change
    log_status_change(requisition, old_status, requisition.status, request)
    requisition.save()

    return redirect('inventory_approved_requisitions')


def inventory_requisition_view(request, req_id):
    """INVENTORY VIEW: Modal for inventory dashboard (detailed view with stock info)"""
    req = get_object_or_404(Requisition, pk=req_id)
    items = Requisition_Item.objects.filter(requisition=req).select_related('product')

    # Get approval history
    approval_history = RequisitionStatusHistory.objects.filter(
        requisition=req
    ).order_by('-changed_at')

    # Check inventory balance with details
    for item in items:
        try:
            bal = InventoryBalance.objects.get(product=item.product)
            item.available_qty = bal.quantity_unit
            item.has_stock = bal.quantity_unit >= item.quantity
            item.shortage = max(0, item.quantity - bal.quantity_unit)
        except:
            item.available_qty = 0
            item.has_stock = False
            item.shortage = item.quantity

    return render(request, "liong/partials/inventory_requisition_modal.html", {
        "req": req,
        "items": items,
        "approval_history": approval_history
    })


# ---------------------------------------------------------------
# SHARED FUNCTIONS
# ---------------------------------------------------------------
def log_status_change(req, old_status, new_status, request):
    """Shared function to log status changes"""
    try:
        admin_id = request.session.get('acc_id')
        if not admin_id:
            print("No admin_id in session")
            return
            
        admin_user = Admin.objects.get(pk=admin_id)
        
        RequisitionStatusHistory.objects.create(
            requisition=req,
            old_status=old_status,
            new_status=new_status,
            changed_by=admin_user
        )
        print(f"Status change logged: {old_status} -> {new_status} for requisition {req.requisition_id}")
        
    except Admin.DoesNotExist:
        print(f"Admin with id {admin_id} does not exist")
    except Exception as e:
        print(f"Error logging status change: {str(e)}")





































def inventory_dashboard(request):
    # Only inventory admins can access
    if request.session.get('admin_role') != 'inventory_admin':
        return redirect('admin_login')

    # Fetch all inventory balances with totals
    balances = InventoryBalance.objects.select_related('product').all()

    # Calculate analytics
    total_products = balances.count()
    low_stock_count = 0
    out_of_stock_count = 0
    healthy_stock_count = 0
    
    low_stock_products = []
    
    for b in balances:
        # Calculate current quantity
        b.current_quantity = b.quantity_unit or 0
        b.min_stock = b.min_stock or 0
        
        # Calculate deficit
        b.deficit = max(0, b.min_stock - b.current_quantity) if b.min_stock > 0 else 0
        
        # Categorize stock status
        if b.current_quantity == 0:
            out_of_stock_count += 1
            low_stock_products.append(b)
        elif b.current_quantity <= b.min_stock:
            low_stock_count += 1
            low_stock_products.append(b)
        else:
            healthy_stock_count += 1

    # Get recent activity (last 10 stock in/out records)
    recent_stock_in = StockIn.objects.select_related('product').order_by('-date_in')[:5]
    recent_stock_out = StockOut.objects.select_related('product').order_by('-date_out')[:5]
    
    recent_activity = []
    
    for stock_in in recent_stock_in:
        recent_activity.append({
            'type': 'in',
            'description': f'Stock in: {stock_in.product.name}',
            'quantity': f'+{stock_in.quantity}',
            'timestamp': stock_in.date_in
        })
    
    for stock_out in recent_stock_out:
        recent_activity.append({
            'type': 'out',
            'description': f'Stock out: {stock_out.product.name}',
            'quantity': f'-{stock_out.quantity}',
            'timestamp': stock_out.date_out
        })
    
    # Sort by timestamp (most recent first)
    recent_activity.sort(key=lambda x: x['timestamp'], reverse=True)
    recent_activity = recent_activity[:5]

    return render(request, 'liong/inventory_dashboard.html', {
        'total_products': total_products,
        'low_stock_count': low_stock_count,
        'out_of_stock_count': out_of_stock_count,
        'healthy_stock_count': healthy_stock_count,
        'low_stock_products': low_stock_products,
        'recent_activity': recent_activity
    })


# Add this function to views.py
@transaction.atomic
def create_purchase_request_from_balance(request):
    """Create purchase request directly from inventory balance"""
    if 'acc_id' not in request.session:
        messages.error(request, "Please log in first.")
        return redirect('admin_login')

    current_admin = Admin.objects.get(acc_id=request.session['acc_id'])
    
    if current_admin.role not in ['inventory_admin', 'super_admin']:
        messages.error(request, "Only inventory can create purchase requests.")
        return redirect('inventory_dashboard')

    if request.method == 'POST':
        product_id = request.POST.get('product_id')
        quantity = request.POST.get('quantity')
        estimated_unit_price = request.POST.get('estimated_unit_price', 0)
        remarks = request.POST.get('remarks', '')
        
        if not product_id or not quantity:
            messages.error(request, "Product and quantity are required.")
            return redirect('inventory_dashboard')
        
        try:
            product = Products.objects.get(pk=product_id)
            
            # Create a temporary requisition for this purchase request
            # In a real scenario, you might want to create a proper requisition
            # For now, we'll create a purchase request without a requisition
            
            # Calculate total estimated cost
            total_estimated = Decimal(quantity) * Decimal(estimated_unit_price)
            
            # Create purchase request
            purchase_request = PurchaseRequest.objects.create(
                requested_by=current_admin,
                payment_method='cash_on_delivery',  # Default
                remarks=f"Manual purchase request from inventory balance.\nProduct: {product.name}\nQuantity: {quantity} {product.unit}\n{remarks}",
                total_estimated_cost=total_estimated
            )
            
            # Create purchase request item
            PurchaseRequestItem.objects.create(
                request=purchase_request,
                product=product,
                quantity_to_purchase=quantity,
                estimated_unit_price=estimated_unit_price
            )
            
            messages.success(request, f"Purchase request PR-{purchase_request.request_id} created for {product.name}.")
            return redirect('inventory_dashboard')
            
        except Products.DoesNotExist:
            messages.error(request, "Product not found.")
            return redirect('inventory_dashboard')
        except Exception as e:
            messages.error(request, f"Error creating purchase request: {str(e)}")
            return redirect('inventory_dashboard')
    
    return redirect('inventory_dashboard')


def balance(request):
    if request.session.get('admin_role') != 'inventory_admin':
        return redirect('admin_login')

    balances = InventoryBalance.objects.select_related('product').all()
    suppliers = Supplier.objects.filter(status='active')
    
    # Calculate statistics
    total_products = balances.count()
    low_stock_count = 0
    in_stock_count = 0
    out_of_stock_count = 0
    
    for balance in balances:
        if balance.quantity_unit <= 0:
            out_of_stock_count += 1
        elif balance.min_stock > 0 and balance.quantity_unit < balance.min_stock:
            low_stock_count += 1
        elif balance.min_stock > 0 and balance.quantity_unit >= balance.min_stock:
            in_stock_count += 1
        else:
            in_stock_count += 1
    
    # Add deficit calculation to each balance
    for balance in balances:
        if balance.min_stock > 0:
            balance.deficit = max(0, balance.min_stock - balance.quantity_unit)
        else:
            balance.deficit = 0
    
    return render(request, 'liong/balance.html', {
        'balances': balances,
        'suppliers': suppliers,  # Add this line
        'total_products': total_products,
        'low_stock_count': low_stock_count,
        'in_stock_count': in_stock_count,
        'out_of_stock_count': out_of_stock_count
    })

# -------------------------
# STOCK IN
# -------------------------
def stock_in_view(request):
    if request.session.get('admin_role') != 'inventory_admin':
        return redirect('admin_login')

    products = Products.objects.all()

    if request.method == 'POST':
        product_id = request.POST.get('product')
        quantity = request.POST.get('quantity') or 0
        quantity_meters = request.POST.get('quantity_meters') or 0
        quantity_klg = request.POST.get('quantity_klg') or 0
        date_in = request.POST.get('date_in') or date.today()

        # Validate - removed unit check since it comes from product
        if not product_id:
            messages.error(request, "Please select a product.")
            return redirect('stock_in')

        try:
            product = Products.objects.get(pk=product_id)
            unit = product.unit  # Get unit from the product itself
        except Products.DoesNotExist:
            messages.error(request, "Product not found.")
            return redirect('stock_in')

        admin = Admin.objects.get(pk=request.session.get('acc_id'))

        # Create StockIn record
        StockIn.objects.create(
            product=product,
            unit=unit,  # Use the unit from the product
            quantity=float(quantity),
            quantity_meters=float(quantity_meters),
            quantity_klg=float(quantity_klg),
            date_in=date_in,
            acc=admin
        )

        # Update InventoryBalance
        balance, created = InventoryBalance.objects.get_or_create(
            product=product,
            defaults={
                'unit': unit,  # Use the unit from the product
                'quantity_unit': 0,
                'quantity_meters': 0,
                'quantity_klg': 0
            }
        )

        balance.quantity_unit = (balance.quantity_unit or 0) + float(quantity)
        balance.quantity_meters = (balance.quantity_meters or 0) + float(quantity_meters)
        balance.quantity_klg = (balance.quantity_klg or 0) + float(quantity_klg)
        balance.last_updated = timezone.now()
        balance.save()

        messages.success(request, f"{quantity} {unit} added to {product.name}.")
        return redirect('stock_in')

    return render(request, 'liong/stock_in.html', {'products': products})   


# -------------------------
# ADD PRODUCT
# -------------------------
def add_product(request):
    if request.method == 'POST':
        item_name = request.POST.get('item_name')
        unit = request.POST.get('unit')

        if not item_name or not unit:
            messages.error(request, "Please enter product name and select unit.")
            return redirect('stock_in')

        Products.objects.create(name=item_name, unit=unit)
        messages.success(request, f'Product "{item_name}" added successfully!')
        return redirect('stock_in')

    # If GET request (shouldn't happen from modal)
    return redirect('stock_in')
    

# -------------------------
# STOCK OUT
# -------------------------
from decimal import Decimal

def stock_out_view(request):
    if request.session.get('admin_role') != 'inventory_admin':
        return redirect('admin_login')

    # Get the current admin OBJECT
    current_admin = Admin.objects.get(acc_id=request.session.get("acc_id"))
    
    # Fetch all products with inventory balance
    balances = InventoryBalance.objects.select_related('product').all()
    
    # Prepare product data for JS
    products = {}
    for b in balances:
        products[str(b.product.product_id)] = {
            'item_name': b.product.name,
            'unit_type': b.unit,
            'quantity_unit': float(b.quantity_unit),
            'quantity_meters': float(b.quantity_meters),
            'quantity_klg': float(b.quantity_klg)
        }

    if request.method == "POST":
        try:
            product_id = int(request.POST.get("product") or 0)
        except ValueError:
            messages.error(request, "Invalid product selected.")
            return redirect("stock_out")

        # Convert form values to Decimal
        qty_unit = Decimal(request.POST.get("quantity") or 0)
        qty_meters = Decimal(request.POST.get("quantity_meters") or 0)
        qty_klg = Decimal(request.POST.get("quantity_klg") or 0)
        date_out = request.POST.get("date_out") or timezone.now().date()

        try:
            balance = InventoryBalance.objects.get(product_id=product_id)
            unit_type = balance.unit  # Get unit from inventory balance
        except InventoryBalance.DoesNotExist:
            messages.error(request, "Product does not exist in inventory balance.")
            return redirect("stock_out")

        # Check stock availability
        if qty_unit > balance.quantity_unit or \
           qty_meters > balance.quantity_meters or \
           qty_klg > balance.quantity_klg:
            messages.error(request, "Not enough stock available!")
            return redirect("stock_out")

        # Deduct stock using Decimal operations
        balance.quantity_unit -= qty_unit
        balance.quantity_meters -= qty_meters
        balance.quantity_klg -= qty_klg
        balance.save()

        # Save stock-out record - PASS THE ADMIN OBJECT, NOT ID
        StockOut.objects.create(
            product_id=product_id,
            unit=unit_type,
            quantity=qty_unit,
            quantity_meters=qty_meters,
            quantity_klg=qty_klg,
            date_out=date_out,
            acc=current_admin  # Pass the Admin object instance
        )

        messages.success(request, "Stock-out recorded successfully!")
        return redirect("stock_out")

    # Recent stock out
    recent_stock_out = StockOut.objects.select_related('product').order_by('-stock_out_id')[:10]

    return render(request, "liong/stock_out.html", {
        "products": balances,  # use balances for <select> options
        "products_json": products,  # for JS
        "recent_stock_out": recent_stock_out,
        "current_admin": current_admin  # Pass admin object to template if needed
    })


# -------------------------
# BALANCE
# -------------------------
def balance(request):
    if request.session.get('admin_role') != 'inventory_admin':
        return redirect('admin_login')

    balances = InventoryBalance.objects.select_related('product').all()
    return render(request, 'liong/balance.html', {'balances': balances})


# -------------------------
# LOGOUT
# -------------------------
def admin_logout(request):
    request.session.flush()
    return redirect('admin_login')






















# Add these functions to your views.py

# ============================================
# INVENTORY: Create Purchase Request
# ============================================
from django.db import connection

@transaction.atomic
def create_purchase_request(request, requisition_id):
    """Inventory creates purchase request for shortages"""
    if 'acc_id' not in request.session:
        messages.error(request, "Please log in first.")
        return redirect('admin_login')

    current_admin = Admin.objects.get(acc_id=request.session['acc_id'])
    
    if current_admin.role not in ['inventory_admin', 'super_admin']:
        messages.error(request, "Only inventory can create purchase requests.")
        return redirect('inventory_approved_requisitions')

    requisition = get_object_or_404(Requisition, pk=requisition_id)
    
    # Check if already has purchase request
    existing_request = PurchaseRequest.objects.filter(
        requisition=requisition,
        status__in=['pending', 'approved']
    ).first()
    
    if existing_request:
        messages.info(request, f"Purchase request already exists: PR-{existing_request.request_id}")
        return redirect('inventory_approved_requisitions')

    # Get items with shortages
    items = Requisition_Item.objects.filter(requisition=requisition).select_related('product')
    shortage_items = []
    
    for item in items:
        try:
            inv_balance = InventoryBalance.objects.get(product=item.product)
            available = inv_balance.quantity_unit
            shortage = max(0, item.quantity - available)
            
            if shortage > 0:
                shortage_items.append({
                    'item': item,
                    'quantity': shortage,
                    'product': item.product
                })
        except InventoryBalance.DoesNotExist:
            shortage = item.quantity
            shortage_items.append({
                'item': item,
                'quantity': shortage,
                'product': item.product
            })

    if not shortage_items:
        messages.warning(request, "No shortages found for purchase.")
        return redirect('inventory_approved_requisitions')

    # If GET request, show the form
    if request.method == 'GET':
        return render(request, 'liong/create_purchase_request_form.html', {
            'requisition': requisition,
            'shortage_items': shortage_items,
            'current_admin': current_admin
        })
    
    # If POST request, process the form
    elif request.method == 'POST':
        payment_method = request.POST.get('payment_method', 'cash_on_delivery')
        remarks = request.POST.get('remarks', '')
        custom_payment = request.POST.get('custom_payment', '')

# If custom payment is specified, use it
        if custom_payment and payment_method == 'custom':
            payment_method = custom_payment
        
        # Create purchase request
        purchase_request = PurchaseRequest.objects.create(
            requisition=requisition,
            requested_by=current_admin,
            payment_method=payment_method,
            remarks=f"Auto-generated from shortages in Requisition #{requisition.requisition_id}\n{remarks}"
        )

        # Create purchase request items with prices
        total_estimated_cost = 0
        for item_data in shortage_items:
            price_key = f'price_{item_data["item"].id}'
            estimated_price = request.POST.get(price_key, 0)
            
            if estimated_price:
                estimated_price = Decimal(estimated_price)
            else:
                estimated_price = Decimal('0')
            
            item = PurchaseRequestItem.objects.create(
                request=purchase_request,
                requisition_item=item_data['item'],
                product=item_data['product'],
                quantity_to_purchase=item_data['quantity'],
                estimated_unit_price=estimated_price
            )
            
            total_estimated_cost += item.total_estimated_price

        # Update total cost
        purchase_request.total_estimated_cost = total_estimated_cost
        purchase_request.save()

        # Update requisition status
        requisition.status = "Pending Purchase"
        requisition.save()

        messages.success(request, f"Purchase request PR-{purchase_request.request_id} created successfully.")
        return redirect('inventory_approved_requisitions')

# ============================================
# SUPER ADMIN: Approve/Deny Purchase Request
# ============================================
def purchase_requests_list(request):
    """Super Admin: List all purchase requests for approval"""
    if 'acc_id' not in request.session:
        return redirect('admin_login')

    current_admin = Admin.objects.get(acc_id=request.session['acc_id'])
    
    if current_admin.role != 'super_admin':
        messages.error(request, "Only super admin can approve purchase requests.")
        return redirect('requestApproval')

    purchase_requests = PurchaseRequest.objects.filter(
        status='pending'
    ).select_related('requisition', 'requested_by').prefetch_related(
        'purchaserequestitem_set__product'
    ).order_by('-request_date')

    return render(request, 'liong/purchase_requests.html', {
        'purchase_requests': purchase_requests,
        'current_admin': current_admin
    })


@require_POST
@transaction.atomic
def approve_purchase_request(request, request_id):
    """Super Admin approves purchase request"""
    if 'acc_id' not in request.session:
        messages.error(request, "Please log in first.")
        return redirect('admin_login')

    current_admin = Admin.objects.get(acc_id=request.session['acc_id'])
    
    if current_admin.role != 'super_admin':
        messages.error(request, "Only super admin can approve purchase requests.")
        return redirect('purchase_requests_list')

    purchase_request = get_object_or_404(PurchaseRequest, pk=request_id)
    
    if purchase_request.status != 'pending':
        messages.error(request, "Purchase request is already processed.")
        return redirect('purchase_requests_list')

    # Update purchase request
    purchase_request.status = 'approved'
    purchase_request.approved_by = current_admin
    purchase_request.approval_date = timezone.now()
    purchase_request.save()

    messages.success(request, f"Purchase request PR-{purchase_request.request_id} approved.")
    return redirect('purchase_requests_list')


@require_POST
@transaction.atomic
def deny_purchase_request(request, request_id):
    """Super Admin denies purchase request"""
    if 'acc_id' not in request.session:
        messages.error(request, "Please log in first.")
        return redirect('admin_login')

    current_admin = Admin.objects.get(acc_id=request.session['acc_id'])
    
    if current_admin.role != 'super_admin':
        messages.error(request, "Only super admin can deny purchase requests.")
        return redirect('purchase_requests_list')

    purchase_request = get_object_or_404(PurchaseRequest, pk=request_id)
    
    if purchase_request.status != 'pending':
        messages.error(request, "Purchase request is already processed.")
        return redirect('purchase_requests_list')

    denial_reason = request.POST.get('denial_reason', '')
    
    # Update purchase request
    purchase_request.status = 'denied'
    purchase_request.denial_reason = denial_reason
    purchase_request.save()

    # Revert requisition status
    requisition = purchase_request.requisition
    requisition.status = "Approved"  # Back to approved for inventory to re-check
    requisition.save()

    messages.success(request, f"Purchase request PR-{purchase_request.request_id} denied.")
    return redirect('purchase_requests_list')


# ============================================
# INVENTORY: Create Purchase Order
# ============================================
def approved_purchase_requests(request):
    """Inventory: View approved purchase requests to create POs"""
    if 'acc_id' not in request.session:
        return redirect('admin_login')

    current_admin = Admin.objects.get(acc_id=request.session['acc_id'])
    
    if current_admin.role not in ['inventory_admin', 'super_admin']:
        messages.error(request, "Only inventory can create purchase orders.")
        return redirect('inventory_approved_requisitions')

    approved_requests = PurchaseRequest.objects.filter(
        status='approved',
        purchaseorder__isnull=True  # Not yet converted to PO
    ).select_related('requisition', 'approved_by').prefetch_related(
        'purchaserequestitem_set__product'
    ).order_by('-approval_date')

    suppliers = Supplier.objects.filter(status='active')

    return render(request, 'liong/create_purchase_order.html', {
        'approved_requests': approved_requests,
        'suppliers': suppliers,
        'current_admin': current_admin
    })


@transaction.atomic
def create_purchase_order(request, request_id):
    """Inventory creates purchase order from approved request"""
    if 'acc_id' not in request.session:
        messages.error(request, "Please log in first.")
        return redirect('admin_login')

    current_admin = Admin.objects.get(acc_id=request.session['acc_id'])
    
    if current_admin.role not in ['inventory_admin', 'super_admin']:
        messages.error(request, "Only inventory can create purchase orders.")
        return redirect('approved_purchase_requests')

    purchase_request = get_object_or_404(PurchaseRequest, pk=request_id)
    
    if purchase_request.status != 'approved':
        messages.error(request, "Purchase request must be approved first.")
        return redirect('approved_purchase_requests')

    if request.method == 'POST':
        supplier_id = request.POST.get('supplier')
        delivery_date = request.POST.get('delivery_date')
        payment_terms = request.POST.get('payment_terms', 'Net 30')
        notes = request.POST.get('notes', '')
        
        if not supplier_id:
            messages.error(request, "Please select a supplier.")
            return redirect('approved_purchase_requests')

        supplier = get_object_or_404(Supplier, pk=supplier_id)
        
        # Create purchase order
        purchase_order = PurchaseOrder.objects.create(
            request=purchase_request,
            supplier=supplier,
            created_by=current_admin,
            delivery_date=delivery_date,
            payment_terms=payment_terms,
            notes=notes
        )
        
        # Get items from purchase request
        request_items = PurchaseRequestItem.objects.filter(request=purchase_request)
        
        for req_item in request_items:
            unit_price = request.POST.get(f'unit_price_{req_item.item_id}', 0)
            
            # Create PO item
            PurchaseOrderItem.objects.create(
                po=purchase_order,
                product=req_item.product,
                quantity=req_item.quantity_to_purchase,
                unit_price=unit_price
            )
            
            # Update requisition_item purchase_qty
            if req_item.requisition_item:
                req_item.requisition_item.purchase_qty = req_item.quantity_to_purchase
                req_item.requisition_item.save()

        messages.success(request, f"Purchase order {purchase_order.po_number} created successfully.")
        return redirect('purchase_orders_list')
    
    return redirect('approved_purchase_requests')


# ============================================
# PURCHASE ORDER MANAGEMENT
# ============================================
def purchase_orders_list(request):
    """List all purchase orders"""
    if 'acc_id' not in request.session:
        return redirect('admin_login')

    current_admin = Admin.objects.get(acc_id=request.session['acc_id'])
    
    purchase_orders = PurchaseOrder.objects.select_related(
        'supplier', 'created_by', 'request__requisition'
    ).prefetch_related('purchaseorderitem_set').order_by('-created_date')

    return render(request, 'liong/purchase_orders.html', {
        'purchase_orders': purchase_orders,
        'current_admin': current_admin
    })


@require_POST
@transaction.atomic
def send_purchase_order(request, po_id):
    """Mark PO as sent to supplier"""
    if 'acc_id' not in request.session:
        messages.error(request, "Please log in first.")
        return redirect('admin_login')

    current_admin = Admin.objects.get(acc_id=request.session['acc_id'])
    
    if current_admin.role not in ['inventory_admin', 'super_admin']:
        messages.error(request, "Only inventory can send purchase orders.")
        return redirect('purchase_orders_list')

    purchase_order = get_object_or_404(PurchaseOrder, pk=po_id)
    
    if purchase_order.status != 'draft':
        messages.error(request, "Only draft POs can be sent.")
        return redirect('purchase_orders_list')

    purchase_order.status = 'sent'
    purchase_order.sent_date = timezone.now()
    purchase_order.save()
    
    # Create history
    PurchaseOrderHistory.objects.create(
        po=purchase_order,
        old_status='draft',
        new_status='sent',
        changed_by=current_admin,
        notes="Sent to supplier"
    )

    messages.success(request, f"Purchase order {purchase_order.po_number} sent to supplier.")
    return redirect('purchase_orders_list')


# ============================================
# RECEIVING & QUALITY CHECK
# ============================================
def receive_purchase_order(request, po_id):
    """Receive goods from supplier with quality check"""
    if 'acc_id' not in request.session:
        return redirect('admin_login')

    current_admin = Admin.objects.get(acc_id=request.session['acc_id'])
    
    if current_admin.role not in ['inventory_admin', 'super_admin']:
        messages.error(request, "Only inventory can receive goods.")
        return redirect('purchase_orders_list')

    purchase_order = get_object_or_404(PurchaseOrder.objects.select_related(
        'supplier'
    ).prefetch_related(
        'purchaseorderitem_set__product'
    ), pk=po_id)

    if request.method == 'POST':
        # Create receiving record
        receiving = PurchaseReceiving.objects.create(
            po=purchase_order,
            received_by=current_admin,
            invoice_number=request.POST.get('invoice_number'),
            delivery_note_number=request.POST.get('delivery_note_number'),
            carrier=request.POST.get('carrier'),
            quality_check_notes=request.POST.get('quality_check_notes')
        )
        
        all_accepted = True
        any_received = False
        
        # Process each item
        for item in purchase_order.purchaseorderitem_set.all():
            received_qty = Decimal(request.POST.get(f'received_qty_{item.po_item_id}', 0))
            accepted_qty = Decimal(request.POST.get(f'accepted_qty_{item.po_item_id}', 0))
            
            if received_qty > 0:
                any_received = True
                
                # Create received item record
                ReceivedItem.objects.create(
                    receiving=receiving,
                    po_item=item,
                    quantity_received=received_qty,
                    quantity_accepted=accepted_qty,
                    quantity_rejected=received_qty - accepted_qty,
                    rejection_reason=request.POST.get(f'rejection_reason_{item.po_item_id}', ''),
                    quality_checker=current_admin,
                    quality_check_date=timezone.now()
                )
                
                # Update PO item
                item.received_quantity += accepted_qty
                
                if accepted_qty < received_qty:
                    item.quality_status = 'partial'
                elif accepted_qty == received_qty:
                    item.quality_status = 'passed'
                else:
                    item.quality_status = 'failed'
                
                item.save()
                
                if accepted_qty < item.quantity:
                    all_accepted = False
        
        # Update receiving status
        if any_received:
            if all_accepted and all(item.received_quantity >= item.quantity for item in purchase_order.purchaseorderitem_set.all()):
                receiving.overall_status = 'accepted'
                purchase_order.status = 'received'
                purchase_order.completed_date = timezone.now()
                
                # Auto stock in accepted items
                stock_in_accepted_items(purchase_order, current_admin)
            else:
                receiving.overall_status = 'partial'
                purchase_order.status = 'partially_received'
        else:
            receiving.overall_status = 'rejected'
        
        receiving.save()
        purchase_order.save()
        
        # Create history
        PurchaseOrderHistory.objects.create(
            po=purchase_order,
            old_status='sent',
            new_status=purchase_order.status,
            changed_by=current_admin,
            notes="Goods received with quality check"
        )
        
        messages.success(request, f"Goods received for {purchase_order.po_number}")
        return redirect('purchase_orders_list')

    return render(request, 'liong/receive_purchase_order.html', {
        'purchase_order': purchase_order,
        'current_admin': current_admin
    })


@transaction.atomic
def stock_in_accepted_items(purchase_order, admin):
    """Stock in accepted items to inventory"""
    for item in purchase_order.purchaseorderitem_set.all():
        if item.quality_status in ['passed', 'partial'] and item.received_quantity > 0:
            # Get or create inventory balance
            balance, created = InventoryBalance.objects.get_or_create(
                product=item.product,
                defaults={
                    'unit': item.product.unit,
                    'quantity_unit': 0
                }
            )
            
            # Update inventory
            balance.quantity_unit += item.received_quantity
            balance.save()
            
            # Create stock in record
            StockIn.objects.create(
                product=item.product,
                unit=item.product.unit,
                quantity=item.received_quantity,
                date_in=timezone.now().date(),
                acc=admin
            )
            
            # Update requisition item purchase_qty to fulfilled_qty
            # Find related requisition item
            purchase_request = purchase_order.request
            if purchase_request.requisition:
                requisition_items = Requisition_Item.objects.filter(
                    requisition=purchase_request.requisition,
                    product=item.product
                )
                for req_item in requisition_items:
                    # Update fulfilled_qty if it exists, otherwise update purchase_qty
                    req_item.fulfilled_qty = min(req_item.purchase_qty or req_item.quantity, item.received_quantity)
                    req_item.save()


# ============================================
# READY FOR PICKUP & STOCK DEDUCTION
# ============================================
def ready_for_pickup_requisitions(request):
    """List requisitions ready for pickup - ONLY when all items are available"""
    if 'acc_id' not in request.session:
        return redirect('admin_login')

    current_admin = Admin.objects.get(acc_id=request.session['acc_id'])
    
    # Get requisitions that need to be processed
    requisitions = Requisition.objects.filter(
        status__in=['Approved', 'Partially Approved – Pending Purchase', 'Pending Purchase', 'Purchased']
    ).select_related('employee').prefetch_related(
        'requisition_item_set__product'
    )
    
    ready_requisitions = []
    
    for req in requisitions:
        can_fulfill = True
        items_info = []  # Track item availability
        
        for item in req.requisition_item_set.all():
            # Get approved quantity (what should be given to employee)
            approved_qty = item.approved_qty or item.quantity
            
            # Check current stock availability
            try:
                inv_balance = InventoryBalance.objects.get(product=item.product)
                available_stock = inv_balance.quantity_unit
            except InventoryBalance.DoesNotExist:
                available_stock = 0
            
            # Check if purchase was needed and completed
            purchase_qty = item.purchase_qty or 0
            
            if purchase_qty > 0:
                # This item needs purchase - check if purchase is complete
                # Look for related purchase orders
                purchase_complete = False
                
                # Check if there are purchase requests for this requisition
                purchase_requests = PurchaseRequest.objects.filter(
                    requisition=req,
                    status='approved'
                )
                
                for pr in purchase_requests:
                    # Check if purchase order exists and is received
                    purchase_orders = PurchaseOrder.objects.filter(
                        request=pr,
                        status='received'
                    )
                    
                    for po in purchase_orders:
                        # Check if this specific item was received
                        po_items = po.purchaseorderitem_set.filter(
                            product=item.product,
                            received_quantity__gte=purchase_qty
                        )
                        
                        if po_items.exists():
                            purchase_complete = True
                            break
                    
                    if purchase_complete:
                        break
                
                # Item needs purchase but not yet received
                if not purchase_complete:
                    can_fulfill = False
                    items_info.append(f"{item.product.name}: Awaiting purchase delivery")
                    break
                
                # Purchase complete, check if stocked in
                if available_stock < approved_qty:
                    can_fulfill = False
                    items_info.append(f"{item.product.name}: Purchased but not yet stocked in")
                    break
            
            # Item doesn't need purchase but check stock
            elif available_stock < approved_qty:
                can_fulfill = False
                items_info.append(f"{item.product.name}: Insufficient stock ({available_stock} available, need {approved_qty})")
                break
            
            # Item is available
            else:
                items_info.append(f"{item.product.name}: Available in stock")
        
        if can_fulfill:
            req.items_info = items_info
            ready_requisitions.append(req)
    
    return render(request, 'liong/ready_for_pickup.html', {
        'requisitions': ready_requisitions,
        'current_admin': current_admin
    })

@transaction.atomic
def mark_ready_for_pickup(request, requisition_id):
    """Mark requisition as ready for pickup - Reserve stock"""
    if 'acc_id' not in request.session:
        messages.error(request, "Please log in first.")
        return redirect('admin_login')

    current_admin = Admin.objects.get(acc_id=request.session['acc_id'])
    
    if current_admin.role not in ['inventory_admin', 'super_admin']:
        messages.error(request, "Only inventory can mark items ready for pickup.")
        return redirect('ready_for_pickup_requisitions')

    requisition = get_object_or_404(Requisition, pk=requisition_id)
    
    # Check if already ready for pickup
    if requisition.status == 'Ready for Pickup':
        messages.info(request, f"Requisition #{requisition.requisition_id} is already ready for pickup.")
        return redirect('ready_for_pickup_requisitions')
    
    # Check if all items are available
    items = Requisition_Item.objects.filter(requisition=requisition).select_related('product')
    
    for item in items:
        approved_qty = item.approved_qty or item.quantity
        
        try:
            inv_balance = InventoryBalance.objects.get(product=item.product)
            if inv_balance.quantity_unit < approved_qty:
                messages.error(request, 
                    f"Insufficient stock for {item.product.name}. "
                    f"Available: {inv_balance.quantity_unit}, Needed: {approved_qty}")
                return redirect('ready_for_pickup_requisitions')
        except InventoryBalance.DoesNotExist:
            messages.error(request, f"No inventory record for {item.product.name}")
            return redirect('ready_for_pickup_requisitions')
    
    # Reserve stock (deduct from available but mark as reserved)
    for item in items:
        approved_qty = item.approved_qty or item.quantity
        
        inv_balance = InventoryBalance.objects.get(product=item.product)
        inv_balance.quantity_unit -= approved_qty
        inv_balance.save()
        
        # Create stock out record with status='reserved'
        StockOut.objects.create(
            product=item.product,
            unit=item.product.unit,
            quantity=approved_qty,
            date_out=timezone.now().date(),
            acc=current_admin,
            purpose=f"Reserved for Requisition #{requisition.requisition_id} - {requisition.employee.employee_name}",
            status='reserved',
            requisition=requisition,
            notes=f"Ready for pickup. Employee: {requisition.employee.employee_name}"
        )
        
        # Update reserved_qty (you might want to add this field to Requisition_Item)
        item.reserved_qty = approved_qty
        item.save()
    
    # Update requisition status
    requisition.status = "Ready for Pickup"
    requisition.pickup_ready_date = timezone.now()
    requisition.save()
    
    messages.success(request, 
        f"Requisition #{requisition.requisition_id} marked as Ready for Pickup. "
        f"Stock has been reserved for employee {requisition.employee.employee_name}.")
    return redirect('ready_for_pickup_requisitions')


@transaction.atomic
def complete_pickup(request, requisition_id):
    """Complete pickup - Change status from reserved to issued"""
    if 'acc_id' not in request.session:
        messages.error(request, "Please log in first.")
        return redirect('admin_login')

    current_admin = Admin.objects.get(acc_id=request.session['acc_id'])
    
    if current_admin.role not in ['inventory_admin', 'super_admin']:
        messages.error(request, "Only inventory can complete pickup.")
        return redirect('ready_for_pickup_requisitions')

    requisition = get_object_or_404(Requisition, pk=requisition_id)
    
    if requisition.status != 'Ready for Pickup':
        messages.error(request, "Requisition is not ready for pickup.")
        return redirect('ready_for_pickup_requisitions')
    
    # Get reserved stock out records
    stock_outs = StockOut.objects.filter(
        requisition=requisition,
        status='reserved'
    )
    
    if not stock_outs.exists():
        messages.error(request, "No reserved stock found for this requisition.")
        return redirect('ready_for_pickup_requisitions')
    
    # Update status from 'reserved' to 'issued'
    stock_outs.update(
        status='issued',
        purpose=f"Issued for Requisition #{requisition.requisition_id} - {requisition.employee.employee_name}",
        notes=f"Picked up by employee on {timezone.now().strftime('%Y-%m-%d %H:%M')}",
        date_out=timezone.now().date()
    )
    
    # Update fulfilled_qty on requisition items
    items = Requisition_Item.objects.filter(requisition=requisition)
    for item in items:
        item.fulfilled_qty = item.approved_qty or item.quantity
        item.save()
    
    # Mark requisition as completed
    requisition.status = "Fulfilled"
    requisition.fulfilled_date = timezone.now()
    requisition.save()
    
    messages.success(request, 
        f"Pickup completed for Requisition #{requisition.requisition_id}. "
        f"Stock has been issued to {requisition.employee.employee_name}.")
    return redirect('ready_for_pickup_requisitions')

@transaction.atomic
def cancel_pickup(request, requisition_id):
    """Inventory cancels pickup with reason"""
    if 'acc_id' not in request.session:
        messages.error(request, "Please log in first.")
        return redirect('admin_login')

    current_admin = Admin.objects.get(acc_id=request.session['acc_id'])
    
    if current_admin.role not in ['inventory_admin', 'super_admin']:
        messages.error(request, "Only inventory can cancel pickup.")
        return redirect('ready_for_pickup_requisitions')

    requisition = get_object_or_404(Requisition, pk=requisition_id)
    
    if requisition.status != 'Ready for Pickup':
        messages.error(request, "Only requisitions ready for pickup can be cancelled.")
        return redirect('ready_for_pickup_requisitions')
    
    if request.method == 'POST':
        cancellation_reason = request.POST.get('cancellation_reason', 'No reason provided')
        
        # Get reserved stock out records
        stock_outs = StockOut.objects.filter(
            requisition=requisition,
            status='reserved'
        )
        
        # Return stock to inventory
        for stock_out in stock_outs:
            try:
                inv_balance = InventoryBalance.objects.get(product=stock_out.product)
                inv_balance.quantity_unit += stock_out.quantity
                inv_balance.save()
                
                # Update stock out status to cancelled
                stock_out.status = 'cancelled'
                stock_out.purpose = f"Cancelled by Inventory: {cancellation_reason}"
                stock_out.notes = f"Cancelled by {current_admin.username} on {timezone.now().strftime('%Y-%m-%d %H:%M')}. Reason: {cancellation_reason}"
                stock_out.save()
            except InventoryBalance.DoesNotExist:
                pass
        
        # Update requisition status
        requisition.status = "Cancelled by Inventory"
        requisition.notes = f"Cancelled by {current_admin.username} on {timezone.now().strftime('%Y-%m-%d %H:%M')}. Reason: {cancellation_reason}"
        requisition.save()
        
        messages.success(request, 
            f"Pickup cancelled for Requisition #{requisition.requisition_id}. "
            f"Stock has been returned to inventory.")
        return redirect('ready_for_pickup_requisitions')
    
    # GET request - show cancellation form
    return render(request, 'liong/cancel_pickup_modal.html', {
        'requisition': requisition,
        'current_admin': current_admin
    })

# ============================================
# SUPPLIER MANAGEMENT
# ============================================

def supplier_list(request):
    """List all suppliers"""
    if 'acc_id' not in request.session:
        return redirect('admin_login')

    current_admin = Admin.objects.get(acc_id=request.session['acc_id'])
    
    suppliers = Supplier.objects.all().order_by('name')
    
    return render(request, 'liong/suppliers.html', {
        'suppliers': suppliers,
        'current_admin': current_admin
    })


@transaction.atomic
def add_supplier(request):
    """Add new supplier"""
    if 'acc_id' not in request.session:
        messages.error(request, "Please log in first.")
        return redirect('admin_login')

    current_admin = Admin.objects.get(acc_id=request.session['acc_id'])
    
    if current_admin.role not in ['inventory_admin', 'super_admin']:
        messages.error(request, "Only inventory can add suppliers.")
        return redirect('supplier_list')
    
    if request.method == 'POST':
        name = request.POST.get('name')
        contact_person = request.POST.get('contact_person')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        address = request.POST.get('address')
        payment_terms = request.POST.get('payment_terms', 'Net 30')
        
        if not name:
            messages.error(request, "Supplier name is required.")
            return redirect('supplier_list')
        
        # Check if supplier already exists
        if Supplier.objects.filter(name=name).exists():
            messages.warning(request, f"Supplier '{name}' already exists.")
            return redirect('supplier_list')
        
        Supplier.objects.create(
            name=name,
            contact_person=contact_person,
            email=email,
            phone=phone,
            address=address,
            payment_terms=payment_terms
        )
        
        messages.success(request, f"Supplier '{name}' added successfully.")
        return redirect('supplier_list')
    
    return redirect('supplier_list')


@require_POST
@transaction.atomic
def deactivate_supplier(request, supplier_id):
    """Deactivate a supplier"""
    if 'acc_id' not in request.session:
        messages.error(request, "Please log in first.")
        return redirect('admin_login')

    current_admin = Admin.objects.get(acc_id=request.session['acc_id'])
    
    if current_admin.role not in ['inventory_admin', 'super_admin']:
        messages.error(request, "Only inventory can deactivate suppliers.")
        return redirect('supplier_list')

    supplier = get_object_or_404(Supplier, pk=supplier_id)
    
    # Check if supplier has active purchase orders
    active_pos = PurchaseOrder.objects.filter(
        supplier=supplier,
        status__in=['draft', 'sent', 'ordered', 'partially_received']
    ).exists()
    
    if active_pos:
        messages.error(request, f"Cannot deactivate {supplier.name}. They have active purchase orders.")
        return redirect('supplier_list')
    
    supplier.status = 'inactive'
    supplier.save()
    
    messages.success(request, f"Supplier '{supplier.name}' deactivated.")
    return redirect('supplier_list')


@require_POST
@transaction.atomic
def activate_supplier(request, supplier_id):
    """Activate a supplier"""
    if 'acc_id' not in request.session:
        messages.error(request, "Please log in first.")
        return redirect('admin_login')

    current_admin = Admin.objects.get(acc_id=request.session['acc_id'])
    
    if current_admin.role not in ['inventory_admin', 'super_admin']:
        messages.error(request, "Only inventory can activate suppliers.")
        return redirect('supplier_list')

    supplier = get_object_or_404(Supplier, pk=supplier_id)
    
    supplier.status = 'active'
    supplier.save()
    
    messages.success(request, f"Supplier '{supplier.name}' activated.")
    return redirect('supplier_list')


def edit_supplier(request, supplier_id):
    """AJAX: Get supplier details for editing"""
    if 'acc_id' not in request.session:
        return redirect('admin_login')

    supplier = get_object_or_404(Supplier, pk=supplier_id)
    
    return render(request, 'liong/partials/edit_supplier.html', {
        'supplier': supplier
    })


@require_POST
@transaction.atomic
def update_supplier(request, supplier_id):
    """Update supplier details"""
    if 'acc_id' not in request.session:
        messages.error(request, "Please log in first.")
        return redirect('admin_login')

    current_admin = Admin.objects.get(acc_id=request.session['acc_id'])
    
    if current_admin.role not in ['inventory_admin', 'super_admin']:
        messages.error(request, "Only inventory can update suppliers.")
        return redirect('supplier_list')

    supplier = get_object_or_404(Supplier, pk=supplier_id)
    
    name = request.POST.get('name')
    contact_person = request.POST.get('contact_person')
    email = request.POST.get('email')
    phone = request.POST.get('phone')
    address = request.POST.get('address')
    payment_terms = request.POST.get('payment_terms', 'Net 30')
    
    if not name:
        messages.error(request, "Supplier name is required.")
        return redirect('supplier_list')
    
    # Check if name is changed and conflicts with another supplier
    if name != supplier.name and Supplier.objects.filter(name=name).exists():
        messages.error(request, f"Supplier '{name}' already exists.")
        return redirect('supplier_list')
    
    supplier.name = name
    supplier.contact_person = contact_person
    supplier.email = email
    supplier.phone = phone
    supplier.address = address
    supplier.payment_terms = payment_terms
    supplier.save()
    
    messages.success(request, f"Supplier '{supplier.name}' updated successfully.")
    return redirect('supplier_list')


@require_POST
@transaction.atomic
def delete_supplier(request, supplier_id):
    """Delete a supplier (soft delete)"""
    if 'acc_id' not in request.session:
        messages.error(request, "Please log in first.")
        return redirect('admin_login')

    current_admin = Admin.objects.get(acc_id=request.session['acc_id'])
    
    if current_admin.role != 'super_admin':
        messages.error(request, "Only super admin can delete suppliers.")
        return redirect('supplier_list')

    supplier = get_object_or_404(Supplier, pk=supplier_id)
    
    # Check if supplier has any purchase orders
    has_pos = PurchaseOrder.objects.filter(supplier=supplier).exists()
    
    if has_pos:
        messages.error(request, f"Cannot delete {supplier.name}. They have purchase order history.")
        return redirect('supplier_list')
    
    supplier_name = supplier.name
    supplier.delete()
    
    messages.success(request, f"Supplier '{supplier_name}' deleted.")
    return redirect('supplier_list')


# ============================================
# REPORTS
# ============================================
def purchase_order_report(request):
    """Generate purchase order report"""
    if 'acc_id' not in request.session:
        return redirect('admin_login')

    current_admin = Admin.objects.get(acc_id=request.session['acc_id'])
    
    # Get filter parameters
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    supplier_id = request.GET.get('supplier')
    status = request.GET.get('status')
    
    purchase_orders = PurchaseOrder.objects.select_related(
        'supplier', 'created_by'
    ).prefetch_related('purchaseorderitem_set__product')
    
    # Apply filters
    if start_date:
        purchase_orders = purchase_orders.filter(created_date__gte=start_date)
    if end_date:
        purchase_orders = purchase_orders.filter(created_date__lte=end_date)
    if supplier_id:
        purchase_orders = purchase_orders.filter(supplier_id=supplier_id)
    if status:
        purchase_orders = purchase_orders.filter(status=status)
    
    suppliers = Supplier.objects.all()
    
    return render(request, 'liong/reports/purchase_order_report.html', {
        'purchase_orders': purchase_orders,
        'suppliers': suppliers,
        'current_admin': current_admin,
        'filters': {
            'start_date': start_date,
            'end_date': end_date,
            'supplier_id': supplier_id,
            'status': status
        }
    })


def accomplishment_report(request):
    """Generate accomplishment report"""
    if 'acc_id' not in request.session:
        return redirect('admin_login')

    current_admin = Admin.objects.get(acc_id=request.session['acc_id'])
    
    # Get filter parameters
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    # Get completed requisitions
    completed_requisitions = Requisition.objects.filter(
        status='Fulfilled'
    ).select_related('employee').prefetch_related(
        'requisition_item_set__product'
    )
    
    if start_date:
        completed_requisitions = completed_requisitions.filter(date_requested__gte=start_date)
    if end_date:
        completed_requisitions = completed_requisitions.filter(date_requested__lte=end_date)
    
    # Get purchase statistics
    purchase_stats = PurchaseOrder.objects.filter(
        status='received'
    )
    
    if start_date:
        purchase_stats = purchase_stats.filter(created_date__gte=start_date)
    if end_date:
        purchase_stats = purchase_stats.filter(created_date__lte=end_date)
    
    total_purchase_amount = purchase_stats.aggregate(
        total=models.Sum('total_amount')
    )['total'] or 0
    
    return render(request, 'liong/reports/accomplishment_report.html', {
        'completed_requisitions': completed_requisitions,
        'total_purchase_amount': total_purchase_amount,
        'purchase_count': purchase_stats.count(),
        'current_admin': current_admin,
        'filters': {
            'start_date': start_date,
            'end_date': end_date
        }
    })


def purchase_request_detail(request, request_id):
    """AJAX: Purchase request details for modal"""
    pr = get_object_or_404(PurchaseRequest.objects.select_related(
        'requisition__employee', 'requested_by', 'approved_by'
    ).prefetch_related(
        'purchaserequestitem_set__product'
    ), pk=request_id)
    
    return render(request, 'liong/partials/purchase_request_detail.html', {
        'pr': pr
    })


def purchase_order_detail(request, po_id):
    """AJAX: Purchase order details for modal"""
    po = get_object_or_404(PurchaseOrder.objects.select_related(
        'supplier', 'created_by', 'request__requisition__employee'
    ).prefetch_related(
        'purchaseorderitem_set__product',
        'purchaseorderhistory_set__changed_by'
    ), pk=po_id)
    
    return render(request, 'liong/partials/purchase_order_detail.html', {
        'po': po
    })




@transaction.atomic
def employee_cancel_pickup(request, requisition_id):
    """Employee cancels their own pickup request"""
    if 'employee_id' not in request.session:
        messages.error(request, "Please log in first.")
        return redirect('employee_login')

    employee = get_object_or_404(Employee, pk=request.session['employee_id'])
    requisition = get_object_or_404(Requisition, pk=requisition_id, employee=employee)
    
    if requisition.status != 'Ready for Pickup':
        messages.error(request, "Only requisitions ready for pickup can be cancelled.")
        return redirect('employee_requisitions')
    
    # Get reserved stock out records
    stock_outs = StockOut.objects.filter(
        requisition=requisition,
        status='reserved'
    )
    
    # Return stock to inventory
    for stock_out in stock_outs:
        try:
            inv_balance = InventoryBalance.objects.get(product=stock_out.product)
            inv_balance.quantity_unit += stock_out.quantity
            inv_balance.save()
            
            # Update stock out status to cancelled
            stock_out.status = 'cancelled'
            stock_out.purpose = f"Cancelled by employee for Requisition #{requisition.requisition_id}"
            stock_out.notes = f"Cancelled by {employee.employee_name} on {timezone.now().strftime('%Y-%m-%d %H:%M')}"
            stock_out.save()
        except InventoryBalance.DoesNotExist:
            pass
    
    # Update requisition status and add cancellation reason
    requisition.status = "Cancelled by Employee"
    requisition.notes = f"Cancelled by employee on {timezone.now().strftime('%Y-%m-%d %H:%M')}"
    requisition.save()
    
    # Notify inventory admin
    # You can add notification logic here
    
    messages.success(request, 
        f"Your pickup for Requisition #{requisition.requisition_id} has been cancelled. "
        f"Stock has been returned to inventory.")
    return redirect('employee_requisitions')



# Employee portal views
def employee_requisitions(request):
    """Employee view of their requisitions"""
    if 'employee_id' not in request.session:
        return redirect('employee_login')
    
    employee = Employee.objects.get(employee_id=request.session['employee_id'])
    
    requisitions = Requisition.objects.filter(employee=employee).order_by('-date_requested')
    
    return render(request, 'liong/employee_requisitions.html', {
        'requisitions': requisitions,
        'employee': employee
    })

@transaction.atomic
def employee_confirm_pickup(request, requisition_id):
    """Employee confirms they received the items"""
    if 'employee_id' not in request.session:
        messages.error(request, "Please log in first.")
        return redirect('employee_login')
    
    employee = get_object_or_404(Employee, pk=request.session['employee_id'])
    requisition = get_object_or_404(Requisition, pk=requisition_id, employee=employee)
    
    if requisition.status != 'Ready for Pickup':
        messages.error(request, "Only requisitions ready for pickup can be confirmed.")
        return redirect('employee_requisitions')
    
    # Update stock out records from 'reserved' to 'issued'
    stock_outs = StockOut.objects.filter(
        requisition=requisition,
        status='reserved'
    )
    
    stock_outs.update(
        status='issued',
        purpose=f"Issued to {employee.employee_name} - Confirmed by employee",
        notes=f"Confirmed received by {employee.employee_name} on {timezone.now().strftime('%Y-%m-%d %H:%M')}"
    )
    
    # Update requisition
    requisition.status = "Fulfilled"
    requisition.fulfilled_date = timezone.now()
    requisition.notes = f"Confirmed by employee on {timezone.now().strftime('%Y-%m-%d %H:%M')}"
    requisition.save()
    
    # Update fulfilled_qty
    items = Requisition_Item.objects.filter(requisition=requisition)
    for item in items:
        item.fulfilled_qty = item.approved_qty or item.quantity
        item.save()
    
    messages.success(request, 
        f"Thank you for confirming receipt of Requisition #{requisition.requisition_id}.")
    return redirect('employee_requisitions')




def request_history(request):
    """View employee's request history"""
    # Check if user is logged in as employee (through admin system)
    if 'acc_id' not in request.session:
        messages.error(request, "Please log in first.")
        return redirect('admin_login')
    
    try:
        # Get admin/employee from session
        admin = Admin.objects.get(acc_id=request.session['acc_id'])
        
        # If user is not an employee, redirect to appropriate dashboard
        if admin.role != 'employee':
            messages.error(request, "This page is for employees only.")
            
            # Redirect based on role
            if admin.role == 'super_admin':
                return redirect('adminDashboard')
            elif admin.role == 'inventory_admin':
                return redirect('inventory_dashboard')
            else:
                return redirect('admin_login')
        
        # Find employee record for this admin
        try:
            employee = Employee.objects.get(admin=admin)
        except Employee.DoesNotExist:
            # Try to find employee by contact info
            employee = Employee.objects.filter(contact_value=admin.email).first()
            if not employee:
                messages.error(request, "Employee record not found. Please contact administrator.")
                return redirect('admin_login')
        
        # Check if employee is active
        if employee.status != 'active':
            messages.error(request, "Your account has been deactivated. Please contact administrator.")
            return redirect('admin_login')
        
        # Get all requisitions for this employee
        requisitions = Requisition.objects.filter(
            employee=employee
        ).select_related('employee').prefetch_related(
            'requisition_item_set__product'
        ).order_by('-date_requested')
        
        # Counts for stats
        ready_count = requisitions.filter(status='Ready for Pickup').count()
        approved_count = requisitions.filter(status='Approved').count()
        pending_count = requisitions.filter(status='Pending Approval').count()
        received_count = requisitions.filter(status='Received').count()
        
        # Get ready for pickup requisitions
        ready_requisitions = requisitions.filter(status='Ready for Pickup')
        
        context = {
            'requisitions': requisitions,
            'current_user': employee.employee_name,
            'ready_count': ready_count,
            'approved_count': approved_count,
            'pending_count': pending_count,
            'received_count': received_count,
            'ready_requisitions': ready_requisitions,
        }
        
        return render(request, 'liong/requestHistory.html', context)
        
    except Admin.DoesNotExist:
        messages.error(request, "Session expired. Please log in again.")
        request.session.flush()
        return redirect('admin_login')
    except Exception as e:
        messages.error(request, f"An error occurred: {str(e)}")
        return redirect('admin_login')

def mark_as_received(request, requisition_id):
    """Mark a requisition as received by employee"""
    # Check if user is logged in
    if 'acc_id' not in request.session:
        messages.error(request, "Please log in first.")
        return redirect('admin_login')
    
    if request.method == 'POST':
        try:
            admin = Admin.objects.get(acc_id=request.session['acc_id'])
            
            # Check if user is an employee
            if admin.role != 'employee':
                messages.error(request, "Only employees can mark requisitions as received.")
                return redirect('admin_login')
            
            # Find employee
            try:
                employee = Employee.objects.get(admin=admin)
            except Employee.DoesNotExist:
                employee = Employee.objects.filter(contact_value=admin.email).first()
                if not employee:
                    messages.error(request, "Employee record not found.")
                    return redirect('request_history')
            
            # Get requisition
            requisition = get_object_or_404(Requisition, requisition_id=requisition_id, employee=employee)
            
            # Check if requisition is ready for pickup
            if requisition.status != 'Ready for Pickup':
                messages.error(request, f"Requisition #{requisition_id} is not ready for pickup.")
                return redirect('request_history')
            
            # Update status
            requisition.status = 'Received'
            requisition.save()
            
            messages.success(request, f"Requisition #{requisition_id} marked as received.")
            
        except Admin.DoesNotExist:
            messages.error(request, "Session expired. Please log in again.")
            request.session.flush()
            return redirect('admin_login')
        except Exception as e:
            messages.error(request, f"Error marking requisition as received: {str(e)}")
    
    return redirect('request_history')
