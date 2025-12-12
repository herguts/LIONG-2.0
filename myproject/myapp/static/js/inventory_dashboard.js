class InventorySidebar extends HTMLElement {
  connectedCallback() {
    const currentFile = (window.location.pathname.split('/').pop() || 'index.html').toLowerCase();

    const menu = [
      { 
        href: '/inventory-dashboard/', 
        label: 'Inventory Dashboard', 
        icon: 'layers',
        patterns: ['inventory-dashboard']
      },
      { 
        href: '/inventory-dashboard/stock-in/', 
        label: 'Stock In', 
        icon: 'arrow-down-circle',
        patterns: ['stock-in']
      },
      { 
        href: '/inventory-dashboard/stock-out/', 
        label: 'Stock Out', 
        icon: 'arrow-up-circle',
        patterns: ['stock-out']
      },
      { 
        href: '/inventory-dashboard/balance/', 
        label: 'Balance', 
        icon: 'bar-chart-2',
        patterns: ['balance']
      },
      { 
        href: '/inventory-dashboard/approved_requisitions/', 
        label: 'Manage Request', 
        icon: 'package',
        patterns: ['approved_requisitions', 'inventory-requisition']
      },
      { 
        href: '/approved-purchase-requests/', 
        label: 'Create Purchase Orders', 
        icon: 'file-text',
        patterns: ['approved-purchase-requests', 'create-purchase-order']
      },
      { 
        href: '/purchase-orders/', 
        label: 'Manage Purchase', 
        icon: 'shopping-cart',
        patterns: ['purchase-orders', 'send-purchase-order', 'receive-purchase-order']
      },
      { 
        href: '/ready-for-pickup/', 
        label: 'Ready for Pickup', 
        icon: 'truck',
        patterns: ['ready-for-pickup', 'mark-ready-pickup', 'complete-pickup']
      },
      { 
        href: '/suppliers/', 
        label: 'Suppliers', 
        icon: 'users',
        patterns: ['suppliers', 'add-supplier']
      },
      { href: 'http://127.0.0.1:8000', label: 'Logout', icon: 'log-out', patterns: ['logout'], isLogout: true },

    ];

    const makeIconSvg = (name) => {
      try {
        if (window.feather && window.feather.icons && window.feather.icons[name]) {
          return window.feather.icons[name].toSvg({ class: 'icon' });
        }
      } catch (e) { }
      return `<i data-feather="${name}" class="icon"></i>`;
    };

    const itemsHtml = menu.map(item => {
      const itemPath = new URL(item.href, window.location.origin).pathname.toLowerCase();
      const isActive = currentFile === itemPath.split('/').pop() || currentFile === itemPath.slice(1, -1);
      return `
        <li>
          <a href="${item.href}" class="menu-item ${isActive ? 'active' : ''}">
            ${makeIconSvg(item.icon)}
            <span class="label">${item.label}</span>
          </a>
        </li>
      `;
    }).join('');

    this.innerHTML = `
      <style>
        .custom-sidebar {
          width: 250px;
          background: #f8fafc;
          padding: 1rem;
          height: 100vh;
          position: fixed;
          left: 0;
          top: 0;
          border-right: 1px solid #e5e7eb;
          z-index: 40;
          box-sizing: border-box;
        }
        .custom-sidebar .department-head { padding: 1rem 0; margin-bottom: 1rem; border-bottom: 1px solid #e5e7eb; }
        .custom-sidebar .department-head h3 { font-weight: 600; margin: 0; font-size: 1rem; color: #111827; }
        .custom-sidebar .department-head p { font-size: 0.875rem; color: #6b7280; margin: 0.25rem 0 0 0; }
        .custom-sidebar .nav-links { list-style: none; padding: 0; margin: 1rem 0 0 0; }
        .custom-sidebar .menu-item { display: flex; align-items: center; gap: 0.75rem; padding: 0.6rem 0.8rem; color: #4b5563; text-decoration: none; border-radius: 0.375rem; transition: background 0.15s, color 0.15s; border-left: 3px solid transparent; }
        .custom-sidebar .menu-item:hover { background-color: #eef2ff; color: #1e40af; }
        .custom-sidebar .menu-item.active { background-color: #e0e7ff; color: #1e40af; font-weight: 600; border-left-color: #c7d2fe; }
        .custom-sidebar .icon { width: 18px; height: 18px; stroke: currentColor; }
        @media (max-width: 768px) {
          .custom-sidebar { transform: translateX(-100%); transition: transform .25s ease; }
          .custom-sidebar.open { transform: translateX(0); }
        }
      </style>
      <aside class="custom-sidebar">
        <div class="department-head">
          <h3>Inventory</h3>
          <p>Management System</p>
        </div>
        <ul class="nav-links">
          ${itemsHtml}
        </ul>
      </aside>
    `;

    setTimeout(() => feather.replace(), 20);
    setTimeout(() => feather.replace(), 200);
  }
}



// Add to your existing JavaScript file

// Supplier Management Functions
function editSupplier(supplierId) {
    fetch(`/edit-supplier/${supplierId}/`)
        .then(response => response.text())
        .then(html => {
            document.getElementById("editSupplierContent").innerHTML = html;
            document.getElementById("editSupplierModal").classList.remove("hidden");
        })
        .catch(error => {
            console.error('Error loading supplier:', error);
            document.getElementById("editSupplierContent").innerHTML = 
                '<div class="text-red-500 p-4">Error loading supplier details.</div>';
        });
}

function closeEditSupplierModal() {
    document.getElementById("editSupplierModal").classList.add("hidden");
    document.getElementById("editSupplierContent").innerHTML = '';
}

// Add event listener for edit supplier modal
document.addEventListener('DOMContentLoaded', function() {
    const editModal = document.getElementById('editSupplierModal');
    if (editModal) {
        editModal.addEventListener('click', function(e) {
            if (e.target.id === 'editSupplierModal') {
                closeEditSupplierModal();
            }
        });
    }
});

// Add Supplier Modal Functions
function openAddSupplierModal() {
    document.getElementById('addSupplierModal').classList.remove('hidden');
}

function closeAddSupplierModal() {
    document.getElementById('addSupplierModal').classList.add('hidden');
}

// Close modal when clicking outside
document.addEventListener('DOMContentLoaded', function() {
    const addModal = document.getElementById('addSupplierModal');
    
    if (addModal) {
        addModal.addEventListener('click', function(event) {
            if (event.target === addModal) {
                closeAddSupplierModal();
            }
        });
    }
    
    // Close on Escape key
    document.addEventListener('keydown', function(event) {
        if (event.key === 'Escape') {
            closeAddSupplierModal();
        }
    });
});

customElements.define('inventory-sidebar', InventorySidebar);