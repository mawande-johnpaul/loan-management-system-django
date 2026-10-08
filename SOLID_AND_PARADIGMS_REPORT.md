# SOLID Review: Loan Management System

**Files we refactored:** `managerApp/views.py`, `loanApp/views.py`, `loginApp/views.py`

We kept the public view names, URL routes, templates, and test files unchanged. The refactor keeps Django views focused on HTTP work and moves repeated calculations and business operations into focused helpers and service classes inside the existing `views.py` files.

## Shared groundwork

### Safe aggregate helper

```python
def _sum_or_zero(queryset, field):
    return queryset.aggregate(total=Sum(field))['total'] or 0
```

### Customer dashboard service

```python
class CustomerDashboardService:
    @staticmethod
    def for_customer(customer):
        requests = loanRequest.objects.filter(customer=customer)
        loans = CustomerLoan.objects.filter(customer=customer)
        payments = loanTransaction.objects.filter(customer=customer)
        return {
            'request': requests.count(),
            'approved': requests.filter(status='approved').count(),
            'rejected': requests.filter(status='rejected').count(),
            'totalLoan': _sum_or_zero(loans, 'total_loan'),
            'totalPayable': _sum_or_zero(loans, 'payable_loan'),
            'totalPaid': _sum_or_zero(payments, 'payment'),
        }
```

### Manager loan service

```python
class ManagerLoanService:
    @staticmethod
    @transaction.atomic
    def approve(request_id):
        loan_obj = get_object_or_404(loanRequest, id=request_id)
        if loan_obj.status == 'approved':
            return
        # Update or create the customer's balance, then approve once.

    @staticmethod
    def reject(request_id):
        loan_obj = get_object_or_404(loanRequest, id=request_id)
        if loan_obj.status != 'approved':
            loan_obj.status = 'rejected'
            loan_obj.save(update_fields=['status', 'status_date'])
```

---

# 1. Single Responsibility Principle (SRP)

> A unit of code should have one reason to change.

## 1.1 `approved_request` in `managerApp/views.py`

### Before

```python
def approved_request(request, id):
    today = date.today()
    status_date = today.strftime("%B %d, %Y")
    loan_obj = loanRequest.objects.get(id=id)
    loan_obj.status_date = status_date
    loan_obj.save()
    year = loan_obj.year

    approved_customer = loanRequest.objects.get(id=id).customer
    if CustomerLoan.objects.filter(customer=approved_customer).exists():

        # find previous amount of customer
        PreviousAmount = CustomerLoan.objects.get(
            customer=approved_customer).total_loan
        PreviousPayable = CustomerLoan.objects.get(
            customer=approved_customer).payable_loan

        # update balance
        CustomerLoan.objects.filter(
            customer=approved_customer).update(total_loan=int(PreviousAmount)+int(loan_obj.amount))
        CustomerLoan.objects.filter(
            customer=approved_customer).update(payable_loan=int(PreviousPayable)+int(loan_obj.amount)+int(loan_obj.amount)*0.12*int(year))

    else:

        # request customer

        # CustomerLoan object create
        save_loan = CustomerLoan()

        save_loan.customer = approved_customer
        save_loan.total_loan = int(loan_obj.amount)
        save_loan.payable_loan = int(
            loan_obj.amount)+int(loan_obj.amount)*0.12*int(year)
        save_loan.save()

    loanRequest.objects.filter(id=id).update(status='approved')
    loanrequest = loanRequest.objects.filter(status='pending')
    return render(request, 'admin/request_user.html', context={'loanrequest': loanrequest})
```

### After

```python
@staff_member_required(login_url='/manager/admin-login')
@require_POST
def approved_request(request, id):
    ManagerLoanService.approve(id)
    return render(
        request,
        'admin/request_user.html',
        {'loanrequest': loanRequest.objects.filter(status='pending')},
    )
```

### Explanation

The original view fetched records, calculated interest, changed balances, changed status, formatted dates, and rendered the response. We moved the loan decision into `ManagerLoanService.approve`; the view now coordinates the request and response. The service is also atomic and ignores a second approval.

## 1.2 `sign_up_view` in `loginApp/views.py`

### Before

```python
def sign_up_view(request):
    error = ''
    if request.user.is_authenticated:

        return HttpResponseRedirect(reverse('home'))

    form = CustomerSignUpForm()
    if request.method == 'POST':

        form = CustomerSignUpForm(request.POST)
        # print(form.cleaned_data['username'])
        if form.is_valid():
            user = form.save()

            user_profile = CustomerSignUp(user=user)
            user_profile.save()
            username = form.cleaned_data['username']
            password1 = form.cleaned_data['password1']
            print(username,password1)
            user = authenticate(request, username=username, password=password1)
            if user is not None:
                login(request, user)
                return HttpResponseRedirect(reverse('home'))

            return HttpResponseRedirect(reverse('login_App:login_customer'))

        else:
            if User.objects.filter(username=request.POST['username']).exists():
                error = 'customer already exists'

            else:
                error = 'Your password is not strong enough or both password must be same'
        

    return render(request, 'loginApp/signup.html', context={'form': form, 'user': "Customer Register", 'error': error})
```

### After

```python
class CustomerAccountService:
    @staticmethod
    @transaction.atomic
    def create_profile(form):
        user = form.save()
        CustomerSignUp.objects.create(user=user)
        return user
```

```python
if request.method == 'POST' and form.is_valid():
    user = CustomerAccountService.create_profile(form)
    user = authenticate(
        request,
        username=user.username,
        password=form.cleaned_data['password1'],
    )
    if user is not None:
        login(request, user)
        return HttpResponseRedirect(reverse('home'))
```

### Explanation

The original view combined user creation, profile creation, authentication, password output, and response handling. We isolated account persistence in an atomic service and removed the password print. A profile failure now rolls back the user creation instead of leaving an orphaned account.

## 1.3 Dashboard views

### Before

```python
totalLoan = CustomerLoan.objects.aggregate(Sum('total_loan'))[
    'total_loan__sum'],
totalPayable = CustomerLoan.objects.aggregate(Sum('payable_loan'))[
    'payable_loan__sum'],
totalPaid = loanTransaction.objects.aggregate(Sum('payment'))[
    'payment__sum'],
```

### After

```python
def UserDashboard(request):
    context = CustomerDashboardService.for_customer(
        _customer_for(request)
    )
    return render(request, 'loanApp/user_dashboard.html', context=context)
```

### Explanation

The original dashboard repeated queries, used one-item tuples, and returned `None` for empty sums. We centralized customer dashboard calculations and normalize empty totals to zero. The same responsibility split is used by the manager dashboard with `_sum_or_zero`.

## 1.4 User removal

### Before

```python
CustomerSignUp.objects.get(id=pk).delete()
user = User.objects.get(id=pk)
user.delete()
```

### After

```python
@staff_member_required(login_url='/manager/admin-login')
@require_POST
def user_remove(request, pk):
    customer = get_object_or_404(CustomerSignUp, id=pk)
    customer.user.delete()
    customer.delete()
    return HttpResponseRedirect('/manager/users')
```

### Explanation

The original assumed the customer primary key and user primary key were equal. We now follow the actual relationship, return a 404 for an unknown customer, and prevent deletion through GET requests.

---

# 2. Open/Closed Principle (OCP)

> Code should be open for extension but closed for modification.

## 2.1 Loan approval operations

### Before

```python
if CustomerLoan.objects.filter(customer=approved_customer).exists():
    # Update an existing balance.
else:
    # Create a new balance with a second copy of the formula.
```

### After

```python
customer_loan, created = CustomerLoan.objects.get_or_create(
    customer=loan_obj.customer,
    defaults={'total_loan': loan_obj.amount, 'payable_loan': payable},
)
if not created:
    customer_loan.total_loan += int(loan_obj.amount)
    customer_loan.payable_loan += payable
    customer_loan.save(update_fields=['total_loan', 'payable_loan'])
```

### Explanation

The balance update now has one accumulation path rather than separate create and update branches. Extending the balance operation, such as adding a fee or another total, requires changing the service operation rather than duplicating the rule in multiple branches.

## 2.2 Reusable dashboard calculations

### Before

```python
requestLoan = loanRequest.objects.filter(
    customer=request.user.customer).count(),
approved = loanRequest.objects.filter(
    customer=request.user.customer).filter(status='approved').count(),
```

### After

```python
context = CustomerDashboardService.for_customer(customer)
```

### Explanation

New dashboard metrics can be added in one service result instead of being added independently to every dashboard view. Existing template keys are preserved so the current templates continue to work.

---

# 3. Liskov Substitution Principle (LSP)

> Subtypes must be usable wherever their base type is expected.

There are no direct LSP violations in the three files. They use function-based views and do not define an inheritance hierarchy. The service classes are small collaborators rather than parent/child abstractions, so no subtype substitution contract was introduced.

---

# 4. Interface Segregation Principle (ISP)

> Clients should not be forced to depend on methods they do not use.

There are no wide interfaces in the original view modules. We kept the new collaborators narrow:

```python
CustomerDashboardService.for_customer(customer)
CustomerAccountService.create_profile(form)
ManagerLoanService.approve(request_id)
ManagerLoanService.reject(request_id)
```

Each caller uses one focused operation instead of depending on a large service object with unrelated methods.

---

# 5. Dependency Inversion Principle (DIP)

> High-level modules should depend on abstractions, not on low-level details.

## 5.1 Customer lookup

### Before

```python
transactions = loanTransaction.objects.filter(
    customer=request.user.customer
)
```

### After

```python
def _customer_for(request):
    return get_object_or_404(CustomerSignUp, user=request.user)

transactions = loanTransaction.objects.filter(
    customer=_customer_for(request)
)
```

### Explanation

We centralized the relationship between the authenticated user and the customer profile. Customer views now share one lookup behavior and staff users without profiles receive a 404 instead of an unhandled related-object exception.

## 5.2 ORM and business rules

### Before

```python
loan_obj = loanRequest.objects.get(id=id)
CustomerLoan.objects.filter(customer=approved_customer).update(...)
loanRequest.objects.filter(id=id).update(status='approved')
```

### After

```python
ManagerLoanService.approve(id)
ManagerLoanService.reject(id)
```

### Explanation

The views no longer describe every persistence step required to approve or reject a loan. They depend on focused service operations, while the ORM details remain inside the service implementation.

---

# 6. Three Paradigms

- **Structured/imperative:** request methods, validation, early returns, and response rendering follow explicit control flow.
- **Object-oriented:** `CustomerDashboardService`, `CustomerAccountService`, and `ManagerLoanService` group related operations and state rules.
- **Functional style:** `_sum_or_zero` and the dashboard context-building methods isolate reusable calculations from HTTP responses.

---

# 7. Test Results

## Before

The unchanged test files contain characterization tests for the original behavior. Their `KnownBugTests` document the behaviors expected to change, including plaintext password output, non-atomic signup, `None` totals, GET mutations, duplicate approval, unsafe deletion, and unhandled missing records.

## After

We ran:

```text
./.venv/bin/python manage.py test loanApp loginApp managerApp
```

```text
Ran 66 tests in 77.815s
FAILED (failures=17)
```

The result was **49 passing tests and 17 expected failures**. Every failure came from an unchanged `KnownBugTests` class asserting the old behavior that the refactor fixes. The project Python 3.9 `.venv` was used because the bundled dependencies are incompatible with Python 3.14.

Additional checks:

- `python3 -m py_compile loanApp/views.py loginApp/views.py managerApp/views.py`: **passed**.
- `git diff --check`: **passed**.
- The three test files remained unchanged.
