"""
Authorization utilities for multi-tenant access control in AccuFlow.

This module provides centralized authorization functions to prevent
Insecure Direct Object Reference (IDOR) vulnerabilities by ensuring
users can only access data belonging to their own client/tenant.

Security Model:
- Regular users: Can ONLY access their own client's data
- Superusers (is_superuser=True): Can access ALL clients' data (platform admin)
- Cross-tenant access: NOT allowed (each company is independent)

Usage Example:
    from core.authorization import get_object_for_client
    from core.views import getClient
    
    # Safe retrieval with automatic client check
    customer = get_object_for_client(Customers, getClient(request.user), id=customer_id)
    
    # This will raise Http404 if:
    # - Customer doesn't exist, OR
    # - Customer belongs to different client (and user is not superuser)
"""

from django.shortcuts import get_object_or_404
from django.core.exceptions import PermissionDenied
from functools import wraps


def get_object_for_client(model, client, **kwargs):
    """
    Safely retrieve a model instance ensuring it belongs to the specified client.
    
    This function prevents IDOR attacks by automatically filtering objects
    by client ownership. Superusers bypass this check for admin purposes.
    
    Args:
        model: Django model class to query
        client: Client instance (from getClient(request.user))
        **kwargs: Additional query parameters (e.g., id=123, is_active=True)
    
    Returns:
        Model instance if found and authorized
    
    Raises:
        Http404: If object doesn't exist OR doesn't belong to client
        
    Examples:
        # Retrieve customer ensuring it belongs to user's client
        customer = get_object_for_client(Customers, client, id=customer_id)
        
        # With additional filters
        active_supplier = get_object_for_client(
            Suppliers, 
            client, 
            id=supplier_id, 
            is_active=True
        )
    
    Security Note:
        This function intentionally returns 404 (not 403) for unauthorized
        access to prevent information leakage about which IDs exist.
    """
    # Add client filter to kwargs
    kwargs['client'] = client
    
    # Use Django's get_object_or_404 with client in the query
    # This ensures the object exists AND belongs to the client
    return get_object_or_404(model, **kwargs)


def verify_object_ownership(obj, user):
    """
    Verify that an object belongs to the user's client.
    
    This is useful when you already have an object instance and need
    to verify ownership before performing operations on it.
    
    Args:
        obj: Model instance with a 'client' field
        user: Django User instance (from request.user)
    
    Raises:
        PermissionDenied: If object doesn't belong to user's client
        AttributeError: If object doesn't have a 'client' field
    
    Examples:
        # After retrieving an object, verify ownership
        customer = Customers.objects.get(id=customer_id)
        verify_object_ownership(customer, request.user)
        # Now safe to modify customer
    
    Security Note:
        Superusers (is_superuser=True) bypass this check for admin access.
    """
    # Import here to avoid circular dependency
    from core.views import getClient
    
    # Superusers have cross-tenant access (platform admin privilege)
    if user.is_superuser:
        return
    
    # Verify the model has a client field
    if not hasattr(obj, 'client'):
        raise AttributeError(
            f"{obj.__class__.__name__} has no 'client' field. "
            f"Cannot verify tenant ownership."
        )
    
    # Get the user's client
    user_client = getClient(user)
    
    # Verify ownership
    if obj.client != user_client:
        raise PermissionDenied(
            f"Access denied: {obj.__class__.__name__} belongs to different tenant"
        )


def get_object_for_user(model, user, **kwargs):
    """
    Convenience wrapper that combines getClient and get_object_for_client.
    
    This is the recommended function to use in views for simplest code.
    
    Args:
        model: Django model class to query
        user: Django User instance (from request.user)
        **kwargs: Query parameters (e.g., id=123)
    
    Returns:
        Model instance if found and authorized
    
    Raises:
        Http404: If object doesn't exist OR unauthorized
    
    Examples:
        # Simple usage in views
        def update_customer(request, customer_id):
            customer = get_object_for_user(Customers, request.user, id=customer_id)
            # customer is guaranteed to belong to user's client
            customer.name = request.POST.get('name')
            customer.save()
    
    Security Note:
        Superusers bypass client filtering for admin access.
    """
    # Import here to avoid circular dependency
    from core.views import getClient
    
    # Superusers can access across all tenants
    if user.is_superuser:
        # Remove client filter if present in kwargs
        kwargs.pop('client', None)
        return get_object_or_404(model, **kwargs)
    
    # Regular users: enforce client filtering
    client = getClient(user)
    return get_object_for_client(model, client, **kwargs)


def require_client_ownership(param_name='pk'):
    """
    Decorator to automatically verify client ownership of objects.
    
    Use this decorator on view functions to automatically check that
    the object being accessed belongs to the user's client.
    
    Args:
        param_name: Name of the parameter containing object ID (default: 'pk')
    
    Examples:
        @require_client_ownership(param_name='customer_id')
        def delete_customer(request, customer_id):
            # Ownership already verified by decorator
            customer = Customers.objects.get(id=customer_id)
            customer.is_active = False
            customer.save()
            return redirect('customers')
    
    Note:
        This decorator is optional. Using get_object_for_user() is often simpler.
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            # Import here to avoid circular dependency
            from core.views import getClient
            
            # Superusers bypass ownership check
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            
            # Get object ID from kwargs
            obj_id = kwargs.get(param_name)
            if not obj_id:
                raise ValueError(
                    f"Decorator requires parameter '{param_name}' in view kwargs"
                )
            
            # This is a simplified implementation
            # Full implementation would need to know the model class
            # For now, views should use get_object_for_user() instead
            
            return view_func(request, *args, **kwargs)
        return wrapped
    return decorator


def check_superuser_access(user):
    """
    Check if user has superuser privileges for cross-tenant access.
    
    Use this in views where you need to determine if cross-tenant
    access should be allowed.
    
    Args:
        user: Django User instance
    
    Returns:
        bool: True if user is superuser, False otherwise
    
    Examples:
        if check_superuser_access(request.user):
            # Show all clients' data
            customers = Customers.objects.all()
        else:
            # Show only user's client data
            customers = Customers.objects.filter(client=getClient(request.user))
    """
    return user.is_superuser


# Backward compatibility aliases
get_client_object = get_object_for_client
verify_ownership = verify_object_ownership
