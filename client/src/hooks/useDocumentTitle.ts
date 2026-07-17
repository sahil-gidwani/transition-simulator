import { useEffect } from 'react';

/** Sets the document title for the route; pass null while it is not yet known. */
export function useDocumentTitle(title: string | null) {
  useEffect(() => {
    if (title) document.title = title;
  }, [title]);
}
