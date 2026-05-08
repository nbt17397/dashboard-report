import re
from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget, DateWidget, DecimalWidget, BooleanWidget
from .models import (
    Branch, PurchaseDetail, Warehouse, Customer, Employee, 
    Product, BusinessUnit, SalesTransaction, MaterialGroup, AccountDetail
)
from .models import Supplier, SupplierDebt, SupplierGroup, ReceivablesAgeing, InventorySummary

class SalesTransactionResource(resources.ModelResource):
    # --- 1. MAPPING FIELDS ---
    posting_date = fields.Field(
        attribute='posting_date', 
        column_name='Ngày hạch toán', 
        widget=DateWidget(format='%Y-%m-%d')
    )
    doc_id = fields.Field(attribute='doc_id', column_name='Số chứng từ')
    customer = fields.Field(
        attribute='customer', 
        column_name='Mã khách hàng', 
        widget=ForeignKeyWidget(Customer, 'code')
    )
    product = fields.Field(
        attribute='product', 
        column_name='Mã hàng', 
        widget=ForeignKeyWidget(Product, 'code')
    )
    employee = fields.Field(
        attribute='employee', 
        column_name='Mã nhân viên bán hàng', 
        widget=ForeignKeyWidget(Employee, 'code')
    )
    business_unit = fields.Field(
        attribute='business_unit', 
        column_name='Mã thống kê', 
        widget=ForeignKeyWidget(BusinessUnit, 'code')
    )
    
    # Các trường số liệu
    quantity = fields.Field(attribute='quantity', column_name='Tổng số lượng bán')
    unit_price = fields.Field(attribute='unit_price', column_name='Đơn giá')
    sales_amount = fields.Field(attribute='sales_amount', column_name='Doanh số bán')
    tax_percent = fields.Field(attribute='tax_percent', column_name='%Thuế')
    tax_amount = fields.Field(attribute='tax_amount', column_name='Thuế GTGT')
    debit_acc = fields.Field(attribute='debit_acc', column_name='TK Nợ')
    credit_acc = fields.Field(attribute='credit_acc', column_name='TK Có')
    discount_acc = fields.Field(attribute='discount_acc', column_name='TK chiết khấu')
    discount_amount = fields.Field(attribute='discount_amount', column_name='Chiết khấu')
    actual_sales = fields.Field(attribute='actual_sales', column_name='Doanh số thực tế')

    class Meta:
        model = SalesTransaction
        # KHÔNG khai báo import_id_fields để hệ thống tự tạo mới mọi dòng (không ghi đè)
        import_id_fields = [] 
        
        exclude = ('id',)
        skip_unchanged = False  # Ép buộc import kể cả khi dữ liệu giống hệt
        report_skipped = True

    # --- 2. XỬ LÝ CHẶN DÒNG RÁC ĐẦU VÀ CUỐI FILE ---
    def before_import(self, dataset, **kwargs):
        required_cols = ['Ngày hạch toán', 'Số chứng từ', 'Mã hàng']
        
        # A. Dọn đầu file: Tìm dòng tiêu đề
        header_index = -1
        current_headers = [str(h).strip() if h else "" for h in dataset.headers]
        if not any(col in current_headers for col in required_cols):
            for i, row in enumerate(dataset):
                row_str = [str(cell).strip() if cell else "" for cell in row]
                if any(col in row_str for col in required_cols):
                    header_index = i
                    break

        if header_index >= 0:
            dataset.headers = [str(h).strip() for h in dataset[header_index]]
            for _ in range(header_index + 1):
                del dataset[0]

        # B. Dọn cuối file: Xóa dòng "Tổng cộng" (Duyệt ngược từ dưới lên)
        idx = len(dataset) - 1
        while idx >= 0:
            val = str(dataset[idx][0]).strip() if dataset[idx][0] is not None else ""
            if "Tổng" in val or val == "" or val == "None":
                del dataset[idx]
            else:
                break
            idx -= 1

        # C. Làm sạch Header
        dataset.headers = [
            re.sub(' +', ' ', str(h).replace('\ufeff', '').strip().replace('\n', ' ')) 
            if h else "" for h in dataset.headers
        ]

    # --- 3. TỰ TẠO DANH MỤC VÀ KIỂM TRA DỮ LIỆU ---
    def before_import_row(self, row, **kwargs):
        # Làm sạch dữ liệu trong row
        for key in list(row.keys()):
            if row[key] and isinstance(row[key], str):
                row[key] = row[key].strip()

        # Kiểm tra mã bắt buộc để tránh lỗi Database
        cust_code = row.get('Mã khách hàng')
        prod_code = row.get('Mã hàng')
        
        if not cust_code or not prod_code or str(cust_code).lower() == 'none':
            return None # Bỏ qua dòng trống thực sự

        # 3.1. Tạo Nhóm VTHH
        mat_group_code = row.get('Mã nhóm VTHH')
        material_group = None
        if mat_group_code:
            material_group, _ = MaterialGroup.objects.get_or_create(
                code=mat_group_code,
                defaults={'name': row.get('Tên nhóm VTHH') or 'N/A'}
            )

        # 3.2. Tạo Khách hàng
        Customer.objects.get_or_create(
            code=cust_code,
            defaults={'name': row.get('Tên khách hàng') or 'N/A'}
        )

        # 3.3. Tạo Sản phẩm
        Product.objects.get_or_create(
            code=prod_code,
            defaults={
                'name': row.get('Tên hàng') or 'N/A', 
                'unit': row.get('ĐVT') or 'Cái', 
                'group': material_group
            }
        )

        # 3.4. Các danh mục phụ khác
        emp_code = row.get('Mã nhân viên bán hàng')
        if emp_code:
            Employee.objects.get_or_create(code=emp_code, defaults={'name': row.get('Tên nhân viên bán hàng') or 'N/A'})

        bu_code = row.get('Mã thống kê')
        if bu_code:
            BusinessUnit.objects.get_or_create(code=bu_code, defaults={'name': row.get('Tên thống kê') or 'N/A'})

        if row.get('Chi nhánh'):
            Branch.objects.get_or_create(name=row.get('Chi nhánh'))

        wh_code = row.get('Mã kho')
        if wh_code:
            Warehouse.objects.get_or_create(code=wh_code, defaults={'name': row.get('Tên kho') or 'N/A'})


class SupplierDebtResource(resources.ModelResource):
    supplier = fields.Field(
        attribute='supplier',
        column_name='Mã nhà cung cấp',
        widget=ForeignKeyWidget(Supplier, 'code')
    )
    
    # Mapping chính xác theo các cột đã được xử lý ở before_import
    opening_debit = fields.Field(attribute='opening_debit', column_name='Đầu kỳ_Nợ', widget=DecimalWidget())
    opening_credit = fields.Field(attribute='opening_credit', column_name='Đầu kỳ_Có', widget=DecimalWidget())
    incurred_debit = fields.Field(attribute='incurred_debit', column_name='Phát sinh_Nợ', widget=DecimalWidget())
    incurred_credit = fields.Field(attribute='incurred_credit', column_name='Phát sinh_Có', widget=DecimalWidget())
    closing_debit = fields.Field(attribute='closing_debit', column_name='Cuối kỳ_Nợ', widget=DecimalWidget())
    closing_credit = fields.Field(attribute='closing_credit', column_name='Cuối kỳ_Có', widget=DecimalWidget())

    class Meta:
        model = SupplierDebt
        import_id_fields = [] # Không check trùng để lấy đủ 11k dòng
        skip_unchanged = False
        report_skipped = True

    def before_import(self, dataset, **kwargs):
        # 1. Tìm dòng tiêu đề chính (Mã nhà cung cấp)
        header_index = -1
        for i, row in enumerate(dataset):
            row_vals = [str(c).strip() if c else "" for c in row]
            if 'Mã nhà cung cấp' in row_vals:
                header_index = i
                break
        
        if header_index >= 0:
            # 2. Xử lý tiêu đề 2 tầng (Nợ/Có)
            # Dòng header_index là dòng "Số dư đầu kỳ", "Phát sinh"...
            # Dòng header_index + 1 là dòng "Nợ", "Có"
            main_headers = dataset[header_index]
            sub_headers = dataset[header_index + 1]
            
            new_headers = []
            current_prefix = ""
            
            for m, s in zip(main_headers, sub_headers):
                m_str = str(m).strip() if m else ""
                s_str = str(s).strip() if s else ""
                
                if "Số dư đầu kỳ" in m_str: current_prefix = "Đầu kỳ"
                elif "Phát sinh" in m_str: current_prefix = "Phát sinh"
                elif "Số dư cuối kỳ" in m_str: current_prefix = "Cuối kỳ"
                
                if s_str in ["Nợ", "Có"]:
                    new_headers.append(f"{current_prefix}_{s_str}")
                else:
                    new_headers.append(m_str if m_str else s_str)
            
            dataset.headers = new_headers
            
            # Xóa các dòng tiêu đề và rác
            for _ in range(header_index + 2):
                del dataset[0]

        # 3. Xóa dòng tổng cộng ở cuối
        idx = len(dataset) - 1
        while idx >= 0:
            val = str(dataset[idx][0]).strip() if dataset[idx][0] else ""
            if "Tổng" in val or val == "" or val == "None":
                del dataset[idx]
            else:
                break
            idx -= 1

    def before_import_row(self, row, **kwargs):
        # Tự động tạo Supplier và SupplierGroup nếu chưa có
        sup_code = str(row.get('Mã nhà cung cấp') or '').strip()
        group_code = str(row.get('Mã nhóm nhà cung cấp') or '').strip()
        
        if not sup_code or sup_code == 'None':
            return None

        # Tạo nhóm
        s_group = None
        if group_code:
            s_group, _ = SupplierGroup.objects.get_or_create(code=group_code)

        # Tạo nhà cung cấp
        Supplier.objects.get_or_create(
            code=sup_code,
            defaults={
                'name': row.get('Tên nhà cung cấp') or 'N/A',
                'group': s_group
            }
        )

class AccountDetailResource(resources.ModelResource):
    posting_date = fields.Field(attribute='posting_date', column_name='Ngày hạch toán', widget=DateWidget(format='%Y-%m-%d'))
    doc_id = fields.Field(attribute='doc_id', column_name='Số chứng từ')
    customer = fields.Field(
        attribute='customer',
        column_name='Mã đối tượng',
        widget=ForeignKeyWidget(Customer, 'code')
    )
    
    # Mapping ForeignKeys
    business_unit = fields.Field(
        attribute='business_unit', 
        column_name='Mã thống kê', 
        widget=ForeignKeyWidget(BusinessUnit, 'code')
    )
    branch = fields.Field(
        attribute='branch', 
        column_name='Chi nhánh', 
        widget=ForeignKeyWidget(Branch, 'name')
    )

    account_number = fields.Field(attribute='account_number', column_name='Tài khoản')
    offset_account = fields.Field(attribute='offset_account', column_name='TK đối ứng')
    
    # Mapping các trường khác
    debit_amount = fields.Field(attribute='debit_amount', column_name='Phát sinh Nợ', widget=DecimalWidget())
    credit_amount = fields.Field(attribute='credit_amount', column_name='Phát sinh Có', widget=DecimalWidget())
    unreasonable_cost = fields.Field(attribute='unreasonable_cost', column_name='CP không hợp lý', widget=BooleanWidget())

    class Meta:
        model = AccountDetail
        fields = (
            'posting_date', 'doc_id', 'account_number', 'offset_account', 
            'debit_amount', 'credit_amount', 'business_unit', 'branch', 'customer',
            'unit_code', 'unit_name', 'unreasonable_cost'
        )
        import_id_fields = []
        skip_unchanged = False

    def before_import(self, dataset, **kwargs):
        # 1. Xử lý header rác
        header_index = -1
        for i, row in enumerate(dataset):
            if 'Ngày hạch toán' in [str(c).strip() for c in row if c]:
                header_index = i
                break
        
        if header_index >= 0:
            dataset.headers = [str(h).strip() for h in dataset[header_index]]
            for _ in range(header_index + 1):
                del dataset[0]

        # 2. Xóa dòng Số dư đầu kỳ và các dòng Tổng cộng/Cộng dồn
        idx = len(dataset) - 1
        while idx >= 0:
            row_str = " ".join([str(c) for c in dataset[idx] if c])
            if "Số dư đầu kỳ" in row_str or "Cộng" in row_str or not dataset[idx][2]:
                del dataset[idx]
            idx -= 1

    def before_import_row(self, row, **kwargs):
        # Tự động tạo danh mục BusinessUnit và Branch nếu chưa có
        bu_code = str(row.get('Mã thống kê') or '').strip()
        branch_name = str(row.get('Chi nhánh') or '').strip()

        cust_code = str(row.get('Mã đối tượng') or '').strip()
        cust_name = str(row.get('Tên đối tượng') or '').strip()

        if cust_code and cust_code not in ['', 'None']:
            Customer.objects.get_or_create(
                code=cust_code,
                defaults={'name': cust_name if cust_name else 'N/A'}
            )

        row['Tài khoản'] = row.get('Tài khoản')
        row['TK đối ứng'] = row.get('TK đối ứng')
        
        if bu_code and bu_code != 'None' and bu_code != '':
            BusinessUnit.objects.get_or_create(
                code=bu_code, 
                defaults={'name': str(row.get('Tên thống kê') or 'N/A')}
            )
            
        if branch_name and branch_name != 'None' and branch_name != '':
            Branch.objects.get_or_create(name=branch_name)


class ReceivablesAgeingResource(resources.ModelResource):
    customer = fields.Field(attribute='customer', column_name='Mã khách hàng', widget=ForeignKeyWidget(Customer, 'code'))
    branch = fields.Field(attribute='branch', column_name='Chi nhánh', widget=ForeignKeyWidget(Branch, 'name'))
    doc_date = fields.Field(attribute='doc_date', column_name='Ngày chứng từ', widget=DateWidget(format='%Y-%m-%d'))
    
    # Mapping các trường số liệu (các cột khác sẽ bị bỏ qua vì không khai báo)
    total_debt = fields.Field(attribute='total_debt', column_name='Tổng nợ', widget=DecimalWidget())
    due_total = fields.Field(attribute='due_total', column_name='Nợ trước hạn_Tổng', widget=DecimalWidget())
    overdue_total = fields.Field(attribute='overdue_total', column_name='Nợ quá hạn_Tổng', widget=DecimalWidget())
    # Lưu ý: Các trường chi tiết ngày (0-7, 15-30...) cần được mapping tương tự nếu muốn lấy đủ

    class Meta:
        model = ReceivablesAgeing
        import_id_fields = []
        skip_unchanged = False

    def before_import(self, dataset, **kwargs):
        # 1. Ghép tiêu đề đa tầng (Giống logic cũ để máy hiểu cột Nợ quá hạn_Tổng là cột nào)
        header_idx = -1
        for i, row in enumerate(dataset):
            if 'Mã khách hàng' in [str(c).strip() for c in row if c]:
                header_idx = i
                break
        
        if header_idx >= 0:
            h_main = dataset[header_idx]
            h_sub = dataset[header_idx + 1]
            final_headers = []
            prefix = ""
            for m, s in zip(h_main, h_sub):
                m_s, s_s = str(m or "").strip(), str(s or "").strip()
                if "Nợ trước hạn" in m_s: prefix = "Nợ trước hạn_"
                elif "Nợ quá hạn" in m_s: prefix = "Nợ quá hạn_"
                elif m_s != "": prefix = ""
                
                final_headers.append(f"{prefix}{s_s}" if prefix and s_s else (m_s if m_s else s_s))
            
            dataset.headers = final_headers
            for _ in range(header_idx + 2): del dataset[0]

        # 2. Xóa dòng tổng cộng ở cuối
        idx = len(dataset) - 1
        while idx >= 0:
            val = str(dataset[idx][0]).strip()
            if "Tổng" in val or not val or val == "None": del dataset[idx]
            else: break
            idx -= 1

    def before_import_row(self, row, **kwargs):
        # Tự động tạo danh mục Customer/Branch
        cust_code = str(row.get('Mã khách hàng') or '').strip()
        br_name = str(row.get('Chi nhánh') or '').strip()
        if cust_code and cust_code != 'None':
            Customer.objects.get_or_create(code=cust_code, defaults={'name': row.get('Tên khách hàng') or 'N/A'})
        if br_name and br_name != 'None':
            Branch.objects.get_or_create(name=br_name)

class InventorySummaryResource(resources.ModelResource):
    warehouse = fields.Field(
        attribute='warehouse',
        column_name='Mã kho',
        widget=ForeignKeyWidget(Warehouse, 'code')
    )
    product = fields.Field(
        attribute='product',
        column_name='Mã hàng',
        widget=ForeignKeyWidget(Product, 'code')
    )
    
    # Mapping các cột số liệu (Sau khi đã xử lý tiêu đề tầng 2)
    opening_quantity = fields.Field(attribute='opening_quantity', column_name='Đầu kỳ_Số lượng', widget=DecimalWidget())
    opening_value = fields.Field(attribute='opening_value', column_name='Đầu kỳ_Giá trị', widget=DecimalWidget())
    in_quantity = fields.Field(attribute='in_quantity', column_name='Nhập kho_SL mua hàng', widget=DecimalWidget())
    in_value = fields.Field(attribute='in_value', column_name='Nhập kho_Giá trị mua hàng', widget=DecimalWidget())
    closing_quantity = fields.Field(attribute='closing_quantity', column_name='Cuối kỳ_Số lượng', widget=DecimalWidget())
    closing_value = fields.Field(attribute='closing_value', column_name='Cuối kỳ_Giá trị', widget=DecimalWidget())

    class Meta:
        model = InventorySummary
        import_id_fields = []
        skip_unchanged = False

    def before_import(self, dataset, **kwargs):
        # 1. Tìm Header chuẩn
        header_idx = -1
        for i, row in enumerate(dataset):
            if 'Mã hàng' in [str(c).strip() for c in row if c]:
                header_idx = i
                break
        
        if header_idx >= 0:
            main_h = dataset[header_idx]
            sub_h = dataset[header_idx + 1]
            new_headers = []
            current_main = ""
            
            for m, s in zip(main_h, sub_h):
                m_s = str(m or "").strip()
                s_s = str(s or "").strip()
                
                # Xác định nhóm cột số liệu cần ghép tiêu đề
                if m_s in ["Đầu kỳ", "Nhập kho", "Xuất kho", "Cuối kỳ"]:
                    current_main = m_s
                
                # Nếu có tiêu đề phụ (Số lượng/Giá trị) thì mới ghép
                if s_s in ["Số lượng", "Giá trị", "SL mua hàng", "Giá trị mua hàng", "SL bán hàng", "Giá trị bán hàng"]:
                    new_headers.append(f"{current_main}_{s_s}")
                else:
                    # Nếu không có tiêu đề phụ, hoặc là các cột danh mục phía sau
                    # thì lấy tiêu đề chính (m_s) hoặc tiêu đề phụ (s_s) nếu m_s trống
                    val = m_s if m_s else s_s
                    new_headers.append(val)
                    # Nếu đã sang cột danh mục (như Nhóm VTHH) thì reset current_main
                    if m_s not in ["", "Đầu kỳ", "Nhập kho", "Xuất kho", "Cuối kỳ"]:
                        current_main = ""
            
            dataset.headers = new_headers
            # Xóa các dòng rác phía trên và 2 dòng tiêu đề
            for _ in range(header_idx + 2):
                del dataset[0]

        # 2. Xóa dòng tổng cộng ở cuối
        idx = len(dataset) - 1
        while idx >= 0:
            # Kiểm tra nếu dòng trống hoặc chứa chữ "Cộng"
            row_content = "".join([str(c) for c in dataset[idx] if c])
            if "Tổng" in row_content or not row_content or "Cộng" in row_content:
                del dataset[idx]
            else:
                break
            idx -= 1

    def before_import_row(self, row, **kwargs):
        """
        Tự động xử lý danh mục Warehouse, MaterialGroup và Product trước khi lưu Inventory
        """
        # Kiểm tra mã hàng, nếu trống thì bỏ qua dòng đó
        prod_code = str(row.get('Mã hàng') or '').strip()
        if not prod_code or prod_code == 'None':
            return None

        # 1. Xử lý Warehouse (Kho)
        wh_code = str(row.get('Mã kho') or '').strip()
        if wh_code:
            Warehouse.objects.get_or_create(
                code=wh_code[:255], 
                defaults={'name': str(row.get('Tên kho') or 'N/A')[:500]}
            )

        # 2. Xử lý MaterialGroup (Nhóm VTHH) theo logic tách chuỗi /
        group_raw = str(row.get('Nhóm VTHH') or 'Khác').strip()
        parts = group_raw.split('/')
        
        # Code = phần cuối, Name = toàn bộ chuỗi
        g_code = parts[-1].strip()[:255]
        g_name = group_raw[:500]

        group_obj, _ = MaterialGroup.objects.get_or_create(
            code=g_code, 
            defaults={'name': g_name}
        )

        # 3. Xử lý Product (Vật tư hàng hóa)
        # Sử dụng update_or_create để cập nhật thông tin mới nhất (như ĐVT, Nhóm)
        Product.objects.update_or_create(
            code=prod_code[:500],
            defaults={
                'name': str(row.get('Tên hàng') or 'N/A')[:255],
                'unit': str(row.get('ĐVT') or 'Cái')[:20],
                'group': group_obj,
                'brand': str(row.get('Nguồn gốc') or '')[:100]
            }
        )


class PurchaseDetailResource(resources.ModelResource):
    # Định nghĩa các trường liên kết
    supplier = fields.Field(
        attribute='supplier',
        column_name='Mã nhà cung cấp',
        widget=ForeignKeyWidget(Supplier, 'code')
    )
    business_unit = fields.Field(
        attribute='business_unit',
        column_name='Mã thống kê',
        widget=ForeignKeyWidget(BusinessUnit, 'code')
    )
    warehouse = fields.Field(
        attribute='warehouse',
        column_name='Mã kho',
        widget=ForeignKeyWidget(Warehouse, 'code')
    )
    product = fields.Field(
        attribute='product',
        column_name='Mã hàng', # Tên cột trong file Excel
        widget=ForeignKeyWidget(Product, 'code')
    )
    
    posting_date = fields.Field(attribute='posting_date', column_name='Ngày hạch toán', widget=DateWidget(format='%Y-%m-%d'))
    doc_date = fields.Field(attribute='doc_date', column_name='Ngày chứng từ', widget=DateWidget(format='%Y-%m-%d'))

    class Meta:
        model = PurchaseDetail
        import_id_fields = []
        skip_unchanged = False
        fields = (
            'posting_date', 'doc_date', 'doc_number', 'description',
            'supplier', 'warehouse', 'product', 'business_unit',
            'org_unit_code', 'org_unit_name', 'quantity', 'unit_price',
            'purchase_value', 'vat_value', 'total_value',
            'debit_account', 'credit_account'
        )

    def before_import(self, dataset, **kwargs):
        # 1. Xử lý Header
        header_idx = -1
        for i, row in enumerate(dataset):
            if 'Ngày hạch toán' in [str(c).strip() for c in row if c]:
                header_idx = i
                break
        
        if header_idx >= 0:
            dataset.headers = [str(h).strip() for h in dataset[header_idx]]
            for _ in range(header_idx + 1):
                del dataset[0]
        
        # 2. Xử lý dòng cuối
        idx = len(dataset) - 1
        while idx >= 0:
            row_content = "".join([str(c) for c in dataset[idx] if c and str(c).strip()])
            if any(x in row_content for x in ["Tổng", "Cộng", "Số dòng"]) or not row_content:
                del dataset[idx]
            else:
                break
            idx -= 1

    def before_import_row(self, row, **kwargs):
        # --- 0. Kiểm tra mã hàng ---
        prod_code = str(row.get('Mã hàng') or '').strip()
        if not prod_code or prod_code == 'None':
            return None

        # --- 1. Xử lý MaterialGroup ---
        group_raw = str(row.get('Tên nhóm VTHH') or 'Khác').strip()
        g_code = group_raw.split('/')[-1].strip()
        group_obj, _ = MaterialGroup.objects.get_or_create(
            code=g_code, defaults={'name': group_raw}
        )

        # --- 2. Xử lý Product (Dùng get_or_create để giữ nguyên nếu đã có) ---
        # Chúng ta tạo Product ngay tại đây
        product_obj, _ = Product.objects.get_or_create(
            code=prod_code,
            defaults={
                'name': str(row.get('Tên hàng') or 'N/A'),
                'unit': str(row.get('ĐVT') or 'Cái'),
                'group': group_obj,
                'brand': str(row.get('Nguồn gốc') or '')
            }
        )
        # QUAN TRỌNG: Gán lại vào cột 'Mã hàng' để ForeignKeyWidget tìm thấy
        row['Mã hàng'] = product_obj.code

        # --- 3. Xử lý Business Unit ---
        bu_code = str(row.get('Mã thống kê') or '').strip()
        if bu_code:
            bu_obj, _ = BusinessUnit.objects.get_or_create(
                code=bu_code,
                defaults={'name': str(row.get('Tên thống kê') or bu_code)}
            )
            row['Mã thống kê'] = bu_obj.code

        # --- 4. Xử lý Supplier & SupplierGroup ---
        sup_code = str(row.get('Mã nhà cung cấp') or '').strip()
        if sup_code:
            # Lấy mã và tên nhóm từ Excel
            s_group_code = str(row.get('Mã nhóm nhà cung cấp') or '').strip()
            s_group_name = str(row.get('Tên nhóm nhà cung cấp') or '').strip()
            
            if s_group_code:
                # SO SÁNH THEO CODE (Chuẩn nghiệp vụ)
                s_group_obj, _ = SupplierGroup.objects.get_or_create(
                    code=s_group_code,
                    defaults={'name': s_group_name or s_group_code}
                )
            else:
                # Trường hợp file Excel trống mã nhóm
                s_group_obj, _ = SupplierGroup.objects.get_or_create(
                    code="OTHER",
                    defaults={'name': "Chưa phân loại"}
                )
            
            # Sau đó mới tạo Supplier gắn với Group đó
            sup_obj, _ = Supplier.objects.get_or_create(
                code=sup_code,
                defaults={
                    'name': str(row.get('Tên nhà cung cấp') or 'N/A'),
                    'group': s_group_obj
                }
            )
            # Gán lại vào row để ForeignKeyWidget dùng code tìm Supplier
            row['Mã nhà cung cấp'] = sup_obj.code

        # --- 5. Xử lý Warehouse ---
        wh_code = str(row.get('Mã kho') or '').strip()
        if wh_code:
            wh_obj, _ = Warehouse.objects.get_or_create(
                code=wh_code,
                defaults={'name': str(row.get('Tên kho') or 'N/A')}
            )
            row['Mã kho'] = wh_obj.code

        # --- 6. Các trường lưu text trực tiếp ---
        row['org_unit_code'] = str(row.get('Mã đơn vị') or '').strip()
        row['org_unit_name'] = str(row.get('Tên đơn vị') or '').strip()

        # --- 7. Map lại các trường để Model nhận diện đúng ---
        row['doc_number'] = str(row.get('Số chứng từ') or '').strip()
        row['description'] = str(row.get('Diễn giải') or row.get('Diễn giải chung') or '').strip()
        row['quantity'] = row.get('Số lượng mua') or 0
        row['unit_price'] = row.get('Đơn giá') or 0
        row['purchase_value'] = row.get('Giá trị mua') or 0
        row['vat_value'] = row.get('Thuế GTGT') or 0
        row['total_value'] = row.get('Giá trị nhập kho/Tổng giá trị') or 0
        row['debit_account'] = str(row.get('TK Nợ') or '').strip()
        row['credit_account'] = str(row.get('TK Có') or '').strip()

        return row