/**
 * Tailwind is introduced alongside the existing hand-written CSS rather than
 * replacing it. The two coexist: `preflight` is disabled so Tailwind's reset
 * does not undo the styles every current screen depends on, and utilities are
 * available for new work.
 *
 * @type {import('tailwindcss').Config}
 */
export default {
  // Scoped to the real source extensions — this project is TypeScript, so
  // .{ts,tsx}. A glob naming .{js,jsx} would purge every class in the build.
  content: ['./index.html', './src/**/*.{ts,tsx}'],

  corePlugins: {
    // Tailwind's reset would flatten the existing component styles, which are
    // what the app currently renders with. Turning it off is what makes this
    // additive instead of a rewrite.
    preflight: false,
  },

  theme: {
    extend: {
      // Mapped to the CSS custom properties already defined in styles.css, so
      // a Tailwind utility and a hand-written rule cannot drift apart.
      colors: {
        surface: 'var(--surface)',
        border: 'var(--border)',
        muted: 'var(--text-muted)',
        accent: 'var(--accent)',
        danger: 'var(--danger)',
        success: 'var(--success)',
      },
      borderRadius: {
        DEFAULT: 'var(--radius)',
      },
    },
  },

  plugins: [],
}
