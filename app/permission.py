from rest_framework.permissions import BasePermission, SAFE_METHODS


class HasPerm(BasePermission):
    codename=''

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.has_perm(self.codename)

class IsLibrarian(HasPerm):
    codename='app.manage_rentals'

class IsOrderManager(HasPerm):
    codename='app.manage_orders'

class IsCourier(HasPerm):
    codename='app.deliver_orders'

class IsSuperUserOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        return request.method in SAFE_METHODS or bool(request.user and request.user.is_superuser)

class IsLibrarianOfBookings(HasPerm):
    codename = 'app.review_chillzonebookings'

class IsCashier(HasPerm):
    codename = 'app.use_cash_register'

class IsSuperUser(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_superuser)

    