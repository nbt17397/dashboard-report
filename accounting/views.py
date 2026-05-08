from accounting.tasks import update_single_bu_performance
from rest_framework import viewsets, generics
import pandas as pd
from .models import (
    Branch, Warehouse, Customer, Employee,
    Product, BusinessUnit, SalesTransaction, Supplier, SupplierDebt, SupplierGroup
)
from .serializers import *
from knox.views import LoginView as KnoxLoginView
from rest_framework import permissions, status
from django.contrib.auth import authenticate, login
from rest_framework.response import Response
from rest_framework.views import APIView

class LoginAPI(KnoxLoginView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, format=None):
        username = request.data.get('username')
        password = request.data.get('password')

        user = authenticate(username=username, password=password)
        if not user:
            return Response({'error': 'Sai tài khoản hoặc mật khẩu'}, status=400)

        login(request, user)
        return super().post(request, format=None)

class BranchViewSet(viewsets.ModelViewSet):
    queryset = Branch.objects.all()
    serializer_class = BranchSerializer

class WarehouseViewSet(viewsets.ModelViewSet):
    queryset = Warehouse.objects.all()
    serializer_class = WarehouseSerializer

class CustomerViewSet(viewsets.ModelViewSet):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer

class EmployeeViewSet(viewsets.ModelViewSet):
    queryset = Employee.objects.all()
    serializer_class = EmployeeSerializer

class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer

class BusinessUnitViewSet(viewsets.ModelViewSet):
    queryset = BusinessUnit.objects.all()
    serializer_class = BusinessUnitSerializer

    def get_queryset(self):
        queryset = BusinessUnit.objects.all()
        is_main = self.request.query_params.get("is_main")

        if is_main in ["true", "false"]:
            queryset = queryset.filter(is_main=(is_main == "true"))

        return queryset

class SalesTransactionViewSet(viewsets.ModelViewSet):
    queryset = SalesTransaction.objects.all()
    serializer_class = SalesTransactionSerializer

class SupplierViewSet(viewsets.ModelViewSet):
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer

class SupplierGroupViewSet(viewsets.ModelViewSet):
    queryset = SupplierGroup.objects.all()
    serializer_class = SupplierGroupSerializer

class SupplierDebtViewSet(viewsets.ModelViewSet):
    queryset = SupplierDebt.objects.all()
    serializer_class = SupplierDebtSerializer

class AccountDetailViewSet(viewsets.ModelViewSet):
    queryset = AccountDetail.objects.all().order_by('-id')
    serializer_class = AccountDetailSerializer
    # Thêm bộ lọc nếu cần (ví dụ lọc theo Business Unit)
    filterset_fields = ['business_unit__code']

class ReceivablesAgeingViewSet(viewsets.ModelViewSet):
    queryset = ReceivablesAgeing.objects.all().order_by('-id')
    serializer_class = ReceivablesAgeingSerializer
    search_fields = ['customer__code', 'customer__name']

class PurchaseDetailViewSet(viewsets.ModelViewSet):
    queryset = PurchaseDetail.objects.all().select_related(
        'supplier', 'business_unit', 'product', 'warehouse'
    ).order_by('-posting_date')
    serializer_class = PurchaseDetailSerializer
    filterset_fields = ['supplier__code', 'business_unit__code', 'warehouse__code']


class BUReportAPIView(APIView):
    def get(self, request):
        # 1. Lấy tham số lọc từ query params
        month = request.query_params.get('month')
        year = request.query_params.get('year')
        bu_id = request.query_params.get('bu_id')
        only_roots = request.query_params.get('only_roots')

        # 2. Khởi tạo filter động
        filters = {}
        
        # Chỉ thêm vào filter nếu người dùng có truyền tham số
        if month and month.isdigit():
            filters['month'] = int(month)
        if year and year.isdigit():
            filters['year'] = int(year)
        
        # 3. Xử lý logic Business Unit (Quan trọng)
        # Nếu bu_id là 'all' hoặc không truyền gì cả -> Lấy tất cả (không lọc BU)
        # Nếu bu_id là 'null' -> Lấy bản ghi Tổng công ty
        # Nếu bu_id là số -> Lấy theo ID của BU đó
        
        if bu_id == 'null' or bu_id == '':
            filters['business_unit__isnull'] = True
        elif bu_id and bu_id != 'all':
            filters['business_unit_id'] = bu_id
        # Nếu bu_id='all' hoặc không có bu_id trong params thì không thêm vào filters -> lấy hết

        if only_roots == 'true':
            # Chỉ lấy những bản ghi Performance mà BU của nó không có parent
            filters['business_unit__parent__isnull'] = True

        # 4. Sử dụng .filter() thay vì .get() để tránh lỗi khi có nhiều bản ghi
        queryset = BUPerformance.objects.filter(**filters).order_by('-year', '-month')

        if queryset.exists():
            # many=True cho phép serializer xử lý một danh sách bản ghi
            serializer = BUPerformanceSerializer(queryset, many=True)
            return Response(serializer.data)
        else:
            return Response(
                {"message": "Không tìm thấy dữ liệu phù hợp với bộ lọc."}, 
                status=status.HTTP_404_NOT_FOUND
            )
        

class BUPerformanceDailyListView(generics.ListAPIView):
    serializer_class = BUPerformanceDailySerializer

    def get_queryset(self):
        """
        Cho phép lọc dữ liệu qua URL params:
        ?bu_id=1&month=1&year=2026
        """
        queryset = BUPerformanceDaily.objects.all().select_related(
            'performance_month__business_unit'
        )
        
        bu_id = self.request.query_params.get('bu_id')
        month = self.request.query_params.get('month')
        year = self.request.query_params.get('year')

        # Lọc theo BU (Nếu không truyền bu_id hoặc bu_id=0/null thì lấy Tổng công ty)
        if bu_id:
            queryset = queryset.filter(performance_month__business_unit_id=bu_id)
        else:
            queryset = queryset.filter(performance_month__business_unit__isnull=True)

        # Lọc theo tháng/năm
        if month:
            queryset = queryset.filter(date__month=month)
        if year:
            queryset = queryset.filter(date__year=year)

        return queryset.order_by('date')
    

class BUPerformanceUpdateAPIView(APIView):
    """
    API để trigger cập nhật dữ liệu hiệu suất BU
    """
    def post(self, request):
        serializer = PerformanceUpdateSerializer(data=request.data)
        
        if serializer.is_valid():
            bu_id = serializer.validated_data.get('bu_id')
            month = serializer.validated_data.get('month')
            year = serializer.validated_data.get('year')
            target_date = serializer.validated_data.get('target_date')

            # Chuyển target_date thành string để gửi vào task nếu có
            target_date_str = target_date.strftime('%Y-%m-%d') if target_date else None

            try:
                # GỌI TASK: 
                # Cách 1: Chạy ngay lập tức (Sync) để lấy kết quả trả về API
                result = update_single_bu_performance(
                    bu_id=bu_id, 
                    month=month, 
                    year=year, 
                    target_date_str=target_date_str
                )
                
                # Cách 2: Nếu muốn chạy ngầm (Async) qua Celery
                # update_single_bu_performance.delay(bu_id, month, year, target_date_str)
                # result = "Task has been queued"

                return Response({
                    "status": "success",
                    "message": result
                }, status=status.HTTP_200_OK)

            except Exception as e:
                return Response({
                    "status": "error",
                    "message": str(e)
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)