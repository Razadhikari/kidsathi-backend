from rest_framework.permissions import SAFE_METHODS, BasePermission

from apps.core.tenancy import get_request_school

SCHOOL_ADMIN = "school_admin"
TEACHER = "teacher"
ACCOUNTANT = "accountant"
PARENT = "parent"
STAFF_ROLES = {SCHOOL_ADMIN, TEACHER, ACCOUNTANT}


class SchoolRolePermission(BasePermission):
    """Allow if the user holds one of `read_roles` (safe methods) or `write_roles` in the current school.

    Subclass and set the two sets, or use `school_roles(read=..., write=...)`.
    """

    read_roles: set[str] = set()
    write_roles: set[str] = set()

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        _school, roles = get_request_school(request)
        if request.user.is_superuser:
            return True
        allowed = self.read_roles | self.write_roles if request.method in SAFE_METHODS else self.write_roles
        return bool(roles & allowed)


def school_roles(read: set[str], write: set[str]):
    return type("SchoolRoles", (SchoolRolePermission,), {"read_roles": set(read), "write_roles": set(write)})
