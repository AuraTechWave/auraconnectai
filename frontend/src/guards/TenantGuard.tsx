import React, { useEffect, useState } from 'react';
import { Navigate, useParams } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import LoadingSpinner from '../components/customer/LoadingSpinner';
import ErrorMessage from '../components/customer/ErrorMessage';

interface TenantGuardProps {
  children: React.ReactNode;
  requireTenant?: boolean;
  validateAccess?: boolean;
}

export const TenantGuard: React.FC<TenantGuardProps> = ({
  children,
  requireTenant = true,
  validateAccess = true,
}) => {
  const { restaurantId } = useParams();
  const { user, currentTenant, setCurrentTenant, validateTenantAccess } = useAuth();
  const [isValidating, setIsValidating] = useState(true);
  const [hasAccess, setHasAccess] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const validate = async () => {
      if (!requireTenant) {
        setIsValidating(false);
        setHasAccess(true);
        return;
      }

      if (!restaurantId) {
        setError('Restaurant ID is required');
        setIsValidating(false);
        return;
      }

      try {
        // Validate user has access to this tenant
        if (validateAccess) {
          const accessGranted = await validateTenantAccess(restaurantId);
          if (!accessGranted) {
            setError('You do not have access to this restaurant');
            setIsValidating(false);
            return;
          }
        }

        // Set current tenant context
        if (currentTenant?.id !== restaurantId) {
          await setCurrentTenant(restaurantId);
        }

        setHasAccess(true);
      } catch (err) {
        setError('Failed to validate restaurant access');
        console.error('Tenant validation error:', err);
      } finally {
        setIsValidating(false);
      }
    };

    validate();
  }, [restaurantId, requireTenant, validateAccess, currentTenant, setCurrentTenant, validateTenantAccess]);

  if (isValidating) {
    return <LoadingSpinner message="Validating restaurant access..." />;
  }

  if (error) {
    return <ErrorMessage type="error" message={error} onRetry={() => window.location.reload()} />;
  }

  if (!hasAccess) {
    return <Navigate to="/restaurants" replace />;
  }

  return <>{children}</>;
};

export default TenantGuard;