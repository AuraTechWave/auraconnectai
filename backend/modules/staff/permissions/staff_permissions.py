def check_permission(user, permission_key):
    permissions = user.get("permissions", [])
    return permission_key in permissions
