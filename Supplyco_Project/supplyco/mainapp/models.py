from django.db import models
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password, check_password


class Staff(models.Model):
    staff_id = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100)
    password = models.CharField(max_length=128)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def set_password(self, raw_password):
        self.password = make_password(raw_password)

    def check_password(self, raw_password):
        return check_password(raw_password, self.password)

    def __str__(self):
        return f"{self.name} ({self.staff_id})"


class Profile(models.Model):
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('user', 'User'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='user')
    referred_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name='referred_customers')

    district = models.CharField(max_length=100, null=True, blank=True)
    city = models.CharField(max_length=100, null=True, blank=True)
    
    RATION_CARD_CHOICES = [
        ('yellow', 'Yellow (AAY)'),
        ('pink', 'Pink (PHH)'),
        ('blue', 'Blue (NPS)'),
        ('white', 'White (NPNS)'),
    ]
    ration_card_color = models.CharField(max_length=10, choices=RATION_CARD_CHOICES, default='white')

    def __str__(self):
        return f"{self.user.username} - {self.role} ({self.district}, {self.city})"


class Product(models.Model):
    name = models.CharField(max_length=100)
    category = models.CharField(max_length=50, default='General')
    price = models.FloatField()
    quantity = models.FloatField()
    unit = models.CharField(max_length=10, choices=[
        ('kg', 'Kilogram'),
        ('g', 'Gram'),
        ('l', 'Liter'),
        ('ml', 'Milliliter'),
        ('pcs', 'Pieces'),
    ], default='kg')
    is_subsidy = models.BooleanField(default=False)
    
    # Ration Card Eligibility
    is_eligible_yellow = models.BooleanField(default=True)
    is_eligible_pink = models.BooleanField(default=True)
    is_eligible_blue = models.BooleanField(default=True)
    is_eligible_white = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def stock_percentage(self):
        # Dynamically determine the 'full' baseline
        # Use a minimum of 50, or the highest volume ever held (current + sold)
        total_historical = self.sales.aggregate(total=models.Sum('quantity_sold'))['total'] or 0
        baseline = max(50.0, float(self.quantity) + float(total_historical))
        
        percentage = (float(self.quantity) / baseline) * 100
        return min(percentage, 100)

    @property
    def stock_status_class(self):
        if self.quantity == 0:
            return "bg-danger"
        elif self.quantity < 5:
            return "bg-warning"
        return "bg-success"

    @property
    def stock_status_label(self):
        if self.quantity == 0:
            return "Out of Stock"
        elif self.quantity < 5:
            return "Low Stock"
        return "In Stock"

    @property
    def status_html(self):
        """Returns the pre-formatted HTML badge for stock status."""
        try:
            qty_formatted = "{:g}".format(self.quantity)
            unit_str = str(self.unit)
            if self.quantity == 0:
                return '<span class="badge-status bg-danger bg-opacity-10 text-danger">DEPLETED</span>'
            elif self.quantity < 5:
                return f'<span class="badge-status bg-warning bg-opacity-10 text-warning"><i class="bi bi-exclamation-triangle-fill me-1"></i>CRITICAL ({qty_formatted} {unit_str})</span>'
            else:
                return f'<span class="badge-status bg-success bg-opacity-10 text-success"><i class="bi bi-check-circle-fill me-1"></i>AVAILABLE ({qty_formatted} {unit_str})</span>'
        except Exception as e:
            return f'<span class="badge bg-danger">Error: {str(e)}</span>'

    @property
    def admin_status_html(self):
        """Admin-only: shows quantity without OPTIMAL/CRITICAL labels."""
        try:
            qty_formatted = "{:g}".format(self.quantity)
            unit_str = str(self.unit)
            
            # Determine color based on health but don't show the text label
            if self.quantity == 0:
                color_class = "text-danger bg-danger"
            elif self.quantity < 5:
                color_class = "text-warning bg-warning"
            else:
                color_class = "text-success bg-success"
                
            return f'<span class="badge-status {color_class} bg-opacity-10">{qty_formatted} {unit_str}</span>'
        except Exception as e:
            return f'<span class="badge bg-danger">Error: {str(e)}</span>'

    @property
    def display_html(self):
        """Returns the combined name and ID HTML block (Category removed for redundancy)."""
        try:
            name_str = str(self.name)
            id_str = str(self.id)
            return f'<div class="fw-bold" style="color: var(--accent-blue); font-size: 1.05rem;">{name_str}</div>' + \
                   f'<div class="text-secondary small opacity-75">UID: #{id_str}</div>'
        except Exception as e:
            return f'<div class="text-danger">Display Error: {str(e)}</div>'

    @property
    def inventory_html(self):
        """Returns only the status badge (Progress bar removed as per user request)."""
        try:
            return f'<div class="mb-0">{self.status_html}</div>'
        except Exception as e:
            return f'<div class="text-danger">Inventory Error: {str(e)}</div>'

    @property
    def admin_inventory_html(self):
        """Admin-only inventory HTML: uses admin_status_html (no OPTIMAL label)."""
        try:
            percentage = float(self.stock_percentage)
            status_badge = self.admin_status_html
            status_class = str(self.stock_status_class)
            
            return f'<div class="mb-2">{status_badge}</div>' + \
                   f'<div class="progress" style="height: 6px;">' + \
                   f'<div class="progress-bar {status_class}" role="progressbar" data-width="{percentage}"></div>' + \
                   f'</div>'
        except Exception as e:
            return f'<div class="text-danger">Inventory Error: {str(e)}</div>'

    @property
    def ration_eligibility_html(self):
        """Returns a unified row of color-coded indicator pills for all card types."""
        try:
            items = []
            cards = [
                ('YELLOW', self.is_eligible_yellow, '#fbbf24'),
                ('PINK', self.is_eligible_pink, '#f472b6'),
                ('BLUE', self.is_eligible_blue, '#60a5fa'),
                ('WHITE', self.is_eligible_white, '#ffffff'),
            ]
            
            for name, is_elig, color in cards:
                if is_elig:
                    # Visible badge
                    items.append(f'<span class="badge" style="background: {color}20; color: {color}; border: 1px solid {color}40; font-size: 0.55rem; padding: 2px 5px; margin-right: 2px; font-weight: 700;">{name}</span>')
                else:
                    # Dimmed/Struck-through badge
                    items.append(f'<span class="badge" style="background: rgba(255,255,255,0.03); color: rgba(255,255,255,0.15); border: 1px solid rgba(255,255,255,0.05); font-size: 0.55rem; padding: 2px 5px; margin-right: 2px; text-decoration: line-through; filter: grayscale(1);">{name}</span>')
            
            return f'<div class="d-flex align-items-center mt-1">{"".join(items)}</div>'
        except Exception:
            return ''

    @property
    def category_badge_html(self):
        """Returns the pre-formatted HTML badge for category."""
        try:
            cat_str = str(self.category)
            return f'<span class="badge bg-primary bg-opacity-20 text-info border border-info border-opacity-25 badge-premium" style="font-size: 0.6rem;">{cat_str}</span>'
        except Exception as e:
            return f'<span class="badge bg-danger">Error: {str(e)}</span>'

    @property
    def subsidy_badge_html(self):
        """Returns the pre-formatted HTML badge for subsidy status."""
        if self.is_subsidy:
            return '<span class="badge bg-warning bg-opacity-20 text-warning border border-warning border-opacity-25 badge-premium ms-1">SUBSIDY</span>'
        return ''

    def __str__(self):
        return self.name


class Sale(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='sales')
    customer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='purchases')
    staff = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name='assisted_sales')
    quantity_sold = models.FloatField()
    total_price = models.FloatField()
    bill_given = models.BooleanField(default=False)
    sale_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.product.name} - {self.quantity_sold} - {self.sale_date}"

class Warehouse(models.Model):
    name = models.CharField(max_length=100)
    location = models.CharField(max_length=200, blank=True, null=True)
    manager = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name='managed_warehouses')

    def __str__(self):
        return self.name

class WarehouseStock(models.Model):
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='stocks')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='warehouse_stocks')
    quantity = models.FloatField(default=0.0)
    aisle = models.CharField(max_length=20, blank=True, null=True)
    bin_number = models.CharField(max_length=20, blank=True, null=True)

    class Meta:
        unique_together = ('warehouse', 'product')

    def __str__(self):
        return f"{self.product.name} in {self.warehouse.name}: {self.quantity}"


class StockArrival(models.Model):
    """Represents a batch of goods that arrived from the government/central supply to a depot."""
    STATUS_CHOICES = [
        ('Pending', 'Pending – Awaiting Confirmation'),
        ('Confirmed', 'Confirmed – Stock Updated'),
        ('Rejected', 'Rejected'),
    ]
    warehouse = models.ForeignKey(Warehouse, on_delete=models.SET_NULL, null=True, related_name='arrivals')
    arrival_date = models.DateTimeField(auto_now_add=True)
    received_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    vehicle_no = models.CharField(max_length=20, blank=True, null=True, help_text="Transport vehicle number")
    driver_name = models.CharField(max_length=100, blank=True, null=True)
    expected_arrival = models.DateTimeField(blank=True, null=True, help_text="Scheduled arrival time for the load")
    notes = models.TextField(blank=True, null=True, help_text="e.g. Challan No., Source Office")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')

    def __str__(self):
        return f"Arrival #{self.id} → {self.warehouse} [{self.status}] on {self.arrival_date.strftime('%d %b %Y')}"


class StockArrivalItem(models.Model):
    """Individual product line within a StockArrival."""
    arrival = models.ForeignKey(StockArrival, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.FloatField()

    def __str__(self):
        return f"{self.quantity} {self.product.unit} of {self.product.name} (Arrival #{self.arrival.id})"


class StockTransferLog(models.Model):
    """Audit log for every inter-depot stock transfer."""
    from_warehouse = models.ForeignKey(Warehouse, on_delete=models.SET_NULL, null=True, related_name='transfers_out')
    to_warehouse   = models.ForeignKey(Warehouse, on_delete=models.SET_NULL, null=True, related_name='transfers_in')
    product        = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    quantity       = models.FloatField()
    transferred_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    transferred_at = models.DateTimeField(auto_now_add=True)
    vehicle_no     = models.CharField(max_length=20, blank=True, null=True, help_text="Vehicle carrying the transferred stock")
    driver_name    = models.CharField(max_length=100, blank=True, null=True)
    notes          = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.quantity} {self.product.unit if self.product else ''} of {self.product.name if self.product else '?'} | {self.from_warehouse} → {self.to_warehouse}"


