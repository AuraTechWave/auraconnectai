// frontend/components/menu/__tests__/MenuVersioning.test.tsx

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';
import '@testing-library/jest-dom';

import MenuVersioning from '../MenuVersioning';
import { useRBAC } from '../../../hooks/useRBAC';
import { useNotifications } from '../../ui/Notification';
import { useApiQuery } from '../../../hooks/useApiQuery';
import apiClient from '../../../utils/authInterceptor';

// Mock dependencies
vi.mock('../../../hooks/useRBAC');
vi.mock('../../ui/Notification');
vi.mock('../../../hooks/useApiQuery');
vi.mock('../../../utils/authInterceptor');

const mockUseRBAC = vi.mocked(useRBAC);
const mockUseNotifications = vi.mocked(useNotifications);
const mockUseApiQuery = vi.mocked(useApiQuery);
const mockApiClient = vi.mocked(apiClient);

describe('MenuVersioning Component', () => {
  const mockAddNotification = vi.fn();
  const mockRefetch = vi.fn();

  // Sample data
  const mockVersionsData = {
    items: [
      {
        id: 1,
        version_number: 'v20250728-001',
        version_name: 'Test Version',
        description: 'Test description',
        version_type: 'manual',
        is_active: true,
        is_published: true,
        published_at: '2025-01-28T10:00:00Z',
        created_by: 1,
        total_items: 10,
        total_categories: 3,
        total_modifiers: 5,
        created_at: '2025-01-28T09:00:00Z',
        updated_at: '2025-01-28T09:00:00Z'
      },
      {
        id: 2,
        version_number: 'v20250728-002',
        version_name: 'Draft Version',
        description: 'Draft for testing',
        version_type: 'manual',
        is_active: false,
        is_published: false,
        created_by: 1,
        total_items: 8,
        total_categories: 2,
        total_modifiers: 4,
        created_at: '2025-01-28T11:00:00Z',
        updated_at: '2025-01-28T11:00:00Z'
      }
    ],
    total: 2,
    page: 1,
    size: 20,
    pages: 1
  };

  const mockAuditLogs = {
    items: [
      {
        id: 1,
        action: 'create_version',
        entity_type: 'menu_version',
        entity_name: 'Test Version',
        change_type: 'create',
        change_summary: 'Created new version',
        user_id: 1,
        created_at: '2025-01-28T09:00:00Z'
      }
    ],
    total: 1,
    page: 1,
    size: 50,
    pages: 1
  };

  const mockVersionStats = {
    total_versions: 5,
    published_versions: 3,
    draft_versions: 2,
    scheduled_versions: 0,
    total_changes_today: 8,
    active_version: mockVersionsData.items[0]
  };

  beforeEach(() => {
    // Reset all mocks
    vi.clearAllMocks();

    // Setup default mock implementations
    mockUseRBAC.mockReturnValue({
      hasPermission: vi.fn((permission: string) => {
        // Grant all permissions by default
        return true;
      })
    });

    mockUseNotifications.mockReturnValue({
      addNotification: mockAddNotification,
      NotificationContainer: () => <div data-testid="notification-container" />
    });

    // Setup API query mocks
    mockUseApiQuery
      .mockReturnValueOnce({
        data: mockVersionsData,
        loading: false,
        error: null,
        refetch: mockRefetch
      })
      .mockReturnValueOnce({
        data: mockAuditLogs,
        loading: false,
        error: null,
        refetch: mockRefetch
      })
      .mockReturnValueOnce({
        data: mockVersionStats,
        loading: false,
        error: null,
        refetch: mockRefetch
      });

    // Setup API client mocks
    mockApiClient.post = vi.fn();
    mockApiClient.delete = vi.fn();
  });

  afterEach(() => {
    vi.resetAllMocks();
  });

  describe('Rendering', () => {
    it('renders the component with correct title', () => {
      render(<MenuVersioning />);
      
      expect(screen.getByText('Menu Versioning & Audit Trail')).toBeInTheDocument();
    });

    it('displays version statistics correctly', () => {
      render(<MenuVersioning />);
      
      expect(screen.getByText('5')).toBeInTheDocument(); // total versions
      expect(screen.getByText('3')).toBeInTheDocument(); // published
      expect(screen.getByText('2')).toBeInTheDocument(); // drafts
      expect(screen.getByText('8')).toBeInTheDocument(); // changes today
    });

    it('shows loading state when versions are loading', () => {
      mockUseApiQuery
        .mockReturnValueOnce({
          data: null,
          loading: true,
          error: null,
          refetch: mockRefetch
        })
        .mockReturnValueOnce({
          data: mockAuditLogs,
          loading: false,
          error: null,
          refetch: mockRefetch
        })
        .mockReturnValueOnce({
          data: mockVersionStats,
          loading: false,
          error: null,
          refetch: mockRefetch
        });

      render(<MenuVersioning />);
      
      expect(screen.getByText('Loading menu versions...')).toBeInTheDocument();
    });

    it('renders tab navigation correctly', () => {
      render(<MenuVersioning />);
      
      expect(screen.getByText('Versions')).toBeInTheDocument();
      expect(screen.getByText('Comparison')).toBeInTheDocument();
      expect(screen.getByText('Audit Trail')).toBeInTheDocument();
    });
  });

  describe('Tab Navigation', () => {
    it('switches between tabs correctly', () => {
      render(<MenuVersioning />);
      
      // Initially on versions tab
      expect(screen.getByText('Create Version')).toBeInTheDocument();
      
      // Switch to audit trail tab
      fireEvent.click(screen.getByText('Audit Trail'));
      
      // Should show audit content
      expect(screen.getByText('create_version')).toBeInTheDocument();
    });

    it('shows comparison tab empty state initially', () => {
      render(<MenuVersioning />);
      
      fireEvent.click(screen.getByText('Comparison'));
      
      expect(screen.getByText('Select two versions from the Versions tab to compare them.')).toBeInTheDocument();
    });
  });

  describe('Version Management', () => {
    it('opens create version modal when button is clicked', () => {
      render(<MenuVersioning />);
      
      fireEvent.click(screen.getByText('Create Version'));
      
      expect(screen.getByText('Create New Version')).toBeInTheDocument();
      expect(screen.getByPlaceholderText('Optional descriptive name')).toBeInTheDocument();
    });

    it('closes create version modal when cancel is clicked', () => {
      render(<MenuVersioning />);
      
      fireEvent.click(screen.getByText('Create Version'));
      fireEvent.click(screen.getByText('Cancel'));
      
      expect(screen.queryByText('Create New Version')).not.toBeInTheDocument();
    });

    it('handles version creation form submission', async () => {
      mockApiClient.post.mockResolvedValueOnce({ data: { id: 3 } });
      
      render(<MenuVersioning />);
      
      // Open modal and fill form
      fireEvent.click(screen.getByText('Create Version'));
      
      const nameInput = screen.getByPlaceholderText('Optional descriptive name');
      const descriptionInput = screen.getByPlaceholderText('Describe the changes in this version');
      
      fireEvent.change(nameInput, { target: { value: 'New Test Version' } });
      fireEvent.change(descriptionInput, { target: { value: 'Test description' } });
      
      // Submit form
      fireEvent.click(screen.getByText('Create Version'));
      
      await waitFor(() => {
        expect(mockApiClient.post).toHaveBeenCalledWith('/menu/versions', {
          version_name: 'New Test Version',
          description: 'Test description',
          version_type: 'manual',
          include_inactive: false,
          scheduled_publish_at: null
        });
      });
      
      expect(mockAddNotification).toHaveBeenCalledWith({
        type: 'success',
        message: 'Version "New Test Version" created successfully'
      });
    });

    it('handles version creation error', async () => {
      mockApiClient.post.mockRejectedValueOnce({
        response: { data: { detail: 'Creation failed' } }
      });
      
      render(<MenuVersioning />);
      
      fireEvent.click(screen.getByText('Create Version'));
      fireEvent.click(screen.getByText('Create Version'));
      
      await waitFor(() => {
        expect(mockAddNotification).toHaveBeenCalledWith({
          type: 'error',
          message: 'Creation failed'
        });
      });
    });
  });

  describe('Version Actions', () => {
    it('allows publishing unpublished versions', () => {
      render(<MenuVersioning />);
      
      // The draft version should have a publish button
      const publishButtons = screen.getAllByText('Publish');
      expect(publishButtons.length).toBeGreaterThan(0);
    });

    it('handles version publishing', async () => {
      mockApiClient.post.mockResolvedValueOnce({ data: {} });
      
      render(<MenuVersioning />);
      
      const publishButtons = screen.getAllByText('Publish');
      fireEvent.click(publishButtons[0]);
      
      await waitFor(() => {
        expect(mockApiClient.post).toHaveBeenCalledWith(
          expect.stringContaining('/publish'),
          expect.any(Object)
        );
      });
    });

    it('handles version rollback with confirmation', async () => {
      // Mock window.prompt
      const mockPrompt = vi.spyOn(window, 'prompt').mockReturnValue('Test rollback reason');
      mockApiClient.post.mockResolvedValueOnce({ data: {} });
      
      render(<MenuVersioning />);
      
      const rollbackButtons = screen.getAllByText('Rollback');
      fireEvent.click(rollbackButtons[0]);
      
      await waitFor(() => {
        expect(mockPrompt).toHaveBeenCalledWith('Please provide a reason for the rollback:');
        expect(mockApiClient.post).toHaveBeenCalledWith('/menu/versions/rollback', {
          target_version_id: expect.any(Number),
          create_backup: true,
          rollback_reason: 'Test rollback reason'
        });
      });
      
      mockPrompt.mockRestore();
    });

    it('cancels rollback when no reason is provided', () => {
      const mockPrompt = vi.spyOn(window, 'prompt').mockReturnValue(null);
      
      render(<MenuVersioning />);
      
      const rollbackButtons = screen.getAllByText('Rollback');
      fireEvent.click(rollbackButtons[0]);
      
      expect(mockApiClient.post).not.toHaveBeenCalled();
      
      mockPrompt.mockRestore();
    });

    it('handles version deletion with confirmation', async () => {
      const mockConfirm = vi.spyOn(window, 'confirm').mockReturnValue(true);
      mockApiClient.delete.mockResolvedValueOnce({ data: {} });
      
      render(<MenuVersioning />);
      
      const deleteButtons = screen.getAllByText('Delete');
      fireEvent.click(deleteButtons[0]);
      
      await waitFor(() => {
        expect(mockConfirm).toHaveBeenCalled();
        expect(mockApiClient.delete).toHaveBeenCalledWith(
          expect.stringContaining('/menu/versions/')
        );
      });
      
      mockConfirm.mockRestore();
    });
  });

  describe('Version Selection and Comparison', () => {
    it('tracks selected versions for comparison', () => {
      render(<MenuVersioning />);
      
      // Select first version
      const checkboxes = screen.getAllByRole('checkbox');
      fireEvent.click(checkboxes[0]);
      
      expect(screen.getByText('1 version(s) selected')).toBeInTheDocument();
    });

    it('enables compare button when two versions are selected', () => {
      render(<MenuVersioning />);
      
      const checkboxes = screen.getAllByRole('checkbox');
      fireEvent.click(checkboxes[0]);
      fireEvent.click(checkboxes[1]);
      
      expect(screen.getByText('2 version(s) selected')).toBeInTheDocument();
      expect(screen.getByText('Compare Selected')).toBeInTheDocument();
    });

    it('handles version comparison', async () => {
      const mockComparisonResult = {
        from_version_id: 1,
        to_version_id: 2,
        from_version_number: 'v20250728-001',
        to_version_number: 'v20250728-002',
        summary: { created: 2, updated: 1, deleted: 0 },
        categories: [],
        items: [],
        modifiers: [],
        generated_at: '2025-01-28T12:00:00Z'
      };
      
      mockApiClient.post.mockResolvedValueOnce({ data: mockComparisonResult });
      
      render(<MenuVersioning />);
      
      // Select two versions
      const checkboxes = screen.getAllByRole('checkbox');
      fireEvent.click(checkboxes[0]);
      fireEvent.click(checkboxes[1]);
      
      // Click compare
      fireEvent.click(screen.getByText('Compare Selected'));
      
      await waitFor(() => {
        expect(mockApiClient.post).toHaveBeenCalledWith('/menu/versions/compare', {
          from_version_id: expect.any(Number),
          to_version_id: expect.any(Number),
          include_details: true
        });
      });
    });

    it('shows error when trying to compare without selecting two versions', () => {
      render(<MenuVersioning />);
      
      // Select only one version
      const checkboxes = screen.getAllByRole('checkbox');
      fireEvent.click(checkboxes[0]);
      
      // Try to compare
      fireEvent.click(screen.getByText('Compare Selected'));
      
      expect(mockAddNotification).toHaveBeenCalledWith({
        type: 'error',
        message: 'Please select exactly 2 versions to compare'
      });
    });
  });

  describe('Permissions', () => {
    it('hides create button when user lacks create permission', () => {
      mockUseRBAC.mockReturnValue({
        hasPermission: vi.fn((permission: string) => {
          return permission !== 'menu:create';
        })
      });
      
      render(<MenuVersioning />);
      
      expect(screen.queryByText('Create Version')).not.toBeInTheDocument();
    });

    it('shows error notification when user tries unauthorized actions', async () => {
      mockUseRBAC.mockReturnValue({
        hasPermission: vi.fn(() => false)
      });
      
      render(<MenuVersioning />);
      
      // Try to publish (should show error)
      const publishButtons = screen.getAllByText('Publish');
      if (publishButtons.length > 0) {
        fireEvent.click(publishButtons[0]);
        
        expect(mockAddNotification).toHaveBeenCalledWith({
          type: 'error',
          message: 'You do not have permission to publish versions'
        });
      }
    });
  });

  describe('Audit Trail', () => {
    it('displays audit logs correctly', () => {
      render(<MenuVersioning />);
      
      fireEvent.click(screen.getByText('Audit Trail'));
      
      expect(screen.getByText('create_version')).toBeInTheDocument();
      expect(screen.getByText('menu_version')).toBeInTheDocument();
      expect(screen.getByText('Created new version')).toBeInTheDocument();
    });

    it('formats audit log timestamps correctly', () => {
      render(<MenuVersioning />);
      
      fireEvent.click(screen.getByText('Audit Trail'));
      
      // Should display formatted timestamp
      const timestamp = new Date('2025-01-28T09:00:00Z').toLocaleString();
      expect(screen.getByText(timestamp)).toBeInTheDocument();
    });
  });

  describe('Error Handling', () => {
    it('handles API errors gracefully', () => {
      mockUseApiQuery
        .mockReturnValueOnce({
          data: null,
          loading: false,
          error: 'API Error',
          refetch: mockRefetch
        })
        .mockReturnValueOnce({
          data: mockAuditLogs,
          loading: false,
          error: null,
          refetch: mockRefetch
        })
        .mockReturnValueOnce({
          data: mockVersionStats,
          loading: false,
          error: null,
          refetch: mockRefetch
        });

      render(<MenuVersioning />);
      
      // Should show loading text when there's an error and no data
      expect(screen.getByText('Loading menu versions...')).toBeInTheDocument();
    });

    it('handles network errors in form submission', async () => {
      mockApiClient.post.mockRejectedValueOnce(new Error('Network error'));
      
      render(<MenuVersioning />);
      
      fireEvent.click(screen.getByText('Create Version'));
      fireEvent.click(screen.getByText('Create Version'));
      
      await waitFor(() => {
        expect(mockAddNotification).toHaveBeenCalledWith({
          type: 'error',
          message: 'Failed to create version'
        });
      });
    });
  });

  describe('Form Validation', () => {
    it('validates scheduled version requires datetime', () => {
      render(<MenuVersioning />);
      
      fireEvent.click(screen.getByText('Create Version'));
      
      // Change to scheduled type
      const versionTypeSelect = screen.getByDisplayValue('manual');
      fireEvent.change(versionTypeSelect, { target: { value: 'scheduled' } });
      
      // Should show datetime input
      expect(screen.getByLabelText('Scheduled Publish Time')).toBeInTheDocument();
    });

    it('handles form reset after successful creation', async () => {
      mockApiClient.post.mockResolvedValueOnce({ data: { id: 3 } });
      
      render(<MenuVersioning />);
      
      fireEvent.click(screen.getByText('Create Version'));
      
      const nameInput = screen.getByPlaceholderText('Optional descriptive name');
      fireEvent.change(nameInput, { target: { value: 'Test Version' } });
      
      fireEvent.click(screen.getByText('Create Version'));
      
      await waitFor(() => {
        expect(mockRefetch).toHaveBeenCalled(); // Should refetch data
      });
      
      // Modal should be closed and form reset
      expect(screen.queryByText('Create New Version')).not.toBeInTheDocument();
    });
  });
});