import type { Config } from "tailwindcss"

const config = {
  darkMode: ["class"],
  content: [
    './pages/**/*.{ts,tsx}',
    './components/**/*.{ts,tsx}',
    './app/**/*.{ts,tsx}',
    './src/**/*.{ts,tsx}',
  ],
  prefix: "",
  theme: {
  	container: {
  		center: true,
  		padding: '2rem',
  		screens: {
  			'2xl': '1400px'
  		}
  	},
  	extend: {
  		colors: {
  			border: '#27272A',
  			input: '#27272A',
  			ring: '#4F46E5',
  			background: '#09090B',
  			foreground: '#FFFFFF',
  			primary: {
  				DEFAULT: '#4F46E5',
  				foreground: '#FFFFFF'
  			},
  			secondary: {
  				DEFAULT: '#111113',
  				foreground: '#9CA3AF'
  			},
  			destructive: {
  				DEFAULT: '#EF4444',
  				foreground: '#FFFFFF'
  			},
  			success: {
  				DEFAULT: '#22C55E',
  				foreground: '#FFFFFF'
  			},
  			warning: {
  				DEFAULT: '#F59E0B',
  				foreground: '#FFFFFF'
  			},
  			muted: {
  				DEFAULT: '#111113',
  				foreground: '#9CA3AF'
  			},
  			accent: {
  				DEFAULT: '#111113',
  				foreground: '#FFFFFF'
  			},
  			popover: {
  				DEFAULT: '#111113',
  				foreground: '#FFFFFF'
  			},
  			card: {
  				DEFAULT: '#111113',
  				foreground: '#FFFFFF'
  			}
  		},
  		borderRadius: {
  			lg: '16px',
  			md: '12px',
  			sm: '8px'
  		},
  		keyframes: {
  			'accordion-down': {
  				from: {
  					height: '0'
  				},
  				to: {
  					height: 'var(--radix-accordion-content-height)'
  				}
  			},
  			'accordion-up': {
  				from: {
  					height: 'var(--radix-accordion-content-height)'
  				},
  				to: {
  					height: '0'
  				}
  			},
  		},
  		animation: {
  			'accordion-down': 'accordion-down 0.2s ease-out',
  			'accordion-up': 'accordion-up 0.2s ease-out'
  		},
  		fontFamily: {
  			sans: [
  				'var(--font-inter)',
  				'sans-serif'
  			]
  		}
  	}
  },
  plugins: [require("tailwindcss-animate")],
} satisfies Config

export default config
