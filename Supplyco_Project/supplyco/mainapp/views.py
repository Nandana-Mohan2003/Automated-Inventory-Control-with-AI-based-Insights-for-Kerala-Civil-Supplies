from django.shortcuts import render, redirect
from django.db.models import Q, Prefetch
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required, user_passes_test
from .models import Product, Sale, Profile, Staff
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum, Count, F, Value
from django.db.models.functions import TruncMonth, Coalesce

# CHECK ADMIN
def is_admin(user):
    try:
        return user.profile.role == 'admin'
    except Profile.DoesNotExist:
        return user.is_staff

def is_depot_manager(user):
    try:
        # Both central admin and staff (depot admins) can manage depots
        return user.profile.role in ['admin', 'staff']
    except Profile.DoesNotExist:
        return user.is_staff

# CHECK CUSTOMER
def is_customer(user):
    try:
        return user.profile.role == 'user'
    except Profile.DoesNotExist:
        return not user.is_staff

# CHECK STAFF
def is_staff_member(request):
    return 'staff_id' in request.session

def home(request):
    if not request.user.is_authenticated:
        return redirect("user_login")
    try:
        if request.user.profile.role == 'admin':
            return redirect("admin_dashboard")
        elif request.user.profile.role == 'staff':
            return redirect("staff_dashboard")
    except Profile.DoesNotExist:
        if request.user.is_staff:
            return redirect("admin_dashboard")
    return redirect("user_products")

def user_register(request):
    if request.user.is_authenticated:
        try:
            if request.user.profile.role == 'admin':
                return redirect("admin_dashboard")
        except Profile.DoesNotExist:
            if request.user.is_staff:
                return redirect("admin_dashboard")
        return redirect("user_products")

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        first_name = request.POST.get("first_name")
        email = request.POST.get("email")

        if User.objects.filter(username=username).exists():
            return render(request, "register.html", {"error": "Username already exists"})

        if User.objects.filter(email=email).exists():
            return render(request, "register.html", {"error": "An account with this email already exists"})

        district = request.POST.get("district")
        city = request.POST.get("city")
        ration_card_color = request.POST.get("ration_card_color", "white")

        user = User.objects.create_user(username=username, password=password, email=email, first_name=first_name)
        # Create Profile (default to 'user')
        referred_by = None
        if 'staff_id' in request.session:
            try:
                referred_by = Staff.objects.get(staff_id=request.session['staff_id'])
            except Staff.DoesNotExist:
                pass
        
        Profile.objects.create(
            user=user, 
            role='user', 
            referred_by=referred_by, 
            district=district, 
            city=city,
            ration_card_color=ration_card_color
        )
        
        # No need to set is_staff here by default for registration

        messages.success(request, "Registered successfully")
        return redirect("user_login")

    return render(request, "register.html")

def user_login(request):
    if 'staff_id' in request.session:
        return redirect("staff_dashboard")
    if request.user.is_authenticated:
        try:
            role = request.user.profile.role
            if role == 'admin':
                return redirect("admin_dashboard")
        except Profile.DoesNotExist:
            if request.user.is_staff:
                return redirect("admin_dashboard")
        return redirect("user_products")

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        role_requested = request.POST.get("role")

        if role_requested == 'staff':
            try:
                staff_user = Staff.objects.get(staff_id=username, is_active=True)
                if staff_user.check_password(password):
                    request.session['staff_id'] = staff_user.staff_id
                    return redirect('staff_dashboard')
                else:
                    return render(request, "login.html", {"error": "Invalid Staff credentials"})
            except Staff.DoesNotExist:
                return render(request, "login.html", {"error": "Staff member not found"})

        user = authenticate(request, username=username, password=password)

        if user is not None:
            try:
                profile = user.profile
                actual_role = profile.role
                actual_card = profile.ration_card_color
            except Profile.DoesNotExist:
                actual_role = 'admin' if user.is_staff else 'user'
                actual_card = 'white'
            
            if actual_role != role_requested:
                error_msg = f"Access denied. Your account is registered as '{actual_role}', but you're trying to login as '{role_requested}'."
                return render(request, "login.html", {"error": error_msg})

            # Check Ration Card Color for Users
            if actual_role == 'user':
                selected_card = request.POST.get("ration_card_color")
                if selected_card != actual_card:
                    error_msg = f"Authentication Failed. The selected card color does not match our records for this identity."
                    return render(request, "login.html", {"error": error_msg})

            login(request, user)
            if actual_role == 'admin':
                return redirect("admin_dashboard")
            return redirect("user_products")
        
        return render(request, "login.html", {"error": "Invalid login"})

    return render(request, "login.html")

def user_logout(request):
    logout(request)
    if 'staff_id' in request.session:
        del request.session['staff_id']
    return redirect("user_login")

@login_required
@user_passes_test(is_admin)
def admin_dashboard(request):
    query = request.GET.get('q')
    if query:
        products = Product.objects.filter(Q(name__icontains=query) | Q(category__icontains=query))
    else:
        products = Product.objects.all()

    # Filtering by Subsidy
    subsidy_filter = request.GET.get('subsidy')
    if subsidy_filter == 'yes':
        products = products.filter(is_subsidy=True)
    elif subsidy_filter == 'no':
        products = products.filter(is_subsidy=False)
    
    # Order by most recent
    products = products.order_by('-id')

    # AI PREDICTIVE ENGINE
    today = timezone.now()
    seven_days_ago = today - timezone.timedelta(days=7)
    thirty_days_ago = today - timezone.timedelta(days=30)
    
    forecast_data = []
    # Use the filtered products list for AI forecasting if a query exists
    prediction_products = products if query else Product.objects.all()
    
    for p in prediction_products:
        # (Forecasting logic remains same, but using ordered products)
        sales_7d = Sale.objects.filter(product=p, sale_date__gte=seven_days_ago).aggregate(
            total=Coalesce(Sum('quantity_sold'), Value(0.0))
        )['total']
        
        sales_30d = Sale.objects.filter(product=p, sale_date__gte=thirty_days_ago).aggregate(
            total=Coalesce(Sum('quantity_sold'), Value(0.0))
        )['total']
        
        v7 = float(sales_7d) / 7.0
        days_active = (today - p.created_at).days
        v30_window = max(min(days_active, 30), 1)
        v30 = float(sales_30d) / float(v30_window)
        effective_velocity = v7 if v7 > 0 else v30
        
        if p.quantity > 0 and p.quantity < 5 and effective_velocity < 0.1:
            effective_velocity = 0.5 if p.quantity <= 1 else 0.2
        
        days_left = 999
        display_days = "15+"
        if p.quantity <= 0:
            days_left = 0
            display_days = "OUT"
        elif effective_velocity > 0:
            days_left = float(p.quantity) / effective_velocity
            display_days = str(round(days_left, 1)) if days_left < 100 else "15+"
        
        is_fast_mover = v30 > 1.0 or v7 > 0.5
        if days_left < 10 or p.quantity < 5 or is_fast_mover:
            if days_left < 3 or p.quantity <= 0:
                priority_label, priority_class = 'CRITICAL', 'badge-danger'
            elif days_left < 7:
                priority_label, priority_class = 'WARNING', 'badge-warning'
            else:
                priority_label, priority_class = 'STABLE', 'badge-success'
            
            forecast_data.append({
                'id': p.id, 'name': p.name, 'stock_qty': float(p.quantity),
                'total_sold': round(float(sales_30d), 1), 'unit': p.unit,
                'days_left': display_days, 'priority_label': priority_label,
                'priority_class': priority_class, 'velocity': round(effective_velocity, 2),
                'is_fast_mover': is_fast_mover, 'is_subsidy': p.is_subsidy
            })

    forecast_data = sorted(forecast_data, key=lambda x: (0 if x['is_fast_mover'] else 1, float(x['days_left']) if isinstance(x['days_left'], (int, float)) else 100))

    monthly_performance = Sale.objects.annotate(month=TruncMonth('sale_date')).values('month', 'product__name').annotate(
        total_sold=Coalesce(Sum('quantity_sold'), Value(0.0)),
        total_revenue=Coalesce(Sum('total_price'), Value(0.0))
    ).order_by('-month', '-total_sold')

    top_performing_items = Sale.objects.values('product__name').annotate(
        total_sold=Coalesce(Sum('quantity_sold'), Value(0.0))
    ).order_by('-total_sold')[:5]

    from .models import StockArrival, StockTransferLog, Warehouse, WarehouseStock
    recent_arrivals = StockArrival.objects.filter(status='Confirmed').prefetch_related('items__product').order_by('-arrival_date')[:5]
    recent_transfers = StockTransferLog.objects.select_related('product', 'from_warehouse', 'to_warehouse').order_by('-transferred_at')[:5]
    
    # Depot Breakdown
    warehouses = Warehouse.objects.prefetch_related('stocks__product').all()

    # Calculate Stats
    total_products = Product.objects.count()
    total_revenue = Sale.objects.aggregate(total=Coalesce(Sum('total_price'), Value(0.0)))['total']
    
    # Calculate Monthly Movement (Sales in last 30 days)
    thirty_days_ago = today - timezone.timedelta(days=30)
    monthly_movement = Sale.objects.filter(sale_date__gte=thirty_days_ago).aggregate(
        total=Coalesce(Sum('quantity_sold'), Value(0.0)))['total']
    monthly_revenue = Sale.objects.filter(sale_date__gte=thirty_days_ago).aggregate(
        total=Coalesce(Sum('total_price'), Value(0.0)))['total']

    context = {
        'products': products,
        'monthly_performance': monthly_performance,
        'top_performing_items': top_performing_items,
        'predictions': forecast_data,
        'total_products': total_products,
        'total_revenue': total_revenue,
        'monthly_movement': round(monthly_movement, 1),
        'monthly_revenue': round(monthly_revenue, 1),
        'recent_arrivals': recent_arrivals,
        'recent_transfers': recent_transfers,
        'warehouses': warehouses,
    }

    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.GET.get('ajax') == '1'
    if is_ajax:
        response = render(request, 'partials/admin_table_rows.html', context)
        response['Vary'] = 'X-Requested-With'
        response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response['Pragma'] = 'no-cache'
        return response

    return render(request, 'admin_dashboard.html', context)

# ADD PRODUCT (ADMIN)
@login_required
@user_passes_test(is_admin)
def add_product(request):
    if request.method == "POST":
        name = request.POST.get('name')
        category = request.POST.get('category')
        price = request.POST.get('price')
        quantity = request.POST.get('quantity')
        unit = request.POST.get('unit')

        product = Product.objects.create(
            name=name,
            category=category,
            price=float(price or 0),
            quantity=float(quantity or 0),
            unit=unit,
            is_subsidy=request.POST.get('is_subsidy') == 'on',
            is_eligible_yellow=request.POST.get('is_eligible_yellow') == 'on',
            is_eligible_pink=request.POST.get('is_eligible_pink') == 'on',
            is_eligible_blue=request.POST.get('is_eligible_blue') == 'on',
            is_eligible_white=request.POST.get('is_eligible_white') == 'on'
        )
        
        # Ensure WarehouseStock is in sync
        from .models import Warehouse, WarehouseStock
        main_depot = Warehouse.objects.first()
        if main_depot and product.quantity > 0:
            WarehouseStock.objects.get_or_create(
                warehouse=main_depot, 
                product=product, 
                defaults={'quantity': product.quantity}
            )
            
        return redirect('admin_dashboard')

    return render(request, 'add_product.html')

# USER PRODUCT LIST
@login_required
@user_passes_test(is_customer)
def user_products(request):
    query = request.GET.get('q')
    if query:
        products = Product.objects.filter(Q(name__icontains=query) | Q(category__icontains=query))
    else:
        products = Product.objects.all()
    
    # Filtering by Subsidy
    subsidy_filter = request.GET.get('subsidy')
    if subsidy_filter == 'yes':
        products = products.filter(is_subsidy=True)
    elif subsidy_filter == 'no':
        products = products.filter(is_subsidy=False)
    
    # Order by most recent
    products = products.order_by('-id')

    context = {
        'products': products,
        'user_card_color': request.user.profile.ration_card_color if hasattr(request.user, 'profile') else 'white'
    }
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.GET.get('ajax') == '1'
    if is_ajax:
        response = render(request, 'partials/product_table_rows.html', context)
        response['Vary'] = 'X-Requested-With'
        response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response['Pragma'] = 'no-cache'
        return response

    return render(request, 'products.html', context)

@login_required
@user_passes_test(is_admin)
def edit_product(request, pk):
    try:
        product = Product.objects.get(pk=pk)
    except Product.DoesNotExist:
        messages.error(request, "Product not found.")
        return redirect('admin_dashboard')

    if request.method == "POST":
        try:
            old_qty = product.quantity
            product.name = request.POST.get('name')
            product.category = request.POST.get('category')
            product.price = float(request.POST.get('price') or 0)
            product.quantity = float(request.POST.get('quantity') or 0)
            product.unit = request.POST.get('unit')
            product.is_subsidy = request.POST.get('is_subsidy') == 'on'
            product.is_eligible_yellow = request.POST.get('is_eligible_yellow') == 'on'
            product.is_eligible_pink = request.POST.get('is_eligible_pink') == 'on'
            product.is_eligible_blue = request.POST.get('is_eligible_blue') == 'on'
            product.is_eligible_white = request.POST.get('is_eligible_white') == 'on'
            product.save()

            # Maintain WarehouseStock consistency on quantity edit
            delta = product.quantity - old_qty
            if delta != 0:
                from .models import Warehouse, WarehouseStock
                main_depot = Warehouse.objects.first()
                if main_depot:
                    stock, _ = WarehouseStock.objects.get_or_create(warehouse=main_depot, product=product)
                    stock.quantity = max(0, stock.quantity + delta)
                    stock.save()

            messages.success(request, f"Updated record for {product.name} successfully.")
            return redirect('admin_dashboard')
        except (ValueError, TypeError) as e:
            messages.error(request, f"Submission error: Invalid numeric data provided.")
    
    return render(request, 'edit_product.html', {'product': product})


# DELETE PRODUCT (ADMIN)
@login_required
@user_passes_test(is_admin)
def delete_product(request, pk):
    product = Product.objects.get(pk=pk)
    product.delete()
    return redirect('admin_dashboard')


# SELL PRODUCT (ADMIN/CUSTOMER)
@login_required
def sell_product(request, pk):
    try:
        product = Product.objects.get(pk=pk)
    except Product.DoesNotExist:
        messages.error(request, "Product not found.")
        return redirect('admin_dashboard' if request.user.is_staff else 'user_products')

    if request.method == "POST":
        try:
            quantity_sold = float(request.POST.get('quantity_sold', 0))
        except (ValueError, TypeError):
            messages.error(request, "Invalid quantity.")
            return redirect(request.META.get('HTTP_REFERER', 'home'))
        
        if quantity_sold <= 0:
            messages.error(request, "Quantity must be greater than zero.")
        elif product.quantity >= quantity_sold:
            total_price = product.price * quantity_sold
            staff_obj = None
            customer = None
            
            # Check for explicitly provided customer (from staff dashboard sale form)
            customer_id = request.POST.get('customer_id')
            if customer_id:
                try:
                    customer = User.objects.get(id=customer_id)
                except User.DoesNotExist:
                    pass

            if 'staff_id' in request.session:
                try:
                    staff_obj = Staff.objects.get(staff_id=request.session['staff_id'])
                    # If staff is selling but no customer selected, it might still link if the user is a walk-in
                except Staff.DoesNotExist:
                    pass
            elif request.user.is_authenticated:
                try:
                    role = request.user.profile.role
                    if role == 'user':
                        customer = request.user
                        staff_obj = request.user.profile.referred_by
                except Profile.DoesNotExist:
                    pass

            Sale.objects.create(
                product=product,
                quantity_sold=quantity_sold,
                total_price=total_price,
                customer=customer,
                staff=staff_obj
            )
            product.quantity -= quantity_sold
            product.save()
            
            # Update WarehouseStock (Subtract from Main Depot by default)
            from .models import Warehouse, WarehouseStock
            main_depot = Warehouse.objects.first()
            if main_depot:
                stock, _ = WarehouseStock.objects.get_or_create(warehouse=main_depot, product=product)
                stock.quantity = max(0, stock.quantity - quantity_sold)
                stock.save()

            messages.success(request, f"Successfully recorded purchase: {quantity_sold} {product.unit} of {product.name}")
        else:
            messages.error(request, f"Insufficient stock for {product.name}")
            
    return redirect(request.META.get('HTTP_REFERER', 'home'))


# STOCK ANALYTICS & PREDICTION
@login_required
@user_passes_test(is_admin)
def stock_analytics(request):
    # Monthly Stock Performance
    monthly_performance = Sale.objects.annotate(
        month=TruncMonth('sale_date')
    ).values('month', 'product__name').annotate(
        total_sold=Coalesce(Sum('quantity_sold'), Value(0.0)),
        total_revenue=Coalesce(Sum('total_price'), Value(0.0))
    ).order_by('-month', '-total_sold')

    # Top Performing Items
    top_performing_items = Sale.objects.values('product__name').annotate(
        total_sold=Coalesce(Sum('quantity_sold'), Value(0.0))
    ).order_by('-total_sold')[:5]

    # AI ADVANCED PREDICTIONS
    today = timezone.now()
    seven_days_ago = today - timezone.timedelta(days=7)
    thirty_days_ago = today - timezone.timedelta(days=30)
    
    forecast_data = []
    for p in Product.objects.all():
        sales_7d = Sale.objects.filter(product=p, sale_date__gte=seven_days_ago).aggregate(
            total=Coalesce(Sum('quantity_sold'), Value(0.0))
        )['total']
        
        sales_30d = Sale.objects.filter(product=p, sale_date__gte=thirty_days_ago).aggregate(
            total=Coalesce(Sum('quantity_sold'), Value(0.0))
        )['total']
        
        v7 = float(sales_7d) / 7.0
        
        # Non-diluted v30
        days_active = (today - p.created_at).days
        v30_window = max(min(days_active, 30), 1)
        v30 = float(sales_30d) / float(v30_window)
        
        effective_velocity = v7 if v7 > 0 else v30
        is_adjusted = False
        
        # SAFETY VELOCITY for Low Stock intuition
        if p.quantity > 0 and p.quantity < 5 and effective_velocity < 0.1:
            effective_velocity = 0.5 if p.quantity <= 1 else 0.2
            is_adjusted = True

        days_left = 999
        display_days = "15+"
        if p.quantity <= 0:
            days_left = 0
            display_days = "OUT"
        elif effective_velocity > 0:
            days_left = float(p.quantity) / effective_velocity
            display_days = str(round(days_left, 1)) if days_left < 100 else "15+"
        
        is_fast_mover = v30 > 1.0 or v7 > 0.5
        demand_score = effective_velocity / (float(p.quantity) if p.quantity > 0 else 0.1)
        
        forecast_data.append({
            'id': p.id,
            'name': p.name,
            'category': p.category,
            'stock_qty': float(p.quantity),
            'unit': p.unit,
            'total_sold': round(float(sales_30d), 1), 
            'velocity': round(effective_velocity, 2),
            'days_left': display_days,
            'priority_label': 'CRITICAL' if days_left < 3 or p.quantity <= 0 else ('WARNING' if days_left < 7 else 'STABLE'),
            'priority_class': 'badge-danger' if days_left < 3 or p.quantity <= 0 else ('badge-warning' if days_left < 7 else 'badge-success'),
            'is_fast_mover': is_fast_mover,
            'is_adjusted': is_adjusted,
            'demand_score': demand_score,
            'is_subsidy': p.is_subsidy
        })

    # Sort: Fast Movers first, then by demand score
    forecast_data = sorted(forecast_data, key=lambda x: (0 if x['is_fast_mover'] else 1, -x['demand_score']))

    return render(request, 'stock_analytics.html', {
        'monthly_performance': monthly_performance,
        'top_performing_items': top_performing_items,
        'predictions': forecast_data
    })
from django.http import JsonResponse

# API FOR REAL-TIME STOCK
@login_required
def api_stock_levels(request):
    products = Product.objects.exclude(name='Toor Dhal(Thuvara parippu)').values('id', 'name', 'quantity', 'unit', 'is_subsidy')
    data = []
    today = timezone.now()
    seven_days_ago = today - timezone.timedelta(days=7)
    thirty_days_ago = today - timezone.timedelta(days=30)

    for p in products:
        status = "in_stock"
        if p['quantity'] == 0:
            status = "out_of_stock"
        elif p['quantity'] < 5:
            status = "low_stock"
        
        # Velocity logic
        sales_7d = Sale.objects.filter(product_id=p['id'], sale_date__gte=seven_days_ago).aggregate(
            total=Coalesce(Sum('quantity_sold'), Value(0.0))
        )['total']
        
        sales_30d = Sale.objects.filter(product_id=p['id'], sale_date__gte=thirty_days_ago).aggregate(
            total=Coalesce(Sum('quantity_sold'), Value(0.0))
        )['total']
        
        v7 = float(sales_7d) / 7.0
        
        # Non-diluted v30
        p_obj = Product.objects.get(id=p['id'])
        days_active = (today - p_obj.created_at).days
        v30_window = max(min(days_active, 30), 1)
        v30 = float(sales_30d) / float(v30_window)
        
        effective_velocity = v7 if v7 > 0 else v30
        is_adjusted = False
        
        # SAFETY VELOCITY for real-time dashboard intuition
        if p['quantity'] > 0 and p['quantity'] < 5 and effective_velocity < 0.1:
            effective_velocity = 0.5 if p['quantity'] <= 1 else 0.2
            is_adjusted = True

        days_left = 999
        display_days = "15+"
        if p['quantity'] <= 0:
            days_left = 0
            display_days = "OUT"
        elif effective_velocity > 0:
            days_left = float(p['quantity']) / effective_velocity
            display_days = str(round(days_left, 1)) if days_left < 100 else "15+"
        
        is_fast_mover = v30 > 1.0 or v7 > 0.5
        
        # Determine priority for API
        if days_left < 3 or p['quantity'] <= 0:
            priority_label = 'CRITICAL'
            priority_class = 'badge-danger'
        elif days_left < 7:
            priority_label = 'WARNING'
            priority_class = 'badge-warning'
        else:
            priority_label = 'STABLE'
            priority_class = 'badge-success'
        
        data.append({
            'id': p['id'],
            'name': p_obj.name,
            'stock_qty': float(p['quantity']),
            'total_sold': round(float(sales_30d), 1),
            'unit': p['unit'],
            'is_subsidy': p['is_subsidy'],
            'status': status,
            'stock_percentage': p_obj.stock_percentage,
            'velocity': round(effective_velocity, 2),
            'days_left': display_days,
            'priority': 'Critical' if days_left < 3 or p['quantity'] <= 0 else 'Warning',
            'priority_label': priority_label,
            'priority_class': priority_class,
            'is_fast_mover': is_fast_mover,
            'is_adjusted': is_adjusted
        })
    return JsonResponse({'products': data})


# FLUTTER REST API VIEWS
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework import status as drf_status
from rest_framework.authtoken.models import Token
from .serializers import ProductSerializer


@api_view(['POST'])
@permission_classes([AllowAny])
def flutter_login(request):
    user = authenticate(username=request.data.get('username'), password=request.data.get('password'))
    if user:
        token, _ = Token.objects.get_or_create(user=user)
        return Response({'token': token.key, 'username': user.username, 'is_admin': user.is_staff})
    return Response({'error': 'Invalid credentials'}, status=drf_status.HTTP_401_UNAUTHORIZED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def flutter_logout(request):
    request.user.auth_token.delete()
    return Response({'message': 'Logged out'})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def flutter_products(request):
    q = request.query_params.get('q')
    products = Product.objects.exclude(name='Toor Dhal(Thuvara parippu)')
    if q:
        products = products.filter(Q(name__icontains=q) | Q(category__icontains=q))
    return Response(ProductSerializer(products, many=True).data)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def flutter_dashboard(request):
    thirty_days_ago = timezone.now() - timezone.timedelta(days=30)
    products = Product.objects.all()
    top_movers = Sale.objects.filter(sale_date__gte=thirty_days_ago).values('product__name').annotate(total_sold=Sum('quantity_sold')).order_by('-total_sold')[:5]
    monthly = Sale.objects.filter(sale_date__gte=thirty_days_ago).aggregate(total_revenue=Coalesce(Sum('total_price'), Value(0.0)), total_sold=Coalesce(Sum('quantity_sold'), Value(0.0)))
    return Response({'products': ProductSerializer(products, many=True).data, 'top_movers': list(top_movers), 'monthly_revenue': monthly['total_revenue'], 'monthly_sold': monthly['total_sold'], 'total_products': products.count()})


@api_view(['GET'])
@permission_classes([IsAdminUser])
def flutter_analytics(request):
    today = timezone.now()
    seven_days_ago = today - timezone.timedelta(days=7)
    thirty_days_ago = today - timezone.timedelta(days=30)
    forecast_data = []
    for p in Product.objects.all():
        sales_7d = Sale.objects.filter(product=p, sale_date__gte=seven_days_ago).aggregate(total=Coalesce(Sum('quantity_sold'), Value(0.0)))['total']
        sales_30d = Sale.objects.filter(product=p, sale_date__gte=thirty_days_ago).aggregate(total=Coalesce(Sum('quantity_sold'), Value(0.0)))['total']
        v7 = float(sales_7d) / 7.0
        v30 = float(sales_30d) / max(min((today - p.created_at).days, 30), 1)
        ev = v7 if v7 > 0 else v30
        is_adj = False
        if p.quantity > 0 and p.quantity < 5 and ev < 0.1:
            ev = 0.5 if p.quantity <= 1 else 0.2
            is_adj = True
        dl = 999
        dd = '15+'
        if p.quantity <= 0: dl, dd = 0, 'OUT'
        elif ev > 0: dl = float(p.quantity) / ev; dd = str(round(dl, 1)) if dl < 100 else '15+'
        pr = 'CRITICAL' if (dl < 3 or p.quantity <= 0) else ('WARNING' if dl < 7 else 'STABLE')
        forecast_data.append({'id': p.id, 'name': p.name, 'category': p.category, 'stock_qty': float(p.quantity), 'unit': p.unit, 'total_sold': round(float(sales_30d),1), 'velocity': round(ev,2), 'days_left': dd, 'priority_label': pr, 'is_fast_mover': v7>(v30*1.5) and v7>0.5, 'is_adjusted': is_adj})
    return Response({'forecast': forecast_data})


@api_view(['POST'])
@permission_classes([IsAdminUser])
def flutter_add_product(request):
    s = ProductSerializer(data=request.data)
    if s.is_valid(): s.save(); return Response(s.data, status=drf_status.HTTP_201_CREATED)
    return Response(s.errors, status=drf_status.HTTP_400_BAD_REQUEST)


@api_view(['PUT', 'PATCH'])
@permission_classes([IsAdminUser])
def flutter_edit_product(request, pk):
    try: p = Product.objects.get(pk=pk)
    except Product.DoesNotExist: return Response({'error': 'Not found'}, status=drf_status.HTTP_404_NOT_FOUND)
    s = ProductSerializer(p, data=request.data, partial=True)
    if s.is_valid(): s.save(); return Response(s.data)
    return Response(s.errors, status=drf_status.HTTP_400_BAD_REQUEST)


@api_view(['DELETE'])
@permission_classes([IsAdminUser])
def flutter_delete_product(request, pk):
    try: Product.objects.get(pk=pk).delete(); return Response(status=drf_status.HTTP_204_NO_CONTENT)
    except Product.DoesNotExist: return Response({'error': 'Not found'}, status=drf_status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def flutter_sell_product(request, pk):
    try: product = Product.objects.get(pk=pk)
    except Product.DoesNotExist: return Response({'error': 'Not found'}, status=drf_status.HTTP_404_NOT_FOUND)
    qty = float(request.data.get('quantity_sold', 0))
    if qty <= 0 or qty > product.quantity: return Response({'error': 'Invalid quantity'}, status=drf_status.HTTP_400_BAD_REQUEST)
    Sale.objects.create(product=product, quantity_sold=qty, total_price=qty * product.price)
    product.quantity -= qty; product.save()
    return Response({'message': f'Sold {qty} {product.unit} of {product.name}', 'remaining': product.quantity})
# STAFF DASHBOARD
def staff_dashboard(request):
    if not is_staff_member(request):
        return redirect('user_login')
    
    staff_obj = Staff.objects.get(staff_id=request.session['staff_id'])
    # Get customers referred by this staff member
    referred_customers = User.objects.filter(profile__referred_by=staff_obj)
    
    customer_data = []
    total_referral_volume = 0
    total_pending_count = 0

    for customer in referred_customers:
        # Calculate ALL total spending for this customer (regardless of staff assistant)
        sales = Sale.objects.filter(customer=customer)
        total_spent = sales.aggregate(total=Sum('total_price'))['total'] or 0
        total_referral_volume += total_spent
        
        # Check if all bills are given
        pending_bills = sales.filter(bill_given=False).exists()
        if pending_bills:
            total_pending_count += 1
        
        customer_data.append({
            'user': customer,
            'total_spent': total_spent,
            'pending_bills': pending_bills,
            'last_purchase': sales.order_by('-sale_date').first().sale_date if sales.exists() else None
        })
    
    # NEW: Fetch recent purchases across ALL referred customers for the dashboard feed
    recent_purchases = Sale.objects.filter(customer__profile__referred_by=staff_obj).order_by('-sale_date')[:15]
    
    # NEW: Fetch movement and depot data for Staff Dashboard (Depot Admin view)
    from .models import Warehouse, StockArrival, StockTransferLog
    warehouses = Warehouse.objects.prefetch_related('stocks__product').all()
    recent_arrivals = StockArrival.objects.filter(status='Confirmed').prefetch_related('items__product').order_by('-arrival_date')[:5]
    recent_transfers = StockTransferLog.objects.select_related('product', 'from_warehouse', 'to_warehouse').order_by('-transferred_at')[:5]

    return render(request, 'staff_dashboard.html', {
        'customers': customer_data,
        'staff': staff_obj,
        'total_referral_volume': total_referral_volume,
        'total_pending_count': total_pending_count,
        'products': Product.objects.all(),
        'recent_purchases': recent_purchases,
        'warehouses': warehouses,
        'recent_arrivals': recent_arrivals,
        'recent_transfers': recent_transfers,
    })

# MARK BILL AS GIVEN
def mark_bill_given(request, customer_id):
    if not is_staff_member(request):
        return redirect('user_login')
        
    staff_obj = Staff.objects.get(staff_id=request.session['staff_id'])
    customer = User.objects.get(id=customer_id)
    # Mark all sales for this customer as bill given
    Sale.objects.filter(customer=customer, bill_given=False).update(bill_given=True)
    messages.success(request, f"All pending bills for {customer.username} marked as given.")
    return redirect('staff_dashboard')

# CUSTOMER PURCHASE DETAIL (STAFF ONLY)
def customer_purchase_detail(request, customer_id):
    if not is_staff_member(request):
        return redirect('user_login')
    
    staff_obj = Staff.objects.get(staff_id=request.session['staff_id'])
    customer = User.objects.get(id=customer_id)
    
    # Verify this customer was referred by this staff
    if customer.profile.referred_by != staff_obj:
        messages.error(request, "Access denied. You can only view details for your referred customers.")
        return redirect('staff_dashboard')
    
    # Fetch ALL sales history for this customer
    sales = Sale.objects.filter(customer=customer).order_by('-sale_date')
    total_spent = sales.aggregate(total=Sum('total_price'))['total'] or 0
    
    return render(request, 'customer_purchase_detail.html', {
        'customer': customer,
        'sales': sales,
        'total_spent': total_spent,
        'staff': staff_obj
    })

# PROCUREMENT DASHBOARD
@login_required
@user_passes_test(is_admin)
# WAREHOUSE MANAGEMENT
@login_required
@user_passes_test(is_depot_manager)
def warehouse_management(request):
    from .models import Warehouse, WarehouseStock, Product, StockTransferLog
    
    if request.method == "POST":
        action = request.POST.get('action')
        if action == 'transfer':
            try:
                product_id = request.POST.get('product')
                from_wh_id = request.POST.get('from_warehouse')
                to_wh_id = request.POST.get('to_warehouse')
                qty = float(request.POST.get('quantity', 0))
                notes = request.POST.get('notes', '').strip()
                
                product = Product.objects.get(id=product_id)
                from_wh = Warehouse.objects.get(id=from_wh_id)
                to_wh = Warehouse.objects.get(id=to_wh_id)

                if from_wh.id == to_wh.id:
                    messages.error(request, "Source and destination depots must be different.")
                    return redirect('warehouse_management')
                
                from_stock, _ = WarehouseStock.objects.get_or_create(warehouse=from_wh, product=product)
                to_stock, _ = WarehouseStock.objects.get_or_create(warehouse=to_wh, product=product)
                
                if from_stock.quantity >= qty and qty > 0:
                    from_stock.quantity -= qty
                    to_stock.quantity += qty
                    from_stock.save()
                    to_stock.save()
                    # Log the transfer
                    StockTransferLog.objects.create(
                        from_warehouse=from_wh,
                        to_warehouse=to_wh,
                        product=product,
                        quantity=qty,
                        transferred_by=request.user,
                        vehicle_no=request.POST.get('vehicle_no', '').strip() or None,
                        driver_name=request.POST.get('driver_name', '').strip() or None,
                        notes=notes or None
                    )
                    messages.success(request, f"Transferred {qty} {product.unit} of {product.name} → {from_wh.name} to {to_wh.name}.")
                else:
                    messages.error(request, f"Insufficient stock in {from_wh.name}. Available: {from_stock.quantity} {product.unit}.")
                    
            except Exception as e:
                messages.error(request, f"Transfer failed: {str(e)}")
            return redirect('warehouse_management')

    warehouses = Warehouse.objects.all()
    stocks = WarehouseStock.objects.select_related('product', 'warehouse').order_by('warehouse__name', 'product__name')
    products = Product.objects.all()
    transfer_logs = StockTransferLog.objects.select_related('product', 'from_warehouse', 'to_warehouse', 'transferred_by').order_by('-transferred_at')[:30]
    
    # Calculate Master Godown Aggregate Stock
    from django.db.models import Sum
    master_stocks = WarehouseStock.objects.values('product__name', 'product__unit').annotate(
        total_quantity=Sum('quantity')
    ).order_by('product__name')
    
    return render(request, 'warehouse_management.html', {
        'warehouses': warehouses,
        'stocks': stocks,
        'products': products,
        'transfer_logs': transfer_logs,
        'master_stocks': master_stocks,
    })


# STOCK ARRIVALS (Supplyco Inbound Allocation)
@login_required
@user_passes_test(is_depot_manager)
def stock_arrivals(request):
    from .models import StockArrival, StockArrivalItem, Warehouse, WarehouseStock

    if request.method == "POST":
        action = request.POST.get('action')

        # ─── LOG A NEW ARRIVAL ───────────────────────────────────────
        if action == 'log_arrival':
            try:
                warehouse_id = request.POST.get('warehouse')
                notes = request.POST.get('notes', '').strip()
                product_ids = request.POST.getlist('product_id')
                quantities = request.POST.getlist('quantity')

                if not product_ids:
                    messages.error(request, "Please add at least one product to the arrival.")
                    return redirect('stock_arrivals')

                warehouse = Warehouse.objects.get(id=warehouse_id)
                arrival = StockArrival.objects.create(
                    warehouse=warehouse,
                    received_by=request.user,
                    vehicle_no=request.POST.get('vehicle_no', '').strip(),
                    driver_name=request.POST.get('driver_name', '').strip(),
                    expected_arrival=request.POST.get('expected_arrival') or None,
                    notes=notes,
                    status='Pending'
                )
                for pid, qty in zip(product_ids, quantities):
                    try:
                        product = Product.objects.get(id=pid)
                        qty_float = float(qty)
                        if qty_float > 0:
                            StockArrivalItem.objects.create(arrival=arrival, product=product, quantity=qty_float)
                    except (Product.DoesNotExist, ValueError):
                        continue

                messages.success(request, f"Inbound Allocation #{arrival.id} logged as PENDING. Please verify and CONFIRM to update depot stock.")
            except Exception as e:
                messages.error(request, f"Failed to log arrival: {str(e)}")
            return redirect('stock_arrivals')

        # ─── CONFIRM ARRIVAL (updates stock) ─────────────────────────
        elif action == 'confirm':
            arrival_id = request.POST.get('arrival_id')
            try:
                arrival = StockArrival.objects.get(id=arrival_id)
                if arrival.status != 'Pending':
                    messages.warning(request, f"Arrival #{arrival.id} is already {arrival.status}.")
                    return redirect('stock_arrivals')

                arrival.status = 'Confirmed'
                arrival.save()

                for item in arrival.items.all():
                    p = item.product
                    p.quantity += item.quantity
                    p.save()  # This triggers WebSocket broadcast to all dashboards

                    # Also update WarehouseStock for the specific depot
                    if arrival.warehouse:
                        stock_entry, _ = WarehouseStock.objects.get_or_create(
                            warehouse=arrival.warehouse, product=p
                        )
                        stock_entry.quantity += item.quantity
                        stock_entry.save()

                messages.success(request, f"Inventory Verified! Arrival #{arrival.id} confirmed. System quantities updated across all dashboards.")
            except StockArrival.DoesNotExist:
                messages.error(request, "Arrival record not found.")
            return redirect('stock_arrivals')

        # ─── REJECT ARRIVAL ──────────────────────────────────────────
        elif action == 'reject':
            arrival_id = request.POST.get('arrival_id')
            try:
                arrival = StockArrival.objects.get(id=arrival_id)
                arrival.status = 'Rejected'
                arrival.save()
                messages.warning(request, f"Arrival #{arrival.id} has been rejected.")
            except StockArrival.DoesNotExist:
                messages.error(request, "Arrival record not found.")
            return redirect('stock_arrivals')

        # ─── DELETE ARRIVAL (Pending or Rejected only) ────────────────
        elif action == 'delete':
            arrival_id = request.POST.get('arrival_id')
            try:
                arrival = StockArrival.objects.get(id=arrival_id)
                if arrival.status == 'Confirmed':
                    messages.error(request, f"Cannot delete a Confirmed arrival (#{arrival.id}). It is part of the audit trail.")
                else:
                    arrival.delete()
                    messages.success(request, f"Arrival #{arrival_id} deleted.")
            except StockArrival.DoesNotExist:
                messages.error(request, "Arrival not found.")
            return redirect('stock_arrivals')

    arrivals = StockArrival.objects.prefetch_related('items__product').order_by('-arrival_date')
    warehouses = Warehouse.objects.all()
    products = Product.objects.all()

    return render(request, 'stock_arrivals.html', {
        'arrivals': arrivals,
        'warehouses': warehouses,
        'products': products,
    })

