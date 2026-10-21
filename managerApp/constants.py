
class Status:
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class Endpoints:
    HOME = "home"
    DASHBOARD = "managerApp:dashboard"
    USERS = "managerApp:total_users"
    USERS_REDIRECT = "/manager/users"
    LOGIN = "/manager/admin-login"


class Templates:
    LOGIN = "admin/adminLogin.html"
    DASHBOARD = "admin/dashboard.html"
    CATEGORY = "admin/admin_add_category.html"
    USERS = "admin/customer.html"
    REQUESTS = "admin/request_user.html"
    APPROVED = "admin/approved_loan.html"
    REJECTED = "admin/rejected_loan.html"
    TRANSACTIONS = "admin/transaction.html"


class Loan:
    ANNUAL_INTEREST_RATE = 0.12
