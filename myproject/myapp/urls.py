from . import views
from django.urls import path
from django.shortcuts import redirect

urlpatterns = [


    path('accounts/login/', lambda request: redirect('/login/?next=' + request.GET.get('next', '/adminDashboard/')), 
         name='accounts_login'),    
    path('', views.admin_login, name='admin_login'),

    path('register/', views.register, name='register'),
    path('pending-accounts/', views.pending_accounts, name='pending_accounts'),
    path('approve-account/<int:acc_id>/', views.approve_account, name='approve_account'),
    path('add-as-employee/<int:acc_id>/', views.add_as_employee, name='add_as_employee'),
    path('toggle-account/<int:acc_id>/', views.toggle_account_status, name='toggle_account_status'),
    path('index/', views.index, name='index'),
    path('normalRequest/', views.normalRequest, name='normalRequest'),
    path('adminDashboard/', views.adminDashboard, name='adminDashboard'),
    path('addEmployees/', views.addEmployees, name='addEmployees'),
    path('removeEmployee/<int:emp_id>/', views.removeEmployee, name='removeEmployee'),
    path('request/', views.request, name='request'),
    path('employeeDashboard/', views.employeeDashboard, name='employeeDashboard'),

     # Account Management
    path('manage-accounts/', views.manage_accounts, name='manage_accounts'),
    path('add-employee-account/', views.add_employee_account, name='add_employee_account'),
    path('toggle-employee-status/<int:employee_id>/', views.toggle_employee_status, name='toggle_employee_status'),
    path('remove-employee/<int:employee_id>/', views.removeEmployee, name='removeEmployee'),
    path('my-account/', views.edit_my_account, name='edit_my_account'),

    # ADMIN DASHBOARD URLs
    path('requestApproval/', views.requestApproval, name='requestApproval'),
    path('approve-requisition/<int:requisition_id>/', views.approve_requisition, name='approve_requisition'),
    path('deny-requisition/<int:requisition_id>/', views.deny_requisition, name='deny_requisition'),
    path('admin-requisition/view/<int:req_id>/', views.admin_requisition_view, name="admin_requisition_view"),
    path('admin-dashboard/requestApproval/', views.requestApproval, name='requestApproval'),

    # INVENTORY DASHBOARD URLs
    path('inventory-dashboard/', views.inventory_dashboard, name='inventory_dashboard'),
    path('inventory-dashboard/stock-in/', views.stock_in_view, name='stock_in'),
    path('inventory-dashboard/stock-out/', views.stock_out_view, name='stock_out'),
    path('inventory-dashboard/add-product/', views.add_product, name='add_product'),
    path('inventory-dashboard/balance/', views.balance, name='balance'),
    path('inventory-dashboard/approved_requisitions/', views.inventory_approved_requisitions, name='inventory_approved_requisitions'),
    path('inventory-partial-approve/<int:requisition_id>/', views.inventory_partial_approve, name='inventory_partial_approve'),
    path('inventory-fulfill-stock/<int:requisition_id>/', views.inventory_fulfill_from_stock, name='inventory_fulfill_stock'),
    path('inventory-requisition/view/<int:req_id>/', views.inventory_requisition_view, name="inventory_requisition_view"),



        # Purchasing URLs
    path('purchase-requests/', views.purchase_requests_list, name='purchase_requests_list'),
    path('approve-purchase-request/<int:request_id>/', views.approve_purchase_request, name='approve_purchase_request'),
    path('deny-purchase-request/<int:request_id>/', views.deny_purchase_request, name='deny_purchase_request'),
    path('create-purchase-request/<int:requisition_id>/', views.create_purchase_request, name='create_purchase_request'),
    path('approved-purchase-requests/', views.approved_purchase_requests, name='approved_purchase_requests'),
    path('create-purchase-order/<int:request_id>/', views.create_purchase_order, name='create_purchase_order'),
    path('send-purchase-order/<int:po_id>/', views.send_purchase_order, name='send_purchase_order'),
    path('receive-purchase-order/<int:po_id>/', views.receive_purchase_order, name='receive_purchase_order'),
    path('ready-for-pickup/', views.ready_for_pickup_requisitions, name='ready_for_pickup_requisitions'),
    path('mark-ready-pickup/<int:requisition_id>/', views.mark_ready_for_pickup, name='mark_ready_for_pickup'),
    path('complete-pickup/<int:requisition_id>/', views.complete_pickup, name='complete_pickup'),
    path('purchase-order/purchase-again/<int:po_id>/', views.purchase_again, name='purchase_again'),
    path('purchase-order/purchase-again/<uuid:po_id>/', views.purchase_again, name='purchase_again'),



    # Supplier Management
    path('suppliers/', views.supplier_list, name='supplier_list'),
    path('add-supplier/', views.add_supplier, name='add_supplier'),
    path('deactivate-supplier/<int:supplier_id>/', views.deactivate_supplier, name='deactivate_supplier'),
    path('activate-supplier/<int:supplier_id>/', views.activate_supplier, name='activate_supplier'),
    path('edit-supplier/<int:supplier_id>/', views.edit_supplier, name='edit_supplier'),
    path('update-supplier/<int:supplier_id>/', views.update_supplier, name='update_supplier'),
    path('delete-supplier/<int:supplier_id>/', views.delete_supplier, name='delete_supplier'),

    # Reports
    path('purchase-order-report/', views.purchase_order_report, name='purchase_order_report'),
    path('accomplishment-report/', views.accomplishment_report, name='accomplishment_report'),

    path('purchase-request/detail/<int:request_id>/', views.purchase_request_detail, name='purchase_request_detail'),
    path('purchase-order/detail/<int:po_id>/', views.purchase_order_detail, name='purchase_order_detail'),
  
    path('create-purchase-request-from-balance/', views.create_purchase_request_from_balance, name='create_purchase_request_from_balance'),
    path('cancel-pickup/<int:requisition_id>/', views.cancel_pickup, name='cancel_pickup'),

    path('employee/request-history/', views.request_history, name='request_history'),
    path('employee/mark-received/<int:requisition_id>/', views.mark_as_received, name='mark_as_received'),


    # Add these to your existing urlpatterns in urls.py
    path('reports/', views.reports_main, name='reports_main'),
    path('reports/<str:report_type>/', views.get_report_data, name='get_report_data'),
    path('reports/export/<str:report_type>/', views.export_report_csv, name='export_report_csv'),

    # Purchase Order URLs
    path('purchase-orders/', views.purchase_orders_list, name='purchase_orders_list'),
    path('purchase-orders/<int:po_id>/', views.purchase_order_detail, name='purchase_order_detail'),
    path('purchase-orders/receive/<int:po_id>/', views.receive_purchase_order, name='receive_purchase_order'),
    path('quality-check/<int:receiving_id>/', views.quality_check_receiving, name='quality_check_receiving'),
    
    # API endpoints for receiving
    path('api/receiving/<int:receiving_id>/', views.get_receiving_details, name='get_receiving_details'),
    path('api/rejected-item/<int:rejected_id>/update-disposition/', views.update_rejection_disposition, name='update_rejection_disposition'),
   ]