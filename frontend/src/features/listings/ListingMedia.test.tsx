import { fireEvent, screen } from '@testing-library/react';
import { expect, it } from 'vitest';
import { renderPage } from '../../test/render';
import { ListingCard } from './ListingCard';
import { ListingGallery } from './ListingGallery';
import { listing } from '../../test/fixtures';
const images = [
  {
    id: 'one',
    url: 'https://res.cloudinary.com/demo/image/upload/one',
    alt_text: 'Garden',
    sort_order: 0,
  },
  {
    id: 'two',
    url: 'https://res.cloudinary.com/demo/image/upload/two',
    alt_text: 'Sunroom',
    sort_order: 1,
  },
];
it('uses uploaded cover in public cards', () => {
  renderPage(<ListingCard listing={{ ...listing, images }} />);
  expect(screen.getByAltText('Garden')).toHaveAttribute('src', images[0].url);
  expect(screen.queryByText('Demo illustration')).not.toBeInTheDocument();
});
it('renders actual gallery photos in order', () => {
  renderPage(<ListingGallery listing={{ ...listing, images }} />);
  expect(screen.getByAltText('Garden')).toHaveAttribute('src', images[0].url);
  expect(screen.getByAltText('Sunroom')).toHaveAttribute('src', images[1].url);
});
it('retains seed placeholder and falls back after broken external photos', () => {
  renderPage(<ListingCard listing={{ ...listing, images }} />);
  fireEvent.error(screen.getByAltText('Garden'));
  expect(screen.getByText('Demo illustration')).toBeInTheDocument();
});
