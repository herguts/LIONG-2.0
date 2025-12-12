from django.shortcuts import redirect, render
from myapp.models import Admin, Employee, Requisition, Requisition_Item, Products, InventoryBalance,StockIn, StockOut, RequisitionStatusHistory, PurchaseRequest, PurchaseRequestItem, Supplier, PurchaseOrder, PurchaseOrderItem, PurchaseOrderHistory, PurchaseReceiving, ReceivedItem, QualityCheck, models, RejectedItem, RejectedStock, ReturnRequest, DisposalRecord, ReplacementRequest
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
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings



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
    """Add new employee with account"""
    if 'acc_id' not in request.session:
        return redirect('admin_login')
    
    current_admin = Admin.objects.get(acc_id=request.session['acc_id'])
    
    if current_admin.role != 'super_admin':
        messages.error(request, "Only super admin can add employees.")
        return redirect('manage_accounts')
    
    if request.method == 'POST':
        try:
            employee_name = request.POST.get('employee_name')
            email = request.POST.get('email')
            password = request.POST.get('password')
            confirm_password = request.POST.get('confirm_password')
            contact_type = request.POST.get('contact_type', 'email')
            contact_value = request.POST.get('contact_value', '')
            role = request.POST.get('role', 'employee')
            position = request.POST.get('position', '')
            date_joined = request.POST.get('date_joined')
            
            # Validate required fields
            if not all([employee_name, email, password, confirm_password, date_joined]):
                messages.error(request, "Please fill in all required fields.")
                return redirect('manage_accounts')
            
            # Validate passwords match
            if password != confirm_password:
                messages.error(request, "Passwords do not match.")
                return redirect('manage_accounts')
            
            # Validate password length
            if len(password) < 6:
                messages.error(request, "Password must be at least 6 characters.")
                return redirect('manage_accounts')
            
            # Check if account already exists
            if Admin.objects.filter(email=email).exists():
                messages.error(request, "An account with this email already exists.")
                return redirect('manage_accounts')
            
            # Create the admin account first
            admin = Admin.objects.create(
                name=employee_name,
                email=email,
                password=password,  # In production, hash this password
                role=role,
                department=request.POST.get('department', '')
            )
            
            # Create the employee record
            employee = Employee.objects.create(
                admin=admin,
                employee_name=employee_name,
                contact_type=contact_type,
                contact_value=contact_value if contact_value else email,
                position=position,
                date_joined=date_joined,
                status='active'
            )
            
            # Check if this is from pending accounts
            from_existing = request.POST.get('from_existing_account')
            existing_acc_id = request.POST.get('existing_acc_id')
            
            if from_existing and existing_acc_id:
                # If creating from pending account, delete the old account
                try:
                    old_account = Admin.objects.get(acc_id=existing_acc_id)
                    old_account.delete()
                    messages.success(request, f"Account converted to employee: {employee_name}")
                except Admin.DoesNotExist:
                    pass
            
            messages.success(request, f"Employee account created successfully for {employee_name}")
            
            # Set session for prefill if needed
            request.session['prefill_account_id'] = None
            
            # FIXED LINE: Just return redirect, don't concatenate with string
            return redirect('manage_accounts')
            
        except Exception as e:
            messages.error(request, f"Error creating employee account: {str(e)}")
            return redirect('manage_accounts')
    
    # If GET request, redirect to manage accounts page
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
                
                for new_item in new_items_data:
                    # Check duplicate name (case-insensitive)
                    if Products.objects.filter(name__iexact=new_item['name']).exists():
                        messages.warning(
                            request, 
                            f'Product "{new_item["name"]}" already exists. It was not added.'
                        )
                        # rollback everything:
                        raise Exception("Duplicate product detected")
                    
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
        qty = balance.quantity_unit or 0  # handle None values

        if qty <= 0:
            out_of_stock_count += 1
        elif 1 <= qty <= 10:
            low_stock_count += 1
        else:  # qty > 10
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

    # Get admin info
    admin = Admin.objects.get(pk=request.session.get('acc_id'))
    
    # Get products for dropdown - assuming you want all products
    products = Products.objects.all()
    
    # Get inventory balances for the select dropdown
    balance = InventoryBalance.objects.select_related('product').all()
    
    # Get recent stock ins (last 10 entries)
    recent_stock_in = StockIn.objects.select_related('product', 'acc').order_by('-stock_in_id')[:10]

    if request.method == 'POST':
        product_id = request.POST.get('product')
        quantity = request.POST.get('quantity') or 0
        quantity_meters = request.POST.get('quantity_meters') or 0
        quantity_klg = request.POST.get('quantity_klg') or 0
        date_in = request.POST.get('date_in') or date.today()

        # Validate
        if not product_id:
            messages.error(request, "Please select a product.")
            return redirect('stock_in')

        try:
            product = Products.objects.get(pk=product_id)
            unit = product.unit  # Get unit from the product itself
        except Products.DoesNotExist:
            messages.error(request, "Product not found.")
            return redirect('stock_in')

        # Create StockIn record
        StockIn.objects.create(
            product=product,
            unit=unit,
            quantity=float(quantity),
            quantity_meters=float(quantity_meters),
            quantity_klg=float(quantity_klg),
            date_in=date_in,
            acc=admin
        )

        # Update InventoryBalance
        balance_obj, created = InventoryBalance.objects.get_or_create(
            product=product,
            defaults={
                'unit': unit,
                'quantity_unit': 0,
                'quantity_meters': 0,
                'quantity_klg': 0
            }
        )

        balance_obj.quantity_unit = (balance_obj.quantity_unit or Decimal('0')) + Decimal(str(quantity))
        balance_obj.quantity_meters = (balance_obj.quantity_meters or Decimal('0')) + Decimal(str(quantity_meters))
        balance_obj.quantity_klg = (balance_obj.quantity_klg or Decimal('0')) + Decimal(str(quantity_klg))
        balance_obj.last_updated = timezone.now()
        balance_obj.save()

        messages.success(request, f"{quantity} {unit} added to {product.name}.")
        return redirect('stock_in')

    return render(request, "liong/stock_in.html", {
        "products": balance,  # use balances for <select> options
        "products_json": products,  # for JS if needed
        "recent_stock_in": recent_stock_in,
        "admin": admin
    })


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
        
        if Products.objects.filter(name=item_name).exists():
            messages.error(request, f'Product "{item_name}" with unit "{unit}" already exists!')
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
            remarks=f"{remarks}"
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




@transaction.atomic  # Ensures database operations are atomic
def purchase_again(request, po_id):
    """Create a new purchase order from an existing partially received PO and send email"""
    try:
        print(f"=== purchase_again view called ===")
        print(f"PO ID: {po_id}")
        print(f"Request method: {request.method}")
        
        # Check if user is logged in
        if 'acc_id' not in request.session:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'error': 'Please log in first.'
                })
            messages.error(request, "Please log in first.")
            return redirect('admin_login')
        
        # Get current admin
        current_admin = Admin.objects.get(acc_id=request.session['acc_id'])
        
        # Check admin role
        if current_admin.role not in ['inventory_admin', 'super_admin']:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'error': 'Only inventory can create purchase orders.'
                })
            messages.error(request, "Only inventory can create purchase orders.")
            return redirect('purchase_orders_list')
        
        # Get the original PO
        original_po = get_object_or_404(PurchaseOrder, pk=po_id)
        print(f"Found PO: {original_po.po_number}, Status: {original_po.status}")
        
        # Check if status is partially_received
        if original_po.status != 'partially_received':
            error_msg = 'Purchase Again is only available for partially received orders.'
            print(f"Error: {error_msg}")
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'error': error_msg
                })
            messages.error(request, error_msg)
            return redirect('purchase_orders_list')
        
        # Handle GET request (opening modal)
        if request.method == 'GET':
            print("Handling GET request for modal data")
            # Return JSON data for modal
            return JsonResponse({
                'success': True,
                'po_number': original_po.po_number,
                'supplier_id': str(original_po.supplier.supplier_id),
                'supplier_name': original_po.supplier.name,
                'payment_method': original_po.payment_method if hasattr(original_po, 'payment_method') else 'cash_on_delivery'
            })
        
        # Handle POST request (submitting form)
        elif request.method == 'POST':
            print("Handling POST request to create new PO")
            
            # Get form data
            supplier_id = request.POST.get('supplier')
            delivery_date = request.POST.get('delivery_date')
            payment_method = request.POST.get('payment_method', 'cash_on_delivery')
            custom_payment = request.POST.get('custom_payment', '')
            notes = request.POST.get('notes', f"Re-order from {original_po.po_number}")
            
            print(f"Form data - Supplier: {supplier_id}, Delivery: {delivery_date}, Payment: {payment_method}")
            
            if not supplier_id:
                error_msg = "Please select a supplier."
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'error': error_msg
                    })
                messages.error(request, error_msg)
                return redirect('purchase_orders_list')
            
            # Get supplier
            supplier = get_object_or_404(Supplier, pk=supplier_id)
            
            # Determine payment terms based on selection
            payment_terms = "Net 30"  # Default
            
            if payment_method == 'cash_on_delivery':
                payment_terms = "Cash on Delivery"
            elif payment_method == 'bank_transfer':
                payment_terms = "Bank Transfer"
            elif payment_method == 'gcash':
                payment_terms = "GCash"
            elif payment_method == 'check':
                payment_terms = "Check Payment"
            elif payment_method == 'credit':
                payment_terms = "Credit - Net 30 Days"
            elif custom_payment:
                payment_terms = custom_payment
            
            # Generate new PO number
            last_po = PurchaseOrder.objects.order_by('-created_date').first()
            if last_po and last_po.po_number.startswith('PO-'):
                try:
                    last_number = int(last_po.po_number.split('-')[1])
                    new_number = f"PO-{last_number + 1:04d}"
                except:
                    new_number = f"PO-{PurchaseOrder.objects.count() + 1:04d}"
            else:
                new_number = f"PO-{PurchaseOrder.objects.count() + 1:04d}"
            
            print(f"Creating new PO with number: {new_number}")
            
            # Create a new PO
            new_po = PurchaseOrder.objects.create(
                po_number=new_number,
                supplier=supplier,
                request=original_po.request,
                total_amount=original_po.total_amount,
                status='draft',
                payment_terms=payment_terms,
                delivery_date=delivery_date if delivery_date else None,
                notes=notes,
                created_by=current_admin,
                created_date=timezone.now()
            )
            
            print(f"New PO created: {new_po.po_id}")
            
            # Copy PO items from original - FIXED: Use 'po' field instead of 'purchase_order'
            original_items = PurchaseOrderItem.objects.filter(po=original_po)  # Changed from purchase_order to po
            print(f"Copying {original_items.count()} items from original PO")
            
            for item in original_items:
                PurchaseOrderItem.objects.create(
                    po=new_po,  # Changed from purchase_order to po
                    product=item.product,
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    total_price=item.total_price
                )
            
            # Also update the requisition status if it exists
            if new_po.request and new_po.request.requisition:
                new_po.request.requisition.status = 'Pending Purchase'
                new_po.request.requisition.save()
            
            # ====================================================
            # AUTOMATICALLY SEND EMAIL TO SUPPLIER
            # ====================================================
            if supplier.email:
                try:
                    # Get all items for the PO - FIXED: Use 'po' field
                    items = new_po.purchaseorderitem_set.all()
                    
                    # Prepare email context
                    context = {
                        'company_name': getattr(settings, 'COMPANY_NAME', 'Your Company'),
                        'po': new_po,
                        'supplier': supplier,
                        'items': items,
                        'sent_by': current_admin,
                        'original_po_number': original_po.po_number,  # Include original PO number
                    }
                    
                    # Render HTML email
                    html_message = render_to_string('liong/emails/purchase_order_email2.html', context)
                    plain_message = strip_tags(html_message)
                    
                    # Send email to supplier
                    send_mail(
                        subject=f"Purchase Order #{new_po.po_number} - {getattr(settings, 'COMPANY_NAME', 'Your Company')}",
                        message=plain_message,
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[supplier.email],
                        html_message=html_message,
                        fail_silently=False,
                    )
                    
                    # Also send a copy to the inventory admin if they have email
                    if current_admin.email:
                        try:
                            send_mail(
                                subject=f"PO #{new_po.po_number} Copy - Sent to {supplier.name}",
                                message=f"Purchase Order #{new_po.po_number} (re-order from {original_po.po_number}) has been sent to {supplier.name} ({supplier.email})",
                                from_email=settings.DEFAULT_FROM_EMAIL,
                                recipient_list=[current_admin.email],
                                fail_silently=True,
                            )
                        except Exception as admin_email_error:
                            print(f"Failed to send admin copy: {admin_email_error}")
                    
                    # Update PO to track email was sent
                    if hasattr(new_po, 'email_sent'):
                        new_po.email_sent = True
                        new_po.email_sent_date = timezone.now()
                        new_po.email_sent_to = supplier.email
                        new_po.save()
                    

                    
                    # Return success response
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({
                            'success': True,
                            'new_po_id': str(new_po.po_id),
                            'new_po_number': new_po.po_number,
                        })
                    
                    messages.success(request)
                    return redirect('purchase_order_list', po_id=new_po.po_id)
                    
                except Exception as email_error:
                    print(f"Email sending error: {email_error}")
                    # If email fails, still show success for PO creation but warn about email
                    new_po.save()
                    warning_msg = f"✅ Purchase Order #{new_po.po_number} created successfully, but email could not be sent to supplier. Error: {str(email_error)[:100]}..."
                    
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({
                            'success': True,
                            'new_po_id': str(new_po.po_id),
                            'new_po_number': new_po.po_number,
                            'warning': warning_msg
                        })
                    
                    messages.warning(request, warning_msg)
                    return redirect('purchase_order_list', po_id=new_po.po_id)
            else:
                # Supplier doesn't have email
                info_msg = f"✅ Purchase Order #{new_po.po_number} created successfully! Note: Supplier does not have an email address."
                
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': True,
                        'new_po_id': str(new_po.po_id),
                        'new_po_number': new_po.po_number,
                        'message': info_msg
                    })
                
                messages.success(request, info_msg)
                return redirect('purchase_order_list', po_id=new_po.po_id)
        
        else:
            # Invalid method
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid request method.'
                })
            return redirect('purchase_orders_list')
            
    except Exception as e:
        print(f"=== ERROR in purchase_again ===")
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {str(e)}")
        import traceback
        print(f"Traceback:\n{traceback.format_exc()}")
        
        error_msg = f'Error creating purchase order: {str(e)}'
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'error': error_msg
            })
        messages.error(request, error_msg)
        return redirect('purchase_orders_list')


# In your views.py, update the view that renders the purchase orders page
def purchase_orders_list(request):
    if 'acc_id' not in request.session:
        messages.error(request, "Please log in first.")
        return redirect('admin_login')

    current_admin = Admin.objects.get(acc_id=request.session['acc_id'])
    
    # Get all purchase orders
    purchase_orders = PurchaseOrder.objects.all().order_by('-created_date')
    
    # GET ALL SUPPLIERS - Add this
    suppliers = Supplier.objects.all().order_by('name')
    
    context = {
        'purchase_orders': purchase_orders,
        'current_admin': current_admin,
        'today': timezone.now().date(),
        'suppliers': suppliers,  # ADD THIS LINE
    }
    
    return render(request, 'liong/purchase_orders.html', context)



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
        
        # Get payment method from form
        payment_method = request.POST.get('payment_method', 'cash_on_delivery')
        custom_payment = request.POST.get('custom_payment', '')
        notes = request.POST.get('notes', '')
        
        if not supplier_id:
            messages.error(request, "Please select a supplier.")
            return redirect('approved_purchase_requests')

        supplier = get_object_or_404(Supplier, pk=supplier_id)
        
        # Determine payment terms based on selection
        payment_terms = "Net 30"  # Default
        
        if payment_method == 'cash_on_delivery':
            payment_terms = "Cash on Delivery"
        elif payment_method == 'bank_transfer':
            payment_terms = "Bank Transfer"
        elif payment_method == 'gcash':
            payment_terms = "GCash"
        elif payment_method == 'check':
            payment_terms = "Check Payment"
        elif payment_method == 'credit':
            payment_terms = "Credit - Net 30 Days"
        elif custom_payment:
            payment_terms = custom_payment
        
        # Create purchase order - model will auto-generate po_number in save()
        purchase_order = PurchaseOrder.objects.create(
            request=purchase_request,
            supplier=supplier,
            created_by=current_admin,
            delivery_date=delivery_date if delivery_date else None,
            payment_terms=payment_terms,
            notes=notes,
            status='draft'  # Initial status for PO
        )
        
        # Get items from purchase request
        request_items = PurchaseRequestItem.objects.filter(request=purchase_request)
        
        # Calculate total for the PO
        total_amount = 0
        
        for req_item in request_items:
            # Calculate unit price from estimated total
            if req_item.total_estimated_price and req_item.quantity_to_purchase > 0:
                unit_price = req_item.total_estimated_price / req_item.quantity_to_purchase
            else:
                # Try to get from product, or use 0
                try:
                    unit_price = req_item.product.price
                except:
                    unit_price = 0
            
            # Create PO item
            po_item = PurchaseOrderItem.objects.create(
                po=purchase_order,
                product=req_item.product,
                quantity=req_item.quantity_to_purchase,
                unit_price=unit_price
            )
            
            # Add to total
            total_amount += po_item.total_price
            
            # Update requisition_item purchase_qty if needed
            if hasattr(req_item, 'requisition_item') and req_item.requisition_item:
                req_item.requisition_item.purchase_qty = req_item.quantity_to_purchase
                req_item.requisition_item.save()
        
        # Update purchase order total amount
        purchase_order.total_amount = total_amount
        purchase_order.save()
        
        # Also update the requisition status if it exists
        if purchase_request.requisition:
            purchase_request.requisition.status = 'Pending Purchase'
            purchase_request.requisition.save()

        # ====================================================
        # AUTOMATICALLY SEND EMAIL TO SUPPLIER
        # ====================================================
        if supplier.email:
            try:
                # Get all items for the PO
                items = purchase_order.purchaseorderitem_set.all()
                
                # Prepare email context
                context = {
                    'company_name': settings.COMPANY_NAME,
                    'po': purchase_order,
                    'supplier': supplier,
                    'items': items,
                    'sent_by': current_admin,
                }
                
                # Render HTML email
                html_message = render_to_string('liong/emails/purchase_order_email.html', context)
                plain_message = strip_tags(html_message)
                
                # Send email to supplier
                send_mail(
                    subject=f"Purchase Order #{purchase_order.po_number} - {settings.COMPANY_NAME}",
                    message=plain_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[supplier.email],
                    html_message=html_message,
                    fail_silently=False,
                )
                
                # Also send a copy to the inventory admin if they have email
                if current_admin.email:
                    try:
                        send_mail(
                            subject=f"PO #{purchase_order.po_number} Copy - Sent to {supplier.name}",
                            message=f"Purchase Order #{purchase_order.po_number} has been sent to {supplier.name} ({supplier.email})",
                            from_email=settings.DEFAULT_FROM_EMAIL,
                            recipient_list=[current_admin.email],
                            fail_silently=True,
                        )
                    except:
                        pass
                
                # Update PO to track email was sent
                purchase_order.email_sent = True
                purchase_order.email_sent_date = timezone.now()
                purchase_order.email_sent_to = supplier.email
                purchase_order.save()
                
                # Show success message with email confirmation
                messages.success(
                    request, 
                    f"✅ Purchase Order #{purchase_order.po_number} created successfully and sent to {supplier.name}!"
                )
                
            except Exception as e:
                # If email fails, still show success for PO creation but warn about email
                purchase_order.save()
                messages.warning(
                    request, 
                    f"✅ Purchase Order #{purchase_order.po_number} created successfully, but email could not be sent to supplier. Error: {str(e)[:100]}..."
                )
        else:
            # Supplier doesn't have email
            messages.success(
                request, 
                f"✅ Purchase Order #{purchase_order.po_number} created successfully! Note: Supplier does not have an email address."
            )

        return redirect('purchase_orders_list')
    
    # If GET request, redirect to the list page
    return redirect('approved_purchase_requests')




# ============================================
# PURCHASE ORDER MANAGEMENT
# ============================================
def purchase_orders_list(request):
    if 'acc_id' not in request.session:
        messages.error(request, "Please log in first.")
        return redirect('admin_login')

    current_admin = Admin.objects.get(acc_id=request.session['acc_id'])
    
    # Get all purchase orders
    purchase_orders = PurchaseOrder.objects.all().order_by('-created_date')
    
    # GET ALL SUPPLIERS - Add this
    suppliers = Supplier.objects.all().order_by('name')
    
    context = {
        'purchase_orders': purchase_orders,
        'current_admin': current_admin,
        'today': timezone.now().date(),
        'suppliers': suppliers,  # ADD THIS LINE
    }
    
    return render(request, 'liong/purchase_orders.html', context)

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

from django.template.loader import render_to_string
from django.utils.html import strip_tags

def send_rejection_notification_email(receiving, disposition, admin):
    """Send HTML email to supplier about rejected items using template"""
    try:
        supplier = receiving.po.supplier
        if not supplier.email:
            return False, "Supplier has no email address"
        
        # Get all rejected items for this receiving
        rejected_items = RejectedItem.objects.filter(receiving=receiving, is_resolved=False)
        total_rejected = sum(item.quantity for item in rejected_items)
        
        if total_rejected == 0:
            return False, "No rejected items found"
        
        # Prepare email context
        context = {
            'company_name': settings.COMPANY_NAME,
            'receiving': receiving,
            'po': receiving.po,
            'supplier': supplier,
            'rejected_items': rejected_items,
            'total_rejected_qty': total_rejected,
            'total_rejected_value': sum(item.quantity * item.po_item.unit_price for item in rejected_items),
            'rejection_disposition': disposition,
            'sent_by': admin,
            'date': timezone.now(),
        }
        
        # Render HTML email from template
        html_message = render_to_string('liong/emails/rejection_notification_email.html', context)
        plain_message = strip_tags(html_message)  # Create plain text version
        
        # Send email with HTML content
        send_mail(
            subject=f"Quality Check Results - Rejected Items from PO #{receiving.po.po_number}",
            message=plain_message,  # Plain text version
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[supplier.email],
            html_message=html_message,  # HTML version
            fail_silently=False,
        )
        
        return True, "Rejection notification email sent successfully"
        
    except Exception as e:
        return False, f"Failed to send email: {str(e)}"
    
def quality_check_receiving(request, receiving_id):
    """Step 2: Quality check - ONLY AFTER APPROVAL DO ITEMS ENTER INVENTORY"""
    if 'acc_id' not in request.session:
        return redirect('admin_login')

    try:
        current_admin = Admin.objects.get(acc_id=request.session['acc_id'])
    except Admin.DoesNotExist:
        messages.error(request, "Admin not found.")
        return redirect('admin_login')
    
    if current_admin.role not in ['inventory_admin', 'super_admin']:
        messages.error(request, "Only inventory can perform quality checks.")
        return redirect('purchase_orders_list')

    receiving = get_object_or_404(PurchaseReceiving.objects.select_related(
        'po', 'po__supplier'
    ).prefetch_related(
        'receiveditem_set__po_item__product'
    ), receiving_id=receiving_id)

    if receiving.overall_status != 'pending_qc':
        messages.error(request, 
            f"This receiving has already been processed. "
            f"Status: {receiving.get_overall_status_display()}"
        )
        return redirect('purchase_orders_list')

    # =========== POST REQUEST (form submission) ===========
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action != 'complete_qc':
            messages.error(request, "Invalid action.")
            return redirect('quality_check_receiving', receiving_id=receiving_id)
        
        disposition = request.POST.get('rejection_disposition', 'return')
        
        try:
            with transaction.atomic():
                has_rejections = False
                total_accepted = Decimal('0')
                total_rejected = Decimal('0')
                qc_errors = []
                
                for received_item in receiving.receiveditem_set.all():
                    accepted_qty_str = request.POST.get(f'accepted_qty_{received_item.received_item_id}', '0')
                    accepted_qty = Decimal(accepted_qty_str) if accepted_qty_str else Decimal('0')
                    
                    if accepted_qty < 0:
                        qc_errors.append(f"Accepted quantity for {received_item.po_item.product.name} cannot be negative.")
                    
                    if accepted_qty > received_item.quantity_received:
                        qc_errors.append(
                            f"Accepted quantity for {received_item.po_item.product.name} "
                            f"({accepted_qty}) exceeds physically received quantity ({received_item.quantity_received})."
                        )
                    
                    rejected_qty = received_item.quantity_received - accepted_qty
                    
                    if rejected_qty > 0:
                        rejection_reason = request.POST.get(
                            f'rejection_reason_{received_item.received_item_id}', ''
                        ).strip()
                        
                        if not rejection_reason:
                            qc_errors.append(f"Rejection reason required for {received_item.po_item.product.name}")
                        
                        has_rejections = True
                        total_rejected += rejected_qty
                    
                    total_accepted += accepted_qty
                
                if qc_errors:
                    raise ValueError("\n".join(qc_errors))
                
                quality_check_data = {
                    'receiving': receiving,
                    'checker': current_admin,
                    'overall_status': 'accepted' if not has_rejections else 'rejected',
                    'notes': request.POST.get('quality_notes', '').strip(),
                    'rejection_disposition': disposition,
                }
                
                quality_check = QualityCheck.objects.create(**quality_check_data)
                
                for received_item in receiving.receiveditem_set.all():
                    accepted_qty_str = request.POST.get(f'accepted_qty_{received_item.received_item_id}', '0')
                    accepted_qty = Decimal(accepted_qty_str) if accepted_qty_str else Decimal('0')
                    rejected_qty = received_item.quantity_received - accepted_qty
                    
                    received_item.quantity_accepted = accepted_qty
                    received_item.quantity_rejected = rejected_qty
                    received_item.quality_checker = current_admin
                    received_item.quality_check_date = timezone.now()
                    
                    if rejected_qty > 0:
                        rejection_reason = request.POST.get(
                            f'rejection_reason_{received_item.received_item_id}', ''
                        ).strip()
                        if hasattr(received_item, 'rejection_reason'):
                            received_item.rejection_reason = rejection_reason
                        
                        rejection_details = request.POST.get(
                            f'rejection_details_{received_item.received_item_id}', ''
                        ).strip()
                        if hasattr(received_item, 'rejection_details'):
                            received_item.rejection_details = rejection_details
                    
                    received_item.save()
                    
                    po_item = received_item.po_item
                    if rejected_qty > 0:
                        if accepted_qty > 0:
                            po_item.quality_status = 'partial'
                        else:
                            po_item.quality_status = 'failed'
                    else:
                        po_item.quality_status = 'passed'
                    po_item.save()
                    
                    if rejected_qty > 0:
                        rejected_item_data = {
                            'receiving': receiving,
                            'po_item': received_item.po_item,
                            'quantity': rejected_qty,
                            'reason': rejection_reason if rejected_qty > 0 else '',
                            'disposition': disposition,
                            'is_resolved': False,
                        }
                        
                        RejectedItem.objects.create(**rejected_item_data)
                
                receiving.overall_status = 'complete'
                if hasattr(receiving, 'quality_check_completed'):
                    receiving.quality_check_completed = timezone.now()
                
                receiving.save()
                
                if total_accepted > 0:
                    success, message = add_accepted_items_to_inventory(receiving, current_admin)
                    if not success:
                        messages.warning(request, f"QC completed but inventory update had issues: {message}")
                else:
                    messages.warning(request, 
                        f"⚠️ Quality check completed but NO items were accepted. "
                        f"All {total_rejected} units were rejected."
                    )
                
                # =========== EMAIL SENDING GOES HERE ===========
                if has_rejections and total_rejected > 0:
                    handle_rejected_items_disposition(receiving, disposition, current_admin)
                    
                    # Send rejection notification email
                    email_success, email_message = send_rejection_notification_email(
                        receiving, 
                        disposition,
                        current_admin
                    )
                    
                    if email_success:
                        messages.info(request, f"📧 Rejection notification sent to supplier.")
                    else:
                        messages.warning(request, f"⚠️ Rejection notification email failed: {email_message}")
                
                po_items = receiving.po.purchaseorderitem_set.all()
                all_items_qc_completed = all(
                    item.received_quantity > 0 and item.quality_status in ['passed', 'partial', 'failed']
                    for item in po_items
                )
                
                old_po_status = receiving.po.status
                
                if all_items_qc_completed:
                    fully_received_and_passed = all(
                        item.received_quantity >= item.quantity and item.quality_status == 'passed'
                        for item in po_items
                    )
                    
                    if fully_received_and_passed:
                        receiving.po.status = 'received'
                        receiving.po.completed_date = timezone.now()
                    else:
                        receiving.po.status = 'partially_received'
                else:
                    receiving.po.status = 'partially_received'
                
                receiving.po.save()
                
                PurchaseOrderHistory.objects.create(
                    po=receiving.po,
                    old_status=old_po_status,
                    new_status=receiving.po.status,
                    changed_by=current_admin,
                    notes=f"✅ Quality check COMPLETED for Receiving #{receiving.receiving_number}. "
                          f"✅ Accepted to inventory: {total_accepted} units. "
                          f"❌ Rejected: {total_rejected} units. "
                          f"Disposition: {disposition}."
                )
            
            if total_accepted > 0:
                if has_rejections:
                    messages.success(request, 
                        f"✅ Quality check completed! "
                        f"✅ {total_accepted} units ACCEPTED and ADDED TO INVENTORY. "
                        f"❌ {total_rejected} units rejected ({disposition})."
                    )
                else:
                    messages.success(request, 
                        f"✅ Quality check PASSED! "
                        f"✅ All {total_accepted} units ACCEPTED and ADDED TO INVENTORY."
                    )
            else:
                messages.warning(request, 
                    f"⚠️ Quality check completed but NO items accepted to inventory. "
                    f"All {total_rejected} units were rejected ({disposition})."
                )
            
            return redirect('purchase_orders_list')
            
        except ValueError as e:
            messages.error(request, f"❌ Quality check validation failed: {str(e)}")
            return redirect('quality_check_receiving', receiving_id=receiving_id)
        except Exception as e:
            messages.error(request, f"❌ Error during quality check: {str(e)}")
            return redirect('quality_check_receiving', receiving_id=receiving_id)

    # =========== GET REQUEST (just showing the form) ===========
    # For GET requests, we don't send emails or check for rejections
    return render(request, 'liong/quality_check_receiving.html', {
        'receiving': receiving,
        'current_admin': current_admin
    })


def receive_purchase_order(request, po_id):
    """Step 1: Initial receiving of goods - NO INVENTORY UPDATE HERE"""
    if 'acc_id' not in request.session:
        return redirect('admin_login')

    try:
        current_admin = Admin.objects.get(acc_id=request.session['acc_id'])
    except Admin.DoesNotExist:
        messages.error(request, "Admin not found.")
        return redirect('admin_login')
    
    if current_admin.role not in ['inventory_admin', 'super_admin']:
        messages.error(request, "Only inventory can receive goods.")
        return redirect('purchase_orders_list')

    purchase_order = get_object_or_404(PurchaseOrder.objects.select_related(
        'supplier'
    ).prefetch_related(
        'purchaseorderitem_set__product'
    ), po_id=po_id)

    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action not in ['receive_partial', 'receive_complete']:
            messages.error(request, "Invalid action.")
            return redirect('receive_purchase_order', po_id=po_id)
        
        invoice_number = request.POST.get('invoice_number', '').strip()
        if not invoice_number:
            messages.error(request, "Invoice number is required.")
            return redirect('receive_purchase_order', po_id=po_id)
        
        has_received_items = False
        received_items_data = []
        total_physically_received = Decimal('0')
        
        for item in purchase_order.purchaseorderitem_set.all():
            received_qty_str = request.POST.get(f'received_qty_{item.po_item_id}', '0')
            received_qty = Decimal(received_qty_str) if received_qty_str else Decimal('0')
            
            if received_qty < 0:
                messages.error(request, f"Quantity for {item.product.name} cannot be negative.")
                return redirect('receive_purchase_order', po_id=po_id)
            
            if received_qty > item.remaining_quantity:
                messages.error(request, 
                    f"Quantity for {item.product.name} ({received_qty}) exceeds remaining quantity ({item.remaining_quantity})."
                )
                return redirect('receive_purchase_order', po_id=po_id)
            
            if received_qty > 0:
                has_received_items = True
                total_physically_received += received_qty
                received_items_data.append({
                    'item': item,
                    'quantity': received_qty
                })
        
        if not has_received_items:
            messages.error(request, "Please enter received quantity for at least one item.")
            return redirect('receive_purchase_order', po_id=po_id)
        
        try:
            with transaction.atomic():
                receive_date_str = request.POST.get('receive_date')
                if receive_date_str:
                    try:
                        receive_date = datetime.strptime(receive_date_str, '%Y-%m-%d').date()
                    except ValueError:
                        receive_date = timezone.now().date()
                else:
                    receive_date = timezone.now().date()
                
                receiving_number = f"REC{timezone.now().strftime('%Y%m%d%H%M%S')}"
                
                receiving = PurchaseReceiving.objects.create(
                    po=purchase_order,
                    received_by=current_admin,
                    invoice_number=invoice_number,
                    delivery_note_number=request.POST.get('delivery_note_number', '').strip(),
                    carrier=request.POST.get('carrier', '').strip(),
                    quality_check_notes=request.POST.get('quality_check_notes', '').strip(),
                    overall_status='pending_qc',
                    receiving_number=receiving_number,
                    receive_date=receive_date
                )
                
                for data in received_items_data:
                    item = data['item']
                    received_qty = data['quantity']
                    
                    ReceivedItem.objects.create(
                        receiving=receiving,
                        po_item=item,
                        quantity_received=received_qty,
                        quantity_accepted=0,
                        quantity_rejected=0,
                        quality_checker=None,
                        quality_check_date=None
                    )
                    
                    item.received_quantity += received_qty
                    item.quality_status = 'pending'
                    item.save()
                
                old_po_status = purchase_order.status
                purchase_order.status = 'partially_received'
                purchase_order.save()
                
                receiving.save()
                
                PurchaseOrderHistory.objects.create(
                    po=purchase_order,
                    old_status=old_po_status,
                    new_status=purchase_order.status,
                    changed_by=current_admin,
                    notes=f"Goods physically received (NOT in inventory yet). "
                          f"Receiving #{receiving.receiving_number}. "
                          f"Physically received: {total_physically_received} units. "
                          f"Invoice: {invoice_number}. "
                          f"PENDING QUALITY CHECK APPROVAL."
                )
            
            messages.success(request, 
                f"✅ Goods physically received! Receiving #: {receiving.receiving_number}. "
                f"📋 {total_physically_received} units pending quality check. "
                f"⚠️ Items NOT added to inventory until QC approval."
            )
            
            return redirect('quality_check_receiving', receiving_id=receiving.receiving_id)
            
        except Exception as e:
            messages.error(request, f"❌ Error receiving goods: {str(e)}")
            return redirect('receive_purchase_order', po_id=po_id)

    return render(request, 'liong/receive_purchase_order.html', {
        'purchase_order': purchase_order,
        'current_admin': current_admin,
        'today': timezone.now().date()
    })

def stock_in_accepted_items(receiving, admin):
    """Stock in only the accepted items from a purchase order"""
    try:
        for received_item in receiving.receiveditem_set.all():
            if received_item.quantity_accepted > 0:
                product = received_item.po_item.product
                accepted_qty = received_item.quantity_accepted
                
                # Create stock in record
                StockIn.objects.create(
                    product=product,
                    unit=product.unit,
                    quantity=accepted_qty,
                    date_in=timezone.now().date(),
                    acc=admin
                )
                
                # Update product stock
                product.stock += int(accepted_qty)  # Assuming stock is integer
                product.save()
                
                # Update or create inventory balance
                balance, created = InventoryBalance.objects.get_or_create(
                    product=product,
                    defaults={
                        'unit': product.unit,
                        'opening_inventory': product.stock,
                        'quantity_unit': product.stock,
                        'min_stock': 0,
                        'procurement_suggestion': 0
                    }
                )
                if not created:
                    balance.quantity_unit = product.stock
                    balance.save()
    except Exception as e:
        print(f"Error stocking in accepted items: {e}")

def add_accepted_items_to_inventory(receiving, admin):
    """Add QC-approved items to inventory - ONLY CALLED AFTER QC APPROVAL"""
    try:
        total_accepted_units = Decimal('0')
        
        for received_item in receiving.receiveditem_set.filter(quantity_accepted__gt=0):
            product = received_item.po_item.product
            accepted_qty = received_item.quantity_accepted
            
            # Convert to Decimal if needed
            if not isinstance(accepted_qty, Decimal):
                accepted_qty = Decimal(str(accepted_qty))
            
            # Update product stock - Use 'stock' field
            product.stock += accepted_qty
            product.save()
            
            total_accepted_units += accepted_qty
            
            # Update InventoryBalance
            try:
                inv_balance, created = InventoryBalance.objects.get_or_create(
                    product=product,
                    defaults={
                        'unit': product.unit,
                        'opening_inventory': Decimal('0'),
                        'quantity_unit': accepted_qty,
                        'quantity_meters': Decimal('0'),
                        'quantity_klg': Decimal('0'),
                        'min_stock': Decimal('0'),
                        'procurement_suggestion': Decimal('0'),
                    }
                )
                
                if not created:
                    inv_balance.quantity_unit += accepted_qty
                    inv_balance.save()
                    
            except:
                pass  # Skip if InventoryBalance doesn't exist or fails
            
            # Create StockIn record
            try:
                StockIn.objects.create(
                    product=product,
                    unit=product.unit,
                    quantity=accepted_qty,
                    quantity_meters=Decimal('0'),
                    quantity_klg=Decimal('0'),
                    date_in=timezone.now().date(),
                    acc=admin
                )
            except:
                pass  # Skip if StockIn creation fails
        
        return True, f"Successfully added {total_accepted_units} units to inventory"
        
    except Exception as e:
        return False, str(e)


def handle_rejected_items_disposition(receiving, disposition, admin):
    """Handle rejected items based on disposition type"""
    try:
        # Update receiving record
        receiving.rejection_disposition = disposition
        receiving.save()
        
        # Update rejected items in RejectedItem model
        for received_item in receiving.receiveditem_set.filter(quantity_rejected__gt=0):
            RejectedItem.objects.create(
                receiving=receiving,
                po_item=received_item.po_item,
                quantity=received_item.quantity_rejected,
                reason=received_item.rejection_reason or 'other',
                details=received_item.rejection_details or '',
                disposition=disposition,
                disposition_date=timezone.now(),
                disposed_by=admin,
                is_resolved=False
            )
        
        return True, f"Rejected items marked with disposition: {disposition}"
        
    except Exception as e:
        return False, str(e)
    

def get_receiving_details(request, receiving_id):
    """API endpoint to get receiving details"""
    if 'acc_id' not in request.session:
        return JsonResponse({'error': 'Not authenticated'}, status=401)
    
    receiving = get_object_or_404(PurchaseReceiving, receiving_id=receiving_id)
    
    data = {
        'receiving_id': receiving.receiving_id,
        'receiving_number': receiving.receiving_number,
        'po_number': receiving.po.po_number,
        'supplier_name': receiving.po.supplier.name,
        'receive_date': receiving.receive_date.strftime('%Y-%m-%d'),
        'status': receiving.get_overall_status_display(),
        'items': []
    }
    
    for received_item in receiving.receiveditem_set.all():
        data['items'].append({
            'item_id': received_item.received_item_id,
            'product_name': received_item.po_item.product.name,
            'quantity_received': float(received_item.quantity_received),
            'quantity_accepted': float(received_item.quantity_accepted),
            'quantity_rejected': float(received_item.quantity_rejected),
            'unit': received_item.po_item.product.unit,
            'rejection_reason': received_item.rejection_reason or '',
            'quality_checker': received_item.quality_checker.name if received_item.quality_checker else '',
            'quality_check_date': received_item.quality_check_date.strftime('%Y-%m-%d %H:%M') if received_item.quality_check_date else ''
        })
    
    return JsonResponse(data)

def update_rejection_disposition(request, rejected_id):
    """API endpoint to update rejection disposition"""
    if 'acc_id' not in request.session:
        return JsonResponse({'error': 'Not authenticated'}, status=401)
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        current_admin = Admin.objects.get(acc_id=request.session['acc_id'])
    except Admin.DoesNotExist:
        return JsonResponse({'error': 'Admin not found'}, status=404)
    
    rejected_item = get_object_or_404(RejectedItem, rejected_id=rejected_id)
    disposition = request.POST.get('disposition')
    notes = request.POST.get('notes', '')
    
    if disposition not in ['return', 'keep_as_rejected', 'destroy', 'replace']:
        return JsonResponse({'error': 'Invalid disposition'}, status=400)
    
    try:
        with transaction.atomic():
            rejected_item.disposition = disposition
            rejected_item.disposition_date = timezone.now()
            rejected_item.disposed_by = current_admin
            rejected_item.disposition_notes = notes
            
            if disposition == 'keep_as_rejected':
                # Check if already in rejected stock
                if not RejectedStock.objects.filter(rejected_item=rejected_item).exists():
                    RejectedStock.objects.create(
                        rejected_item=rejected_item,
                        product=rejected_item.po_item.product,
                        quantity=rejected_item.quantity,
                        batch_number=f"REJ-{rejected_item.receiving.receiving_number}-{timezone.now().strftime('%Y%m%d')}",
                        location='Quarantine Area',
                        status='quarantine',
                        notes=notes or f"Rejected from receiving #{rejected_item.receiving.receiving_number}"
                    )
                    rejected_item.is_resolved = True
            
            rejected_item.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Disposition updated successfully',
                'rejected_id': rejected_item.rejected_id,
                'disposition': disposition,
                'disposition_date': rejected_item.disposition_date.strftime('%Y-%m-%d %H:%M')
            })
            
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


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
    """Mark requisition as ready for pickup - Check availability and reserve but DON'T deduct stock"""
    if 'acc_id' not in request.session:
        messages.error(request, "Please log in first.")
        return redirect('admin_login')

    try:
        current_admin = Admin.objects.get(acc_id=request.session['acc_id'])
    except Admin.DoesNotExist:
        messages.error(request, "Admin not found.")
        return redirect('admin_login')
    
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
    unavailable_items = []
    
    for item in items:
        approved_qty = item.approved_qty or item.quantity
        
        try:
            inv_balance = InventoryBalance.objects.get(product=item.product)
            if inv_balance.quantity_unit < approved_qty:
                unavailable_items.append({
                    'product': item.product.name,
                    'available': inv_balance.quantity_unit,
                    'needed': approved_qty
                })
        except InventoryBalance.DoesNotExist:
            messages.error(request, f"No inventory record for {item.product.name}")
            return redirect('ready_for_pickup_requisitions')
    
    if unavailable_items:
        error_msg = "Insufficient stock for: "
        error_msg += ", ".join([f"{item['product']} (Available: {item['available']}, Needed: {item['needed']})" 
                                for item in unavailable_items])
        messages.error(request, error_msg)
        return redirect('ready_for_pickup_requisitions')
    
    try:
        with transaction.atomic():
            # Reserve stock (MARK as reserved but DON'T deduct from inventory yet)
            for item in items:
                approved_qty = item.approved_qty or item.quantity
                
                # Mark as reserved in the requisition item
                item.reserved_qty = approved_qty
                item.save()
                
                # Create stock out record with status='reserved' (but not deducted from inventory)
                StockOut.objects.create(
                    product=item.product,
                    unit=item.product.unit,
                    quantity=approved_qty,
                    date_out=timezone.now().date(),
                    acc=current_admin,
                    purpose=f"Reserved for Requisition #{requisition.requisition_id} - {requisition.employee.employee_name}",
                    status='reserved',  # This is just reserved, not deducted
                    requisition=requisition,
                    notes=f"Ready for pickup - Reserved for {requisition.employee.employee_name}. "
                          f"Stock will be deducted when employee receives items."
                )
            
            # Update requisition status
            requisition.status = "Ready for Pickup"
            requisition.pickup_ready_date = timezone.now()
            requisition.save()
            
            # Create status history
            RequisitionStatusHistory.objects.create(
                requisition=requisition,
                old_status='Pending Purchase' if requisition.status == 'Pending Purchase' else 'Purchased',
                new_status='Ready for Pickup',
                changed_by=current_admin
            )
            
            messages.success(request, 
                f"✅ Requisition #{requisition.requisition_id} marked as Ready for Pickup. "
                f"Stock has been RESERVED for {requisition.employee.employee_name}. "
                f"Stock will be deducted when employee receives the items."
            )
            
    except Exception as e:
        messages.error(request, f"❌ Error marking requisition as ready: {str(e)}")
    
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
    """Use correct template path"""
    print(f"=== DEBUG: Looking for liong/partials/purchase_order_detail.html ===")
    
    try:
        from .models import PurchaseOrder, PurchaseOrderItem, Admin
        from django.utils import timezone
        
        # Get data
        if 'acc_id' not in request.session:
            return HttpResponse("Not logged in", status=401)
        
        current_admin = Admin.objects.get(acc_id=request.session['acc_id'])
        purchase_order = PurchaseOrder.objects.get(pk=po_id)
        
        # Get items
        try:
            if hasattr(purchase_order, 'purchaseorderitem_set'):
                items = purchase_order.purchaseorderitem_set.all()
            else:
                items = PurchaseOrderItem.objects.filter(po=purchase_order)
        except:
            items = []
        
        context = {
            'purchase_order': purchase_order,
            'current_admin': current_admin,
            'items': items,
            'today': timezone.now().date(),
        }
        
        print(f"✓ Data loaded for PO #{purchase_order.po_number}")
        print(f"✓ Template: liong/partials/purchase_order_detail.html")
        
        # Try the correct template
        from django.template.loader import render_to_string
        try:
            html = render_to_string('liong/partials/purchase_order_detail.html', context)
            print(f"✓ Template rendered: {len(html)} chars")
            return HttpResponse(html)
        except Exception as e:
            print(f"✗ Template error: {type(e).__name__}: {e}")
            
            # Show what we tried to render
            return HttpResponse(f"""
            <div class="p-6">
                <h3 class="text-red-500">Template Error</h3>
                <p><strong>Template:</strong> liong/partials/purchase_order_detail.html</p>
                <p><strong>Error:</strong> {type(e).__name__}: {str(e)}</p>
                
                <div class="mt-4 p-4 bg-gray-800 rounded">
                    <h4 class="font-semibold">Available Data:</h4>
                    <pre class="text-sm">
PO: {purchase_order.po_number}
Status: {purchase_order.status}
Supplier: {purchase_order.supplier.name if purchase_order.supplier else 'None'}
Items: {len(items)}
Created: {purchase_order.created_date}
                    </pre>
                </div>
                
                <button onclick="closePOModal()" class="btn btn-secondary mt-4">Close</button>
            </div>
            """, status=500)
            
    except Exception as e:
        print(f"=== ERROR ===")
        import traceback
        traceback.print_exc()
        
        return HttpResponse(f"""
        <div class="p-6 text-center">
            <h3 class="text-red-500">Error: {type(e).__name__}</h3>
            <p>{str(e)[:100]}</p>
            <button onclick="closePOModal()" class="btn btn-secondary mt-4">Close</button>
        </div>
        """, status=500)




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

@transaction.atomic
def mark_as_received(request, requisition_id):
    """Mark a requisition as received by employee - NOW DEDUCTS STOCK"""
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
            
            # Get requisition items
            items = Requisition_Item.objects.filter(requisition=requisition).select_related('product')
            
            with transaction.atomic():
                # Deduct stock from inventory
                for item in items:
                    approved_qty = item.approved_qty or item.quantity
                    
                    # Update inventory balance - DEDUCT STOCK HERE
                    inv_balance = InventoryBalance.objects.get(product=item.product)
                    inv_balance.quantity_unit -= approved_qty
                    inv_balance.save()
                    
                    # Update Products stock
                    product = item.product
                    product.stock -= approved_qty
                    product.save()
                    
                    # Update StockOut record to change status from 'reserved' to 'issued'
                    stock_out_record = StockOut.objects.filter(
                        requisition=requisition,
                        product=item.product,
                        status='reserved'
                    ).first()
                    
                    if stock_out_record:
                        stock_out_record.status = 'issued'
                        stock_out_record.notes = f"Received by employee on {timezone.now().strftime('%Y-%m-%d %H:%M')}"
                        stock_out_record.save()
                    
                    # Mark as issued in requisition item
                    item.issued_qty = approved_qty
                    item.fulfilled_qty = approved_qty
                    item.save()
                
                # Update requisition status
                old_status = requisition.status
                requisition.status = 'Received'
                requisition.received_date = timezone.now()
                requisition.save()
                
                # Create status history
                RequisitionStatusHistory.objects.create(
                    requisition=requisition,
                    old_status=old_status,
                    new_status='Received',
                    changed_by=admin
                )
                
                messages.success(request, 
                    f"✅ Requisition #{requisition_id} marked as received. "
                    f"Stock has been deducted from inventory."
                )
            
        except InventoryBalance.DoesNotExist as e:
            messages.error(request, f"❌ Inventory record not found: {str(e)}")
        except Admin.DoesNotExist:
            messages.error(request, "Session expired. Please log in again.")
            request.session.flush()
            return redirect('admin_login')
        except Exception as e:
            messages.error(request, f"❌ Error marking requisition as received: {str(e)}")
    
    return redirect('request_history')


















# ============================================
# REPORTS SYSTEM - UPDATED WITH FIXED IMPORTS
# ============================================
from django.db.models import Count, Sum, Avg, Min, Max, Q, F
from django.db.models.functions import TruncDay, TruncWeek, TruncMonth, TruncYear
from datetime import datetime, timedelta
import csv
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.db import transaction

def reports_main(request):
    """Main reports page with enhanced statistics and graphs"""
    if 'acc_id' not in request.session:
        messages.error(request, "Please log in first.")
        return redirect('admin_login')

    current_admin = Admin.objects.get(acc_id=request.session['acc_id'])
    
    # Only allow certain roles to view reports
    allowed_roles = ['super_admin', 'inventory_admin']
    if current_admin.role not in allowed_roles:
        messages.error(request, "You don't have permission to view reports.")
        return redirect('adminDashboard')
    
    # Get current date for filtering
    today = timezone.now().date()
    start_of_month = today.replace(day=1)
    start_of_week = today - timedelta(days=today.weekday())
    
    # Current statistics for dashboard
    context = {
        'current_admin': current_admin,
        'today': today,
        'stats': get_current_stats(),
        'employee_stats': get_employee_stats(),
        'inventory_stats': get_inventory_stats(),
        'time_stats': get_time_stats(start_of_week, start_of_month),
        'status_stats': get_status_stats(),
        'financial_stats': get_financial_stats(start_of_month),
        'trends_stats': get_trends_stats(),  # Make sure this is included
    }
    return render(request, 'liong/reports.html', context)

def get_chart_data():
    """Get data specifically formatted for charts"""
    today = timezone.now().date()
    thirty_days_ago = today - timedelta(days=30)
    
    # Daily requisitions for line chart
    daily_requisitions = []
    for i in range(29, -1, -1):
        date = today - timedelta(days=i)
        count = Requisition.objects.filter(
            date_requested__date=date
        ).count()
        daily_requisitions.append({
            'date': date.strftime('%b %d'),
            'count': count
        })
    
    # Status distribution for pie chart
    status_distribution = Requisition.objects.values('status').annotate(
        count=Count('requisition_id')
    ).order_by('-count')
    
    # Top 10 products by requests
    top_products = Requisition_Item.objects.values(
        'product__name'
    ).annotate(
        total_requests=Count('requisition'),
        total_quantity=Sum('quantity')
    ).order_by('-total_quantity')[:10]
    
    # Monthly trend (last 6 months)
    monthly_trend = []
    for i in range(5, -1, -1):
        month_date = today.replace(day=1) - timedelta(days=30*i)
        month_start = month_date.replace(day=1)
        if i == 0:
            month_end = today
        else:
            next_month = month_date.replace(day=28) + timedelta(days=4)
            month_end = next_month.replace(day=1) - timedelta(days=1)
        
        month_count = Requisition.objects.filter(
            date_requested__range=[month_start, month_end]
        ).count()
        
        monthly_trend.append({
            'month': month_date.strftime('%b'),
            'count': month_count
        })
    
    # Employee performance data
    employee_data = []
    for emp in Employee.objects.filter(status='active').annotate(
        total_requests=Count('requisition'),
        completed_requests=Count('requisition', filter=Q(requisition__status='Received'))
    ).order_by('-total_requests')[:8]:
        if emp.total_requests > 0:
            completion_rate = (emp.completed_requests / emp.total_requests) * 100
        else:
            completion_rate = 0
        
        employee_data.append({
            'name': emp.employee_name,
            'requests': emp.total_requests,
            'completion_rate': round(completion_rate, 1)
        })
    
    return {
        'daily_requisitions': daily_requisitions,
        'status_distribution': list(status_distribution),
        'top_products': list(top_products),
        'monthly_trend': monthly_trend,
        'employee_data': employee_data,
    }


def get_current_stats():
    """Get current system statistics"""
    today = timezone.now().date()
    
    return {
        'total_requisitions': Requisition.objects.count(),
        'pending_approval': Requisition.objects.filter(status='Pending Approval').count(),
        'ready_for_pickup': Requisition.objects.filter(status='Ready for Pickup').count(),
        'pending_purchase': PurchaseOrder.objects.filter(
            status__in=['draft', 'sent', 'ordered']
        ).count(),
        'active_employees': Employee.objects.filter(status='active').count(),
        'total_products': Products.objects.count(),
        'completed_today': Requisition.objects.filter(
            status='Received',
            date_requested__date=today
        ).count(),
        'low_stock': InventoryBalance.objects.filter(
            quantity_unit__lt=F('min_stock')
        ).exclude(min_stock=0).count(),
    }


def get_inventory_stats():
    """Get inventory statistics using fixed threshold of 5 for low stock"""
    inventory_items = InventoryBalance.objects.select_related('product').all()
    
    # Categorize inventory using fixed threshold
    low_stock_items = []
    out_of_stock_items = []
    healthy_stock_items = []
    
    total_value = 0
    
    for item in inventory_items:
        # Calculate current value
        try:
            latest_price = PurchaseOrderItem.objects.filter(
                product=item.product
            ).order_by('-po__created_date').values_list('unit_price', flat=True).first()
            
            if latest_price:
                current_value = float(item.quantity_unit) * float(latest_price)
            else:
                current_value = 0
            total_value += current_value
            item.current_value = current_value
        except Exception as e:
            print(f"Error calculating value for {item.product.name}: {e}")
            current_value = 0
            item.current_value = 0
        
        # Calculate deficit for low stock items - using fixed threshold of 5
        current_stock = float(item.quantity_unit) if item.quantity_unit else 0
        LOW_STOCK_THRESHOLD = 5
        
        # Calculate deficit: how much below 5
        item.deficit = max(LOW_STOCK_THRESHOLD - current_stock, 0) if current_stock < LOW_STOCK_THRESHOLD else 0
        
        # Categorize: 
        # - 0 = out of stock
        # - 1-4 = low stock (below threshold of 5)
        # - 5+ = healthy stock
        if current_stock == 0:
            out_of_stock_items.append(item)
        elif 0 < current_stock < LOW_STOCK_THRESHOLD:
            low_stock_items.append(item)
        else:  # current_stock >= 5
            healthy_stock_items.append(item)
    
    # Stock movement (last 30 days)
    thirty_days_ago = timezone.now() - timedelta(days=30)
    
    stock_in_total = StockIn.objects.filter(
        date_in__gte=thirty_days_ago
    ).aggregate(total=Sum('quantity'))['total'] or 0
    
    stock_out_total = StockOut.objects.filter(
        date_out__gte=thirty_days_ago,
        status='issued'
    ).aggregate(total=Sum('quantity'))['total'] or 0
    
    stock_movement = {
        'stock_in': float(stock_in_total),
        'stock_out': float(stock_out_total),
    }
    
    return {
        'total_items': inventory_items.count(),
        'low_stock_count': len(low_stock_items),
        'out_of_stock_count': len(out_of_stock_items),
        'healthy_stock_count': len(healthy_stock_items),
        'total_value': round(total_value, 2),
        'stock_movement': stock_movement,
        'low_stock_items': low_stock_items[:10],
        'out_of_stock_items': out_of_stock_items[:10],
        'all_items': inventory_items,
    }



# Update the get_financial_stats function:
def get_financial_stats(start_of_month):
    """Get financial statistics (if available)"""
    # Purchase orders this month
    monthly_purchases = PurchaseOrder.objects.filter(
        created_date__gte=start_of_month
    ).aggregate(
        total=Sum('total_amount'),
        count=Count('po_id'),
        avg=Avg('total_amount')
    )
    
    # Top suppliers by spending - get supplier IDs and names with aggregates
    from django.db.models import Max
    
    top_suppliers_query = PurchaseOrder.objects.values(
        'supplier__supplier_id', 'supplier__name'
    ).annotate(
        total_spent=Sum('total_amount'),
        order_count=Count('po_id'),
        last_order_date=Max('created_date')
    ).order_by('-total_spent')[:10]
    
    
    # Convert QuerySet to list of dictionaries with proper structure
    top_suppliers = []
    for item in top_suppliers_query:
        # Get supplier name - handle None case
        supplier_name = item.get('supplier__name')
        
        # If supplier_name is None or empty, try to get it from Supplier model
        if not supplier_name and item.get('supplier__supplier_id'):
            try:
                supplier = Supplier.objects.get(supplier_id=item['supplier__supplier_id'])
                supplier_name = supplier.name
                print(f"DEBUG - Fetched supplier name from DB: {supplier_name}")
            except Supplier.DoesNotExist:
                supplier_name = "Unknown Supplier"
                print(f"DEBUG - Supplier not found: {item['supplier__supplier_id']}")
        
        # Calculate average order value
        avg_order = 0
        if item.get('order_count', 0) > 0 and item.get('total_spent'):
            avg_order = item['total_spent'] / item['order_count']
        
        top_suppliers.append({
            'supplier_name': supplier_name or "No Name",  # Ensure we always have a name
            'total_spent': item.get('total_spent') or 0,
            'order_count': item.get('order_count') or 0,
            'last_order_date': item.get('last_order_date'),
            'avg_order': avg_order
        })
    
    
    # Recent purchase orders (last 10)
    recent_purchases = PurchaseOrder.objects.select_related('supplier').order_by('-created_date')[:10]
    
    # Inventory valuation
    total_inventory_value = 0
    inventory_items = InventoryBalance.objects.all()
    
    for item in inventory_items:
        try:
            latest_price = PurchaseOrderItem.objects.filter(
                product=item.product
            ).order_by('-po__created_date').values_list('unit_price', flat=True).first()
            if latest_price:
                total_inventory_value += float(item.quantity_unit) * float(latest_price)
        except Exception as e:
            print(f"Error calculating inventory value: {e}")
            continue
    
    return {
        'monthly_purchases': monthly_purchases['total'] or 0,
        'avg_purchase_order': monthly_purchases['avg'] or 0,
        'total_orders': monthly_purchases['count'] or 0,
        'inventory_value': round(total_inventory_value, 2),
        'top_suppliers': top_suppliers,
        'recent_purchases': recent_purchases,
    }

# Update the get_employee_stats function to include inventory data:
def get_employee_stats():
    """Get employee statistics"""
    # Get all inventory items for template access
    all_inventory_items = InventoryBalance.objects.select_related('product').all()
    
    # Top 10 employees by number of requests
    top_employees = Employee.objects.filter(status='active').annotate(
        total_requests=Count('requisition'),
        approved_requests=Count('requisition', filter=Q(requisition__status='Approved')),
        completed_requests=Count('requisition', filter=Q(requisition__status='Received'))
    ).order_by('-total_requests')[:10]
    
    # Most requested items across all employees
    most_requested_items = Requisition_Item.objects.filter(
    product__in=StockIn.objects.values('product').distinct()
    ).values(
        'product__name',
        'product__product_id'  # Add product ID if you need it
    ).annotate(
        total_quantity=Sum('quantity'),
        request_count=Count('requisition')
    ).order_by('-total_quantity')[:10]
    
    # Employee performance metrics
    employee_performance = []
    for emp in Employee.objects.filter(status='active')[:5]:
        reqs = Requisition.objects.filter(employee=emp)
        if reqs.exists():
            approval_rate = (reqs.filter(status='Approved').count() / reqs.count()) * 100
            completion_rate = (reqs.filter(status='Received').count() / reqs.count()) * 100
        else:
            approval_rate = completion_rate = 0
        
        employee_performance.append({
            'name': emp.employee_name,
            'total_requests': reqs.count(),
            'approval_rate': round(approval_rate, 1),
            'completion_rate': round(completion_rate, 1),
            'status': emp.status
        })
    
    return {
        'top_employees': list(top_employees),
        'most_requested_items': list(most_requested_items),
        'employee_performance': employee_performance,
        'all_inventory_items': all_inventory_items,  # Add this
    }


def get_time_stats(start_of_week, start_of_month):
    """Get time-based statistics"""
    # Daily stats for last 7 days
    daily_stats = []
    for i in range(6, -1, -1):
        date = timezone.now().date() - timedelta(days=i)
        count = Requisition.objects.filter(
            date_requested__date=date
        ).count()
        
        daily_stats.append({
            'date': date.strftime('%a'),
            'full_date': date.strftime('%Y-%m-%d'),
            'count': count
        })
    
    # Weekly stats
    weekly_count = Requisition.objects.filter(
        date_requested__date__gte=start_of_week
    ).count()
    
    # Monthly stats
    monthly_count = Requisition.objects.filter(
        date_requested__date__gte=start_of_month
    ).count()
    
    # Status trend for the month
    monthly_trend = Requisition.objects.filter(
        date_requested__date__gte=start_of_month
    ).values('status').annotate(
        count=Count('requisition_id')
    ).order_by('-count')
    
    return {
        'daily_stats': daily_stats,
        'weekly_count': weekly_count,
        'monthly_count': monthly_count,
        'monthly_trend': list(monthly_trend),
        'avg_daily': round(monthly_count / max(timezone.now().date().day, 1), 1)
    }


def get_status_stats():
    """Get status-based statistics"""
    # All requisitions by status
    all_status = Requisition.objects.values('status').annotate(
        count=Count('requisition_id')
    ).order_by('-count')
    
    # Aging analysis - requisitions older than 7 days
    seven_days_ago = timezone.now() - timedelta(days=7)
    old_requisitions = Requisition.objects.filter(
        date_requested__lt=seven_days_ago
    ).exclude(status__in=['Received', 'Denied', 'Fulfilled']).count()
    
    # Ready for pickup details
    ready_items = Requisition.objects.filter(
        status='Ready for Pickup'
    ).select_related('employee').order_by('date_requested')[:10]
    
    # Pending approval details
    pending_items = Requisition.objects.filter(
        status='Pending Approval'
    ).select_related('employee').order_by('date_requested')[:10]
    
    return {
        'all_status': list(all_status),
        'old_requisitions': old_requisitions,
        'ready_items': list(ready_items),
        'pending_items': list(pending_items),
        'status_distribution': {item['status']: item['count'] for item in all_status}
    }



def get_report_data(request, report_type):
    """AJAX endpoint to get specific report data"""
    if 'acc_id' not in request.session:
        return JsonResponse({'error': 'Not authenticated'}, status=401)
    
    try:
        current_admin = Admin.objects.get(acc_id=request.session['acc_id'])
        allowed_roles = ['super_admin', 'inventory_admin']
        if current_admin.role not in allowed_roles:
            return JsonResponse({'error': 'Unauthorized'}, status=403)
        
        # Get filter parameters
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        
        data = {}
        
        if report_type == 'employee':
            # Get detailed employee data
            employees = Employee.objects.filter(status='active').annotate(
                total_requests=Count('requisition'),
                total_items=Sum('requisition__requisition_item__quantity')
            ).order_by('-total_requests')
            
            data = {
                'employees': list(employees.values('employee_name', 'total_requests', 'total_items')),
                'most_requested': list(Requisition_Item.objects.values(
                    'product__name'
                ).annotate(
                    total=Sum('quantity')
                ).order_by('-total')[:20])
            }
            
        elif report_type == 'inventory':
            # Get detailed inventory data
            inventory = InventoryBalance.objects.select_related('product').all()
            inventory_list = []
            
            for item in inventory:
                inventory_list.append({
                    'product': item.product.name,
                    'current_stock': float(item.quantity_unit),
                    'min_stock': float(item.min_stock),
                    'unit': item.unit,
                    'status': 'Low Stock' if item.min_stock > 0 and item.quantity_unit < item.min_stock else 
                             'Out of Stock' if item.quantity_unit == 0 else 'Healthy'
                })
            
            data = {'inventory': inventory_list}
            
        elif report_type == 'time':
            # Get time-based data
            today = timezone.now().date()
            if not start_date:
                start_date = today - timedelta(days=30)
            if not end_date:
                end_date = today
            
            # Daily counts
            daily_data = []
            try:
                current = datetime.strptime(str(start_date), '%Y-%m-%d').date()
                end = datetime.strptime(str(end_date), '%Y-%m-%d').date()
                
                while current <= end:
                    count = Requisition.objects.filter(
                        date_requested__date=current
                    ).count()
                    
                    daily_data.append({
                        'date': current.strftime('%Y-%m-%d'),
                        'count': count
                    })
                    
                    current += timedelta(days=1)
            except Exception as e:
                print(f"Error processing time data: {e}")
            
            data = {'daily_data': daily_data}
            
        elif report_type == 'status':
            # Get status details
            status_details = {}
            for status in ['Pending Approval', 'Approved', 'Ready for Pickup', 'Received', 'Denied']:
                items = Requisition.objects.filter(status=status)
                status_details[status] = {
                    'count': items.count(),
                    'items': list(items.values(
                        'requisition_id', 
                        'employee__employee_name',
                        'date_requested'
                    )[:10])
                }
            
            data = status_details
            
        elif report_type == 'financial':
            # Get financial data
            today = timezone.now().date()
            if not start_date:
                start_date = today - timedelta(days=30)
            if not end_date:
                end_date = today
            
            purchases = PurchaseOrder.objects.filter(
                created_date__date__range=[start_date, end_date]
            ).values('po_number', 'supplier__name', 'created_date', 'total_amount', 'status')
            
            total_amount = sum(p['total_amount'] for p in purchases if p['total_amount'])
            
            data = {
                'purchases': list(purchases),
                'total': total_amount
            }
        
        return JsonResponse(data)
        
    except Exception as e:
        print(f"Error in get_report_data: {e}")
        return JsonResponse({'error': str(e)}, status=500)


def export_report_csv(request, report_type):
    """Export report data to CSV"""
    if 'acc_id' not in request.session:
        return HttpResponse('Please log in first.', status=401)
    
    current_admin = Admin.objects.get(acc_id=request.session['acc_id'])
    
    if current_admin.role not in ['super_admin', 'inventory_admin']:
        return HttpResponse('Unauthorized', status=403)
    
    response = HttpResponse(content_type='text/csv')
    filename = f"{report_type}_report_{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    writer = csv.writer(response)
    
    if report_type == 'employee':
        writer.writerow(['Employee Name', 'Total Requests', 'Approved Requests', 
                        'Completed Requests', 'Total Items Requested'])
        
        employees = Employee.objects.filter(status='active').annotate(
            total_requests=Count('requisition'),
            approved_requests=Count('requisition', filter=Q(requisition__status='Approved')),
            completed_requests=Count('requisition', filter=Q(requisition__status='Received')),
            total_items=Sum('requisition__requisition_item__quantity')
        )
        
        for emp in employees:
            writer.writerow([
                emp.employee_name,
                emp.total_requests or 0,
                emp.approved_requests or 0,
                emp.completed_requests or 0,
                emp.total_items or 0
            ])
    
    elif report_type == 'inventory':
        writer.writerow(['Product Name', 'Current Stock', 'Minimum Stock', 
                        'Unit', 'Status', 'Last Updated'])
        
        items = InventoryBalance.objects.select_related('product').all()
        for item in items:
            status = 'Healthy'
            if item.quantity_unit == 0:
                status = 'Out of Stock'
            elif item.min_stock > 0 and item.quantity_unit < item.min_stock:
                status = 'Low Stock'
            
            writer.writerow([
                item.product.name,
                item.quantity_unit,
                item.min_stock,
                item.unit,
                status,
                item.last_updated.strftime('%Y-%m-%d %H:%M')
            ])
    
    elif report_type == 'requisitions':
        writer.writerow(['Requisition ID', 'Employee', 'Date Requested', 
                        'Status', 'Items Count', 'Remarks'])
        
        reqs = Requisition.objects.select_related('employee').all()
        for req in reqs:
            writer.writerow([
                req.requisition_id,
                req.employee.employee_name,
                req.date_requested.strftime('%Y-%m-%d %H:%M'),
                req.status,
                req.requisition_item_set.count(),
                req.remarks or ''
            ])
    
    elif report_type == 'purchases':
        writer.writerow(['PO Number', 'Supplier', 'Date', 'Status', 
                        'Total Amount', 'Items Count', 'Payment Terms'])
        
        pos = PurchaseOrder.objects.select_related('supplier').all()
        for po in pos:
            item_count = po.purchaseorderitem_set.count()
            writer.writerow([
                po.po_number,
                po.supplier.name,
                po.created_date.strftime('%Y-%m-%d'),
                po.get_status_display(),
                po.total_amount,
                item_count,
                po.payment_terms
            ])
    
    return response



def get_trends_stats():
    """Get trends and patterns for product requests"""
    today = timezone.now().date()
    thirty_days_ago = today - timedelta(days=30)
    ninety_days_ago = today - timedelta(days=90)
    
    # Top 15 most requested items in last 90 days
    # FIX: Accessing product__unit instead of trying to get it separately
    most_requested = Requisition_Item.objects.filter(
        requisition__date_requested__gte=ninety_days_ago
    ).values(
        'product__name', 
        'product__product_id',
        'product__unit'  # ADD THIS - product has unit field
    ).annotate(
        total_requests=Count('requisition'),
        total_quantity=Sum('quantity'),
        avg_per_request=Avg('quantity'),
        latest_request=Max('requisition__date_requested')
    ).order_by('-total_quantity')[:15]
    
    # Add inventory data and calculate trends
    trending_items = []
    for item in most_requested:
        product_id = item['product__product_id']
        
        # Get inventory data
        try:
            inventory = InventoryBalance.objects.get(product_id=product_id)
            current_stock = float(inventory.quantity_unit)
            min_stock = float(inventory.min_stock)
            
            # Calculate consumption rate (per week)
            weekly_consumption = Requisition_Item.objects.filter(
                product_id=product_id,
                requisition__date_requested__gte=thirty_days_ago
            ).aggregate(total=Sum('quantity'))['total'] or 0
            
            weekly_consumption = float(weekly_consumption) / 4  # Approximate weekly
            
            # Calculate weeks of stock remaining
            if weekly_consumption > 0:
                weeks_remaining = current_stock / weekly_consumption
            else:
                weeks_remaining = float('inf') if current_stock > 0 else 0
            
            # Determine trend status
            if weeks_remaining < 1:
                trend_status = 'critical'
                trend_text = 'Critical - Restock immediately'
                color_class = 'status-critical'  # Changed from status-denied
            elif weeks_remaining < 2:
                trend_status = 'high'
                trend_text = 'High demand - Monitor closely'
                color_class = 'status-high'  # Changed from status-pending
            elif weeks_remaining < 4:
                trend_status = 'medium'
                trend_text = 'Steady demand'
                color_class = 'status-medium'  # Changed from status-ready
            else:
                trend_status = 'low'
                trend_text = 'Normal demand'
                color_class = 'status-approved'
            
            # Calculate if this is an emerging trend
            # Compare last 30 days vs previous 30-60 days
            recent_period = thirty_days_ago
            older_period = thirty_days_ago - timedelta(days=30)
            
            recent_count = Requisition_Item.objects.filter(
                product_id=product_id,
                requisition__date_requested__gte=recent_period
            ).count()
            
            older_count = Requisition_Item.objects.filter(
                product_id=product_id,
                requisition__date_requested__range=[older_period, recent_period]
            ).count()
            
            if older_count > 0:
                growth_rate = ((recent_count - older_count) / older_count) * 100
            else:
                growth_rate = 100 if recent_count > 0 else 0
            
            trending_items.append({
                'product_name': item['product__name'],
                'product_id': product_id,
                'unit': item['product__unit'],  # Get unit from product
                'total_requests': item['total_requests'],
                'total_quantity': float(item['total_quantity'] or 0),
                'avg_per_request': float(item['avg_per_request'] or 0),
                'current_stock': current_stock,
                'min_stock': min_stock,
                'weekly_consumption': round(weekly_consumption, 2),
                'weeks_remaining': round(weeks_remaining, 1) if weeks_remaining != float('inf') else 999,
                'growth_rate': round(growth_rate, 1),
                'trend_status': trend_status,
                'trend_text': trend_text,
                'color_class': color_class,
                'latest_request': item['latest_request'],
                'stock_status': 'Low' if min_stock > 0 and current_stock < min_stock else 
                               'Out' if current_stock == 0 else 'Healthy',
                'recommendation': get_recommendation(
                    current_stock, 
                    min_stock, 
                    weekly_consumption,
                    growth_rate,
                    weeks_remaining
                )
            })
        except InventoryBalance.DoesNotExist:
            continue
    
    # Group by unit
    unit_trends = Requisition_Item.objects.filter(
        requisition__date_requested__gte=thirty_days_ago
    ).values('product__unit').annotate(
        total_items=Count('product_id'),
        total_quantity=Sum('quantity')
    ).order_by('-total_quantity')[:10]
    
    # Get the most common unit
    top_unit = unit_trends[0]['product__unit'] if unit_trends else 'N/A'
    
    # Seasonal/Weekly patterns - FIXED: Proper day name mapping
    day_of_week_patterns = []
    day_names = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
    
    # Django uses 1=Sunday, 2=Monday, ..., 7=Saturday
    for i in range(1, 8):
        count = Requisition.objects.filter(
            date_requested__week_day=i  # Use i directly
        ).count()
        day_of_week_patterns.append({
            'day': day_names[i-1],  # Adjust index
            'count': count
        })
    
    # Peak hours analysis
    peak_hours = []
    for hour in range(8, 18):  # 8 AM to 5 PM
        count = Requisition.objects.filter(
            date_requested__hour=hour
        ).count()
        peak_hours.append({
            'hour': f"{hour:02d}:00",
            'count': count
        })
    
    return {
        'trending_items': trending_items,
        'unit_trends': list(unit_trends),
        'day_patterns': day_of_week_patterns,
        'peak_hours': peak_hours,
        'analysis_period': 'Last 90 days',
        'top_unit': top_unit,
        'total_trending_items': len(trending_items)
    }


def get_recommendation(current_stock, min_stock, weekly_consumption, growth_rate, weeks_remaining):
    """Generate AI-powered recommendations based on trends"""
    recommendations = []
    
    if current_stock == 0:
        recommendations.append("⚠️ OUT OF STOCK - Order immediately")
    elif weeks_remaining < 1:
        recommendations.append("🚨 Critical stock - Reorder within 24 hours")
    elif weeks_remaining < 2:
        recommendations.append("⚠️ Low stock - Reorder within the week")
    
    if growth_rate > 50:
        recommendations.append(f"📈 High growth ({growth_rate:.1f}%) - Consider increasing stock levels")
    elif growth_rate > 20:
        recommendations.append(f"📈 Growing demand - Monitor closely")
    
    if weekly_consumption > 0:
        suggested_order = max(min_stock * 2, weekly_consumption * 4)  # 4 weeks supply or 2x min stock
        recommendations.append(f"💡 Suggested order quantity: {suggested_order:.1f} units")
    
    if weeks_remaining > 8 and weekly_consumption < (min_stock or 10) / 4:
        recommendations.append("📉 Low consumption - Consider reducing min stock level")
    
    if len(recommendations) == 0:
        recommendations.append("✅ Stock levels optimal - Maintain current levels")
    
    return recommendations