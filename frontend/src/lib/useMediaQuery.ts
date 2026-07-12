import React from 'react';

/** Subscribe to a CSS media query; SSR-safe default until mount. */
export function useMediaQuery(query: string, defaultMatches = false): boolean {
  const [matches, setMatches] = React.useState(defaultMatches);

  React.useEffect(() => {
    const media = window.matchMedia(query);
    const onChange = () => setMatches(media.matches);
    onChange();
    media.addEventListener('change', onChange);
    return () => media.removeEventListener('change', onChange);
  }, [query]);

  return matches;
}
