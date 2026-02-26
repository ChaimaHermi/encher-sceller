export interface ImageInfo {
  filename: string;
  original_name: string;
}

/** Récupère les images d'un listing (images[] ou image pour rétrocompat) */
export function getListingImages(listing: { images?: ImageInfo[]; image?: ImageInfo }): ImageInfo[] {
  if (listing.images?.length) return listing.images;
  if (listing.image) return [listing.image];
  return [];
}

/** Première image pour miniature/aperçu */
export function getFirstImage(listing: { images?: ImageInfo[]; image?: ImageInfo }): ImageInfo | null {
  const imgs = getListingImages(listing);
  return imgs[0] ?? null;
}
