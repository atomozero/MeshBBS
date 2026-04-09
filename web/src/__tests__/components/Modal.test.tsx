/**
 * Modal component tests.
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { Modal, ConfirmModal } from '@/components/ui/Modal';

describe('Modal', () => {
  it('renders when open', () => {
    render(
      <Modal isOpen={true} onClose={() => {}} title="Test Modal">
        <p>Modal content</p>
      </Modal>
    );

    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.getByText('Test Modal')).toBeInTheDocument();
    expect(screen.getByText('Modal content')).toBeInTheDocument();
  });

  it('does not render when closed', () => {
    render(
      <Modal isOpen={false} onClose={() => {}} title="Test Modal">
        <p>Modal content</p>
      </Modal>
    );

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('calls onClose when close button clicked', () => {
    const handleClose = vi.fn();
    render(
      <Modal isOpen={true} onClose={handleClose} title="Test Modal">
        <p>Content</p>
      </Modal>
    );

    const closeButton = screen.getByLabelText('Close modal');
    fireEvent.click(closeButton);

    expect(handleClose).toHaveBeenCalledTimes(1);
  });

  it('calls onClose when backdrop clicked', () => {
    const handleClose = vi.fn();
    render(
      <Modal isOpen={true} onClose={handleClose} title="Test Modal">
        <p>Content</p>
      </Modal>
    );

    // Find backdrop by its classes
    const backdrop = document.querySelector('.fixed.inset-0.bg-black\\/50');
    if (backdrop) {
      fireEvent.click(backdrop);
      expect(handleClose).toHaveBeenCalledTimes(1);
    }
  });
});

describe('ConfirmModal', () => {
  it('renders with title and message', () => {
    render(
      <ConfirmModal
        isOpen={true}
        onClose={() => {}}
        onConfirm={() => {}}
        title="Confirm Delete"
        message="Are you sure you want to delete this item?"
      />
    );

    expect(screen.getByText('Confirm Delete')).toBeInTheDocument();
    expect(
      screen.getByText('Are you sure you want to delete this item?')
    ).toBeInTheDocument();
  });

  it('calls onConfirm when confirm button clicked', () => {
    const handleConfirm = vi.fn();
    render(
      <ConfirmModal
        isOpen={true}
        onClose={() => {}}
        onConfirm={handleConfirm}
        title="Confirm"
        message="Confirm action?"
        confirmText="Yes, Delete"
      />
    );

    fireEvent.click(screen.getByText('Yes, Delete'));
    expect(handleConfirm).toHaveBeenCalledTimes(1);
  });

  it('calls onClose when cancel button clicked', () => {
    const handleClose = vi.fn();
    render(
      <ConfirmModal
        isOpen={true}
        onClose={handleClose}
        onConfirm={() => {}}
        title="Confirm"
        message="Confirm action?"
        cancelText="No"
      />
    );

    fireEvent.click(screen.getByText('No'));
    expect(handleClose).toHaveBeenCalledTimes(1);
  });

  it('shows loading state', () => {
    render(
      <ConfirmModal
        isOpen={true}
        onClose={() => {}}
        onConfirm={() => {}}
        title="Confirm"
        message="Confirm?"
        loading={true}
      />
    );

    // Cancel button should be disabled during loading
    expect(screen.getByText('Cancel')).toBeDisabled();
  });
});
