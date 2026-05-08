from celery import shared_task
from django.db.models import Sum, Q
from .models import BusinessUnit, BUPerformance, InventorySummary, SalesTransaction, AccountDetail, BUPerformanceDaily
from datetime import datetime, timedelta
import calendar

@shared_task
def update_single_bu_performance(bu_id, month=None, year=None, target_date_str=None):
    # --- 1. XỬ LÝ THỜI GIAN ---
    today = datetime.now()
    month = int(month) if month else today.month
    year = int(year) if year else today.year
    
    if target_date_str:
        target_date = datetime.strptime(target_date_str, '%Y-%m-%d').date()
    else:
        if month == today.month and year == today.year:
            target_date = today.date()
        else:
            last_day = calendar.monthrange(year, month)[1]
            target_date = datetime(year, month, last_day).date()

    # --- 2. XÁC ĐỊNH PHẠM VI (GLOBAL / SUB-BU) ---
    is_global = False
    if bu_id is None:
        is_global = True
    else:
        bu = BusinessUnit.objects.filter(id=bu_id).first()
        if bu and bu.parent_id is None:
            is_global = True

    customer_rev_filter = Q(customer__has_revenue=True)

    # --- 3. TÍNH DOANH THU & THỰC THU (LŨY KẾ THÁNG) ---
    base_filter = Q(posting_date__month=month, posting_date__year=year) & customer_rev_filter
    if not is_global:
        base_filter &= Q(business_unit_id=bu_id)

    # Doanh thu tháng
    sales_qs = SalesTransaction.objects.filter(base_filter)
    rev_actual = sales_qs.aggregate(total=Sum('actual_sales'))['total'] or 0


    # Thực thu tháng
    account_qs = AccountDetail.objects.filter(base_filter)
    cash_cond = Q(account_number__startswith='111') | Q(account_number__startswith='112')
    offset_cond = Q(offset_account__startswith='1311') | Q(offset_account__startswith='1312')
    
    match_qs = account_qs.filter(cash_cond & offset_cond)
    sums = match_qs.aggregate(d=Sum('debit_amount'), c=Sum('credit_amount'))
    coll_actual = (sums['d'] or 0) - (sums['c'] or 0)

    # Tồn kho
    inventory_actual = 0
    if is_global:
        inventory_actual = InventorySummary.objects.aggregate(
            total=Sum('closing_value')
        )['total'] or 0

    # --- 4. CẬP NHẬT DATABASE (BẢNG THÁNG) ---
    performance, _ = BUPerformance.objects.update_or_create(
        business_unit_id=bu_id,
        month=month,
        year=year,
        defaults={
            'mtd_revenue_actual': rev_actual,
            'mtd_collection_actual': coll_actual,
            'inventory_value_actual': inventory_actual
        }
    )

    # --- 5. TÍNH VÀ CẬP NHẬT CHO TẤT CẢ CÁC NGÀY TRONG THÁNG (DAILY ACTUAL) ---
    # Chạy vòng lặp từ ngày 1 đến target_date
    current_date = datetime(year, month, 1).date()
    
    while current_date <= target_date:
        daily_filter = Q(posting_date=current_date)
        if not is_global:
            daily_filter &= Q(business_unit_id=bu_id)
        
        # Doanh thu ngày (áp dụng customer_rev_filter tương tự như tháng)
        daily_rev = SalesTransaction.objects.filter(daily_filter & customer_rev_filter).aggregate(
            total=Sum('sales_amount')
        )['total'] or 0

        # Thực thu ngày
        daily_acc_qs = AccountDetail.objects.filter(daily_filter & customer_rev_filter).filter(cash_cond & offset_cond)
        daily_sums = daily_acc_qs.aggregate(d=Sum('debit_amount'), c=Sum('credit_amount'))
        daily_coll = (daily_sums['d'] or 0) - (daily_sums['c'] or 0)

        # Cập nhật bảng Daily
        BUPerformanceDaily.objects.update_or_create(
            performance_month=performance,
            date=current_date,
            defaults={
                'daily_revenue': daily_rev,
                'daily_collection': daily_coll,
            }
        )
        # Tăng lên 1 ngày
        current_date += timedelta(days=1)
    
    bu_name = "TỔNG CÔNG TY" if is_global else f"BU ID {bu_id}"
    return f"Updated {bu_name}: Month Rev={rev_actual} | All days up to {target_date} updated"