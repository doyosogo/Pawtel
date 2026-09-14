import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { HomePage } from './HomePage';
describe('foundation home', () => {
  it('communicates the product and current milestone', () => {
    render(<HomePage />);
    expect(screen.getByRole('heading', { name: 'PAWTEL' })).toBeInTheDocument();
    expect(
      screen.getByText('Pet boarding across Australia.'),
    ).toBeInTheDocument();
    expect(screen.getByText('Foundation milestone')).toBeInTheDocument();
  });
});
