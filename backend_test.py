import requests
import sys
import json
from datetime import datetime

class BusinessManagementAPITester:
    def __init__(self, base_url="https://order-hub-316.preview.emergentagent.com"):
        self.base_url = base_url
        self.session = requests.Session()
        self.tests_run = 0
        self.tests_passed = 0
        self.test_data = {}

    def run_test(self, name, method, endpoint, expected_status, data=None, params=None):
        """Run a single API test"""
        url = f"{self.base_url}/{endpoint}"
        headers = {'Content-Type': 'application/json'}

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        
        try:
            if method == 'GET':
                response = self.session.get(url, headers=headers, params=params)
            elif method == 'POST':
                response = self.session.post(url, json=data, headers=headers)
            elif method == 'PUT':
                response = self.session.put(url, json=data, headers=headers)
            elif method == 'DELETE':
                response = self.session.delete(url, headers=headers)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    return success, response.json()
                except:
                    return success, {}
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                try:
                    print(f"Response: {response.text}")
                except:
                    pass
                return False, {}

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {}

    def test_health(self):
        """Test health endpoint"""
        return self.run_test("Health Check", "GET", "api/health", 200)

    def test_login(self):
        """Test login with admin credentials"""
        success, response = self.run_test(
            "Admin Login",
            "POST",
            "api/auth/login",
            200,
            data={"email": "admin@example.com", "password": "admin123"}
        )
        if success:
            print(f"✅ Login successful - User: {response.get('name', 'Unknown')}, Role: {response.get('role', 'Unknown')}")
        return success

    def test_auth_me(self):
        """Test getting current user info"""
        return self.run_test("Get Current User", "GET", "api/auth/me", 200)

    def test_dashboard(self):
        """Test dashboard summary"""
        success, response = self.run_test("Dashboard Summary", "GET", "api/dashboard/summary", 200)
        if success:
            print(f"✅ Dashboard data: Receivables: {response.get('receivables', 0)}, Payables: {response.get('payables', 0)}")
        return success

    def test_customers_crud(self):
        """Test customer CRUD operations"""
        # Create customer
        customer_data = {
            "name": "Test Customer",
            "phone": "1234567890",
            "shop_name": "Test Shop",
            "address": "Test Address",
            "credit_limit": 10000
        }
        success, customer = self.run_test("Create Customer", "POST", "api/customers", 200, customer_data)
        if not success:
            return False
        
        customer_id = customer.get("id")
        self.test_data["customer_id"] = customer_id
        print(f"✅ Created customer with ID: {customer_id}")

        # List customers
        success, customers = self.run_test("List Customers", "GET", "api/customers", 200)
        if not success:
            return False

        # Get specific customer
        success, customer_detail = self.run_test("Get Customer", "GET", f"api/customers/{customer_id}", 200)
        if not success:
            return False

        # Update customer
        update_data = {"name": "Updated Test Customer"}
        success, updated_customer = self.run_test("Update Customer", "PUT", f"api/customers/{customer_id}", 200, update_data)
        if not success:
            return False

        return True

    def test_suppliers_crud(self):
        """Test supplier CRUD operations"""
        # Create supplier
        supplier_data = {
            "name": "Test Supplier",
            "phone": "0987654321",
            "address": "Supplier Address",
            "is_primary": True
        }
        success, supplier = self.run_test("Create Supplier", "POST", "api/suppliers", 200, supplier_data)
        if not success:
            return False
        
        supplier_id = supplier.get("id")
        self.test_data["supplier_id"] = supplier_id
        print(f"✅ Created supplier with ID: {supplier_id}")

        # List suppliers
        success, suppliers = self.run_test("List Suppliers", "GET", "api/suppliers", 200)
        if not success:
            return False

        # Get specific supplier
        success, supplier_detail = self.run_test("Get Supplier", "GET", f"api/suppliers/{supplier_id}", 200)
        if not success:
            return False

        return True

    def test_products_crud(self):
        """Test product CRUD operations"""
        # Create product
        product_data = {
            "name": "Test Product",
            "unit": "pcs",
            "selling_price": 100.0,
            "cost_price": 80.0
        }
        success, product = self.run_test("Create Product", "POST", "api/products", 200, product_data)
        if not success:
            return False
        
        product_id = product.get("id")
        self.test_data["product_id"] = product_id
        print(f"✅ Created product with ID: {product_id}")

        # List products
        success, products = self.run_test("List Products", "GET", "api/products", 200)
        if not success:
            return False

        # Get specific product
        success, product_detail = self.run_test("Get Product", "GET", f"api/products/{product_id}", 200)
        if not success:
            return False

        return True

    def test_orders_crud(self):
        """Test order CRUD operations"""
        if not all(k in self.test_data for k in ["customer_id", "product_id", "supplier_id"]):
            print("❌ Missing test data for order creation")
            return False

        # Create order
        order_data = {
            "customer_id": self.test_data["customer_id"],
            "customer_name": "Test Customer",
            "items": [{
                "product_id": self.test_data["product_id"],
                "product_name": "Test Product",
                "quantity": 5,
                "unit_price": 100.0,
                "supplier_id": self.test_data["supplier_id"],
                "supplier_name": "Test Supplier"
            }],
            "notes": "Test order"
        }
        success, order = self.run_test("Create Order", "POST", "api/orders", 200, order_data)
        if not success:
            return False
        
        order_id = order.get("id")
        self.test_data["order_id"] = order_id
        print(f"✅ Created order with ID: {order_id}")

        # List orders
        success, orders = self.run_test("List Orders", "GET", "api/orders", 200)
        if not success:
            return False

        # Get specific order
        success, order_detail = self.run_test("Get Order", "GET", f"api/orders/{order_id}", 200)
        if not success:
            return False

        # Update order status
        status_data = {"status": "ordered"}
        success, updated_order = self.run_test("Update Order Status", "PUT", f"api/orders/{order_id}/status", 200, status_data)
        if not success:
            return False

        return True

    def test_invoices_crud(self):
        """Test invoice operations"""
        if "order_id" not in self.test_data:
            print("❌ Missing order data for invoice creation")
            return False

        # Create invoice from order
        invoice_data = {
            "order_id": self.test_data["order_id"],
            "customer_id": self.test_data["customer_id"],
            "customer_name": "Test Customer",
            "items": [{
                "product_id": self.test_data["product_id"],
                "product_name": "Test Product",
                "quantity": 5,
                "unit_price": 100.0,
                "amount": 500.0
            }],
            "total_amount": 500.0,
            "notes": "Test invoice"
        }
        success, invoice = self.run_test("Create Invoice", "POST", "api/invoices", 200, invoice_data)
        if not success:
            return False
        
        invoice_id = invoice.get("id")
        self.test_data["invoice_id"] = invoice_id
        print(f"✅ Created invoice with ID: {invoice_id}")

        # List invoices
        success, invoices = self.run_test("List Invoices", "GET", "api/invoices", 200)
        if not success:
            return False

        # Get specific invoice
        success, invoice_detail = self.run_test("Get Invoice", "GET", f"api/invoices/{invoice_id}", 200)
        if not success:
            return False

        return True

    def test_purchases_crud(self):
        """Test purchase operations"""
        if not all(k in self.test_data for k in ["supplier_id", "order_id"]):
            print("❌ Missing test data for purchase creation")
            return False

        # Create purchase
        purchase_data = {
            "supplier_id": self.test_data["supplier_id"],
            "supplier_name": "Test Supplier",
            "order_id": self.test_data["order_id"],
            "items": [{
                "product_id": self.test_data["product_id"],
                "product_name": "Test Product",
                "quantity": 5,
                "cost_price": 80.0
            }],
            "notes": "Test purchase"
        }
        success, purchase = self.run_test("Create Purchase", "POST", "api/purchases", 200, purchase_data)
        if not success:
            return False
        
        purchase_id = purchase.get("id")
        self.test_data["purchase_id"] = purchase_id
        print(f"✅ Created purchase with ID: {purchase_id}")

        # List purchases
        success, purchases = self.run_test("List Purchases", "GET", "api/purchases", 200)
        if not success:
            return False

        return True

    def test_payments_crud(self):
        """Test payment operations"""
        if not all(k in self.test_data for k in ["customer_id", "supplier_id", "invoice_id"]):
            print("❌ Missing test data for payment creation")
            return False

        # Create customer payment
        customer_payment_data = {
            "payment_type": "customer",
            "entity_id": self.test_data["customer_id"],
            "entity_name": "Test Customer",
            "amount": 250.0,
            "payment_method": "cash",
            "reference": "Test payment",
            "invoice_id": self.test_data["invoice_id"]
        }
        success, payment = self.run_test("Create Customer Payment", "POST", "api/payments", 200, customer_payment_data)
        if not success:
            return False
        
        payment_id = payment.get("id")
        print(f"✅ Created customer payment with ID: {payment_id}")

        # Create supplier payment
        supplier_payment_data = {
            "payment_type": "supplier",
            "entity_id": self.test_data["supplier_id"],
            "entity_name": "Test Supplier",
            "amount": 200.0,
            "payment_method": "bank_transfer",
            "reference": "Test supplier payment"
        }
        success, supplier_payment = self.run_test("Create Supplier Payment", "POST", "api/payments", 200, supplier_payment_data)
        if not success:
            return False

        # List payments
        success, payments = self.run_test("List Payments", "GET", "api/payments", 200)
        if not success:
            return False

        return True

    def test_forgot_password_flow(self):
        """Test forgot password and reset flow"""
        # Test forgot password
        success, response = self.run_test(
            "Forgot Password",
            "POST",
            "api/auth/forgot-password",
            200,
            data={"email": "admin@example.com"}
        )
        if not success:
            return False
        
        otp = response.get("otp")
        if not otp:
            print("❌ No OTP returned in forgot password response")
            return False
        
        print(f"✅ OTP generated: {otp}")
        
        # Test reset password
        success, reset_response = self.run_test(
            "Reset Password",
            "POST",
            "api/auth/reset-password",
            200,
            data={"email": "admin@example.com", "otp": otp, "new_password": "admin123"}
        )
        
        return success

    def test_logout(self):
        """Test logout"""
        return self.run_test("Logout", "POST", "api/auth/logout", 200)
        """Clean up created test data"""
        print("\n🧹 Cleaning up test data...")
        
        # Delete in reverse order of creation
        if "customer_id" in self.test_data:
            self.run_test("Delete Customer", "DELETE", f"api/customers/{self.test_data['customer_id']}", 200)
        
        if "supplier_id" in self.test_data:
            self.run_test("Delete Supplier", "DELETE", f"api/suppliers/{self.test_data['supplier_id']}", 200)
    def cleanup_test_data(self):
            self.run_test("Delete Product", "DELETE", f"api/products/{self.test_data['product_id']}", 200)

def main():
    print("🚀 Starting Business Management System API Tests")
    tester = BusinessManagementAPITester()

    try:
        # Test sequence
        tests = [
            ("Health Check", tester.test_health),
            ("Login", tester.test_login),
            ("Auth Me", tester.test_auth_me),
            ("Dashboard", tester.test_dashboard),
            ("Customer CRUD", tester.test_customers_crud),
            ("Supplier CRUD", tester.test_suppliers_crud),
            ("Product CRUD", tester.test_products_crud),
            ("Order CRUD", tester.test_orders_crud),
            ("Invoice CRUD", tester.test_invoices_crud),
            ("Purchase CRUD", tester.test_purchases_crud),
            ("Forgot Password Flow", tester.test_forgot_password_flow),
            ("Logout", tester.test_logout)
        ]

        for test_name, test_func in tests:
            print(f"\n{'='*50}")
            print(f"Running {test_name} Tests")
            print(f"{'='*50}")
            
            if not test_func():
                print(f"❌ {test_name} tests failed, stopping execution")
                break
        
        # Cleanup
        tester.cleanup_test_data()

        # Print results
        print(f"\n{'='*50}")
        print(f"📊 Test Results")
        print(f"{'='*50}")
        print(f"Tests passed: {tester.tests_passed}/{tester.tests_run}")
        success_rate = (tester.tests_passed / tester.tests_run * 100) if tester.tests_run > 0 else 0
        print(f"Success rate: {success_rate:.1f}%")
        
        return 0 if tester.tests_passed == tester.tests_run else 1

    except Exception as e:
        print(f"❌ Test execution failed: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())