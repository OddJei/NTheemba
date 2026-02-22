/* Minimal global JSX types to satisfy TypeScript when @types/react isn't available. */
declare namespace JSX {
  interface IntrinsicElements {
    [elemName: string]: any;
  }
}
