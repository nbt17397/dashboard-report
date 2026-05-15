from django.contrib import admin
from import_export.admin import ImportExportModelAdmin
from .models import (
    BUPerformance, BUPerformanceDaily, Branch, PurchaseDetail, Warehouse, Customer, Employee, 
    Product, BusinessUnit, SalesTransaction, Supplier, SupplierDebt, SupplierGroup,
    AccountDetail, ReceivablesAgeing, InventorySummary
)
from .resources import PurchaseDetailResource, SalesTransactionResource, SupplierDebtResource, AccountDetailResource, ReceivablesAgeingResource, InventorySummaryResource
from .tasks import update_single_bu_performance, sync_warehouse_inventory_data
from django.contrib import admin, messages
from datetime import datetime
import calendar

# Cấu hình hiển thị cho BusinessUnit (Có trưởng BU)
@admin.register(BusinessUnit)
class BusinessUnitAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'manager')
    search_fields = ('code', 'name', 'manager')

# Cấu hình hiển thị cho Giao dịch bán hàng
@admin.register(SalesTransaction)
class SalesTransactionAdmin(ImportExportModelAdmin):
    resource_class = SalesTransactionResource
    # 1. Các cột hiển thị ngoài danh sách
    list_display = (
        'doc_id', 'posting_date', 'customer', 'product', 
        'quantity', 'sales_amount', 'actual_sales', 'employee'
    )
    
    # 2. Bộ lọc nhanh bên tay phải
    list_filter = ('posting_date', 'branch', 'warehouse', 'business_unit')
    
    # 3. Ô tìm kiếm
    search_fields = ('doc_id', 'customer__name', 'product__name', 'employee__name')
    
    # 4. Gom nhóm các trường khi chỉnh sửa/thêm mới
    fieldsets = (
        ('Thông tin chứng từ', {
            'fields': ('posting_date', 'doc_id', 'branch', 'warehouse', 'business_unit')
        }),
        ('Thông tin đối tượng', {
            'fields': ('customer', 'product', 'employee')
        }),
        ('Số liệu tài chính', {
            'fields': (
                ('quantity', 'unit_price'), 
                ('sales_amount', 'actual_sales'),
                ('tax_percent', 'tax_amount'),
                ('discount_amount', 'discount_acc')
            )
        }),
        ('Kế toán', {
            'fields': ('debit_acc', 'credit_acc'),
            'classes': ('collapse',), # Cho phép ẩn/hiện cho gọn
        }),
    )

# Đăng ký các bảng danh mục còn lại một cách nhanh chóng
@admin.register(Customer)
class CustomerAdmin(ImportExportModelAdmin):
    list_display = ('code', 'name')
    search_fields = ('code', 'name')

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'unit')
    search_fields = ('code', 'name')

admin.site.register(Branch)
@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = (
        'code', 'name', 'business_unit', 
        'inventory_opening_value', 'inventory_in_value', 
        'inventory_out_value', 'inventory_value_actual'
    )
    list_filter = ('business_unit',)
    actions = ['trigger_sync_inventory']

    @admin.action(description='🔄 Đồng bộ tồn kho từ Inventory Summary')
    def trigger_sync_inventory(self, request, queryset):
        # queryset chứa các Warehouse được tích chọn
        count = queryset.count()
        
        # Gọi hàm xử lý (có thể truyền queryset vào hàm hoặc xử lý tại đây)
        for wh in queryset:
            # Bạn có thể gọi trực tiếp logic tính toán cho từng kho
            from django.db.models import Sum
            from .models import InventorySummary
            
            data = InventorySummary.objects.filter(warehouse=wh).aggregate(
                opening=Sum('opening_value'),
                in_val=Sum('in_value'),
                out_val=Sum('out_value'),
                closing=Sum('closing_value')
            )
            
            wh.inventory_opening_value = data['opening'] or 0
            wh.inventory_in_value = data['in_val'] or 0
            wh.inventory_out_value = data['out_val'] or 0
            wh.inventory_value_actual = data['closing'] or 0
            wh.save()

        self.message_user(
            request, 
            f"Đã cập nhật dữ liệu tồn kho thành công cho {count} kho.", 
            messages.SUCCESS
        )
admin.site.register(Employee)

class BUPerformanceDailyInline(admin.TabularInline):
    model = BUPerformanceDaily
    # Thiết kế chỉ cho xem, không cho sửa/xóa trực tiếp ở đây (tùy chọn)
    extra = 0 # Không hiện các dòng trống để thêm mới
    readonly_fields = ('date', 'daily_revenue', 'daily_collection')
    can_delete = False
    
    # Sắp xếp ngày mới nhất lên đầu
    ordering = ('-date',)

@admin.register(BUPerformance)
class BUPerformanceAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'mtd_revenue_actual', 'mtd_collection_actual', 'year', 'month')
    list_filter = ('year', 'month', 'business_unit')
    inlines = [BUPerformanceDailyInline]
    actions = ['trigger_update_data']

    @admin.action(description='🚀 Cập nhật số liệu thực tế (Tháng & Ngày)')
    def trigger_update_data(self, request, queryset):
        success_count = 0
        today = datetime.now().date()
        
        for obj in queryset:
            try:
                # 1. Xác định ngày mục tiêu (target_date)
                # Nếu là tháng/năm hiện tại thì lấy ngày hôm nay
                if obj.month == today.month and obj.year == today.year:
                    target_date = today
                else:
                    # Nếu là tháng cũ, lấy ngày cuối cùng của tháng đó để chốt số liệu
                    last_day = calendar.monthrange(obj.year, obj.month)[1]
                    target_date = datetime(obj.year, obj.month, last_day).date()

                # 2. Gọi hàm xử lý (nên dùng .delay nếu chạy qua Celery)
                # Ở đây gọi trực tiếp để tránh lỗi kết nối Redis nếu hệ thống chưa ổn định
                update_single_bu_performance(
                    bu_id=obj.business_unit.id if obj.business_unit else None,
                    month=obj.month,
                    year=obj.year,
                    target_date_str=target_date.strftime('%Y-%m-%d')
                )
                
                success_count += 1
            except Exception as e:
                self.message_user(
                    request, 
                    f"Lỗi khi cập nhật dòng {obj}: {str(e)}", 
                    messages.ERROR
                )
                continue

        self.message_user(
            request, 
            f"Đã cập nhật thành công số liệu cho {success_count} mục (Bao gồm bảng Tháng và Ngày).", 
            messages.SUCCESS
        )

@admin.register(SupplierDebt)
class SupplierDebtAdmin(ImportExportModelAdmin):
    resource_class = SupplierDebtResource
    list_display = ('supplier', 'opening_debit', 'opening_credit', 'incurred_debit', 'incurred_credit', 'closing_debit', 'closing_credit')
    search_fields = ('supplier__code', 'supplier__name')

admin.site.register(Supplier)
admin.site.register(SupplierGroup)

@admin.register(AccountDetail)
class AccountDetailAdmin(ImportExportModelAdmin):
    resource_class = AccountDetailResource
    list_display = ('posting_date', 'doc_id', 'account_number', 'debit_amount', 'credit_amount', 'branch', 'business_unit')
    list_filter = ('branch', 'business_unit', 'account_number')
    search_fields = ('doc_id', 'account_number')
    

@admin.register(ReceivablesAgeing)
class ReceivablesAgeingAdmin(ImportExportModelAdmin):
    resource_class = ReceivablesAgeingResource
    list_display = ('customer', 'doc_date', 'total_debt', 'overdue_total', 'branch')
    search_fields = ('customer__name', 'customer__code')
    list_filter = ('branch', 'doc_date')

@admin.register(InventorySummary)
class InventorySummaryAdmin(ImportExportModelAdmin):
    resource_class = InventorySummaryResource
    list_display = ('warehouse', 'product', 'opening_quantity', 'closing_quantity', 'closing_value')
    list_filter = ('warehouse', 'product__group')
    search_fields = ('product__code', 'product__name', 'warehouse__name')

@admin.register(PurchaseDetail)
class PurchaseDetailAdmin(ImportExportModelAdmin):
    resource_class = PurchaseDetailResource # Kết nối với Full Code Resource ở turn trước
    
    # Hiển thị các cột quan trọng ra danh sách
    list_display = (
        'posting_date', 'doc_number', 'supplier', 'product', 
        'quantity', 'total_value', 'business_unit', 'org_unit_name'
    )
    
    # Bộ lọc bên phải màn hình
    list_filter = ('posting_date', 'business_unit', 'warehouse', 'supplier')
    
    # Ô tìm kiếm
    search_fields = ('doc_number', 'product__code', 'product__name', 'supplier__name')
    
    # Phân nhóm giao diện nhập liệu
    fieldsets = (
        ('Thông tin chứng từ', {
            'fields': ('posting_date', 'doc_date', 'doc_number', 'description')
        }),
        ('Đối tượng & Danh mục', {
            'fields': ('supplier', 'warehouse', 'product', 'business_unit')
        }),
        ('Đơn vị (Lưu trực tiếp)', {
            'fields': ('org_unit_code', 'org_unit_name')
        }),
        ('Số liệu tài chính', {
            'fields': (('quantity', 'unit_price'), ('purchase_value', 'vat_value', 'total_value'), ('debit_account', 'credit_account'))
        }),
    )