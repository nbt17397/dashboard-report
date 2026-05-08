from django.db import models

class Branch(models.Model):
    name = models.CharField(max_length=255, verbose_name="Chi nhánh")
    
    def __str__(self):
        return self.name
    
class Warehouse(models.Model):
    code = models.CharField(max_length=50, unique=True, verbose_name="Mã kho")
    name = models.CharField(max_length=255, verbose_name="Tên kho")
    
    def __str__(self):
        return f"{self.code} - {self.name}"
    
class CustomerGroup(models.Model):
    code = models.CharField(max_length=50, unique=True, verbose_name="Mã nhóm khách hàng")
    name = models.CharField(max_length=255, verbose_name="Tên nhóm khách hàng")

    def __str__(self):
        return self.name
    
class Customer(models.Model):
    code = models.CharField(max_length=50, unique=True, verbose_name="Mã khách hàng")
    name = models.CharField(max_length=255, verbose_name="Tên khách hàng")
    group = models.ForeignKey(CustomerGroup, on_delete=models.SET_NULL, null=True, blank=True)
    address = models.TextField(verbose_name="Địa điểm giao hàng")

    has_revenue = models.BooleanField(
        default=True,
        verbose_name="Có ghi nhận doanh thu"
    )

    def __str__(self):
        return f"{self.code} - {self.name}"
    
class Employee(models.Model):
    code = models.CharField(max_length=50, unique=True, verbose_name="Mã nhân viên")
    name = models.CharField(max_length=255, verbose_name="Tên nhân viên")

    def __str__(self):
        return self.name
    
class MaterialGroup(models.Model):
    code = models.CharField(max_length=50, unique=True, verbose_name="Mã nhóm VTHH")
    name = models.CharField(max_length=255, verbose_name="Tên nhóm VTHH")
    origin = models.CharField(max_length=100, verbose_name="Nguồn gốc")

    def __str__(self):
        return self.name
    
class Product(models.Model):
    code = models.CharField(max_length=100, unique=True, verbose_name="Mã hàng")
    name = models.CharField(max_length=255, verbose_name="Tên hàng")
    unit = models.CharField(max_length=20, verbose_name="ĐVT")
    group = models.ForeignKey(MaterialGroup, on_delete=models.CASCADE, verbose_name="Nhóm VTHH")
    brand = models.CharField(max_length=100, blank=True, verbose_name="Nhãn hiệu (Trường mở rộng)")

    def __str__(self):
        return self.code
    
class BusinessUnit(models.Model):
    code = models.CharField(max_length=50, unique=True, verbose_name="Mã thống kê")
    name = models.CharField(max_length=255, verbose_name="Tên thống kê")
    manager = models.CharField(max_length=255, verbose_name="Trưởng BU", null=True, blank=True) # Thêm trưởng BU
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="children"
    )
    is_main = models.BooleanField(default=False, verbose_name="BU chính")

    def __str__(self):
        return f"{self.code} - {self.name}"
    
class SalesTransaction(models.Model):
    posting_date = models.DateField(verbose_name="Ngày hạch toán")
    doc_id = models.CharField(max_length=100, verbose_name="Số chứng từ")
    
    # Quan hệ
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, verbose_name="Khách hàng")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name="Hàng hóa")
    employee = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, verbose_name="Nhân viên")
    warehouse = models.ForeignKey(Warehouse, on_delete=models.SET_NULL, null=True, verbose_name="Kho")
    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, verbose_name="Chi nhánh")
    business_unit = models.ForeignKey(BusinessUnit, on_delete=models.SET_NULL, null=True, verbose_name="BU")

    # Dữ liệu số (giữ lại từ excel)
    quantity = models.FloatField(default=0, verbose_name="Tổng số lượng bán")
    unit_price = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Đơn giá")
    sales_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Doanh số bán")
    tax_percent = models.FloatField(default=0, verbose_name="% Thuế")
    tax_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Thuế GTGT")
    
    # Các tài khoản kế toán
    debit_acc = models.CharField(max_length=20, verbose_name="TK Nợ")
    credit_acc = models.CharField(max_length=20, verbose_name="TK Có")
    discount_acc = models.CharField(max_length=20, null=True, blank=True, verbose_name="TK Chiết khấu")
    discount_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Chiết khấu")

    # Các trường thông tin thêm
    actual_sales = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Doanh số thực tế")

    def __str__(self):
        return f"{self.doc_id} - {self.customer.name}"
    
    class Meta:
        verbose_name = "Chi tiết bán hàng"
        verbose_name_plural = "Bảng chi tiết bán hàng"
    
class SupplierGroup(models.Model):
    code = models.CharField(max_length=50, unique=True, verbose_name="Mã nhóm NCC")
    name = models.CharField(max_length=255, verbose_name="Tên nhóm NCC", null=True, blank=True)

    def __str__(self):
        return self.code

class Supplier(models.Model):
    code = models.CharField(max_length=50, unique=True, verbose_name="Mã nhà cung cấp")
    name = models.CharField(max_length=255, verbose_name="Tên nhà cung cấp")
    group = models.ForeignKey(SupplierGroup, on_delete=models.SET_NULL, null=True, blank=True, related_name='suppliers')

    def __str__(self):
        return f"{self.code} - {self.name}"

class SupplierDebt(models.Model):
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, verbose_name="Nhà cung cấp")
    
    # Số dư đầu kỳ
    opening_debit = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="Đầu kỳ - Nợ")
    opening_credit = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="Đầu kỳ - Có")
    
    # Phát sinh
    incurred_debit = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="Phát sinh - Nợ")
    incurred_credit = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="Phát sinh - Có")
    
    # Số dư cuối kỳ
    closing_debit = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="Cuối kỳ - Nợ")
    closing_credit = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="Cuối kỳ - Có")
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Công nợ NCC"
        verbose_name_plural = "Bảng công nợ nhà cung cấp"


class AccountDetail(models.Model):
    posting_date = models.DateField(verbose_name="Ngày hạch toán", null=True, blank=True)
    doc_id = models.CharField(max_length=50, verbose_name="Số chứng từ")
    
    # Tài khoản (lưu trực tiếp)
    account_number = models.CharField(max_length=20, verbose_name="Tài khoản")
    account_name = models.CharField(max_length=255, verbose_name="Tên tài khoản")
    offset_account = models.CharField(max_length=20, verbose_name="TK đối ứng", null=True, blank=True)
    
    # Số tiền
    debit_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="Phát sinh Nợ")
    credit_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="Phát sinh Có")
    balance_debit = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="Dư Nợ")
    balance_credit = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="Dư Có")
    
    # Liên kết bảng (ForeignKey)
    business_unit = models.ForeignKey(BusinessUnit, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Mã thống kê")
    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Chi nhánh")
    
    # Các trường thông tin đơn vị (dạng text)
    unit_code = models.CharField(max_length=50, verbose_name="Mã đơn vị", null=True, blank=True)
    unit_name = models.CharField(max_length=255, verbose_name="Tên đơn vị", null=True, blank=True)
    unreasonable_cost = models.BooleanField(default=False, verbose_name="CP không hợp lý")

    customer = models.ForeignKey(
        Customer,
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        verbose_name="Khách hàng (Đối tượng)"
    )

    class Meta:
        verbose_name = "Sổ chi tiết tài khoản 111-112"
        verbose_name_plural = "Sổ chi tiết các tài khoản 111-112"


class ReceivablesAgeing(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, verbose_name="Khách hàng")
    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Chi nhánh")
    
    doc_date = models.DateField(verbose_name="Ngày chứng từ", null=True, blank=True)
    
    # Số liệu tổng quát
    total_debt = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="Tổng nợ")
    no_due_limit = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="Không có hạn nợ")
    
    # Nợ TRƯỚC HẠN
    due_0_7 = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="Trước hạn 0-7 ngày")
    due_8_14 = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="Trước hạn 8-14 ngày")
    due_15_21 = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="Trước hạn 15-21 ngày")
    due_22_28 = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="Trước hạn 22-28 ngày")
    due_29_60 = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="Trước hạn 29-60 ngày")
    due_above_60 = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="Trước hạn trên 60 ngày")
    due_total = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="Tổng nợ trước hạn")
    
    # Nợ QUÁ HẠN
    overdue_0_14 = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="Quá hạn 0-14 ngày")
    overdue_15_30 = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="Quá hạn 15-30 ngày")
    overdue_31_45 = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="Quá hạn 31-45 ngày")
    overdue_46_60 = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="Quá hạn 46-60 ngày")
    overdue_61_90 = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="Quá hạn 61-90 ngày")
    overdue_91_120 = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="Quá hạn 91-120 ngày")
    overdue_above_120 = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="Quá hạn trên 120 ngày")
    overdue_total = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="Tổng nợ quá hạn")

    class Meta:
        verbose_name = "Chi tiết tuổi nợ"
        verbose_name_plural = "Bảng chi tiết tuổi nợ"

class InventorySummary(models.Model):
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, verbose_name="Kho")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name="Hàng hóa")
    
    # Đầu kỳ
    opening_quantity = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="Đầu kỳ - SL")
    opening_value = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="Đầu kỳ - Giá trị")
    
    # Nhập kho
    in_quantity = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="Nhập kho - SL")
    in_value = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="Nhập kho - Giá trị")
    
    # Xuất kho
    out_quantity = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="Xuất kho - SL")
    out_value = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="Xuất kho - Giá trị")
    
    # Cuối kỳ
    closing_quantity = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="Cuối kỳ - SL")
    closing_value = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="Cuối kỳ - Giá trị")

    # Các trường mở rộng từ file
    ext_field1 = models.CharField(max_length=255, null=True, blank=True, verbose_name="Trường mở rộng 1")
    ext_field2 = models.CharField(max_length=255, null=True, blank=True, verbose_name="Trường mở rộng 2")

    class Meta:
        verbose_name = "Tổng hợp tồn kho"
        verbose_name_plural = "Bảng tổng hợp tồn kho"


class PurchaseDetail(models.Model):
    posting_date = models.DateField(verbose_name="Ngày hạch toán")
    doc_date = models.DateField(verbose_name="Ngày chứng từ")
    doc_number = models.CharField(max_length=100, verbose_name="Số chứng từ")
    description = models.TextField(null=True, blank=True, verbose_name="Diễn giải")
    
    # Khóa ngoại
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, verbose_name="Nhà cung cấp")
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, verbose_name="Kho", null=True, blank=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name="Hàng hóa")
    
    # Mã thống kê liên kết đến bảng BusinessUnit
    business_unit = models.ForeignKey(BusinessUnit, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Mã thống kê (BU)")
    
    # Đơn vị lưu trực tiếp text
    org_unit_code = models.CharField(max_length=100, null=True, blank=True, verbose_name="Mã đơn vị")
    org_unit_name = models.CharField(max_length=255, null=True, blank=True, verbose_name="Tên đơn vị")
    
    # Số liệu
    quantity = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    unit_price = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    purchase_value = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    vat_value = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    total_value = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    
    debit_account = models.CharField(max_length=20)
    credit_account = models.CharField(max_length=20)

    class Meta:
        verbose_name = "Chi tiết mua hàng"
        verbose_name_plural = "Sổ chi tiết mua hàng"


class BUPerformance(models.Model):
    business_unit = models.ForeignKey(
        BusinessUnit, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True, 
        verbose_name="Đơn vị kinh doanh (Null = Tổng)"
    )
    month = models.PositiveSmallIntegerField(verbose_name="Tháng")
    year = models.PositiveIntegerField(verbose_name="Năm")

    # 1. Doanh thu MTD
    mtd_revenue_plan = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="Doanh thu MTD (Kế hoạch)")
    mtd_revenue_actual = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="Doanh thu MTD (Thực tế)")

    # 2. Thu tiền tháng
    mtd_collection_plan = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="Thu tiền tháng (Kế hoạch)")
    mtd_collection_actual = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="Thu tiền tháng (Thực tế)")

    # 3. Giá trị tồn kho
    inventory_value_plan = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="Giá trị tồn kho (Kế hoạch)")
    inventory_value_actual = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="Giá trị tồn kho (Thực tế)")

    # 4. Nợ ngân hàng
    bank_debt_plan = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="Nợ ngân hàng (Kế hoạch)")
    bank_debt_actual = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="Nợ ngân hàng (Thực tế)")

    # 5. Chi phí vận hành (OPEX)
    opex_plan = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="Chi phí vận hành (Kế hoạch)")
    opex_actual = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="Chi phí vận hành (Thực tế)")

    # 6. Tiền cuối kỳ
    cash_balance_plan = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="Tiền cuối kỳ (Kế hoạch)")
    cash_balance_actual = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="Tiền cuối kỳ (Thực tế)")

    class Meta:
        verbose_name = "Chỉ số hiệu suất BU"
        verbose_name_plural = "Bảng theo dõi hiệu suất BU"
        unique_together = ('business_unit', 'month', 'year')

    def __str__(self):
        bu_name = self.business_unit.code if self.business_unit else "TỔNG TOÀN CÔNG TY"
        return f"{bu_name} - Th{self.month}/{self.year}"
    

class BUPerformanceDaily(models.Model):
    performance_month = models.ForeignKey(
        BUPerformance, 
        on_delete=models.CASCADE, 
        related_name='daily_logs'
    )
    date = models.DateField(verbose_name="Ngày")
    
    # Chỉ lưu phát sinh thực tế của riêng ngày đó
    daily_revenue = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="Doanh thu trong ngày")
    daily_collection = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="Thực thu trong ngày")

    class Meta:
        verbose_name = "Hiệu suất BU theo ngày"
        unique_together = ('performance_month', 'date')
        ordering = ['-date']