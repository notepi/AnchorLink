import type { Config } from 'tailwindcss';

const config: Config = {
  darkMode: 'class',
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        // A股风格颜色系统（涨红跌绿）
        anchor: {
          bg: '#0a0a0a',
          bgSecondary: '#111111',
          bgTertiary: '#1a1a1a',
          card: '#111111',
          border: '#262626',
          borderSubtle: '#1f1f1f',
          text: '#e5e5e5',
          textSecondary: '#a3a3a3',
          textTertiary: '#737373',
          textMuted: '#525252',
          accent: '#3b82f6',
          positive: '#ef4444', // A股：涨 = 红色
          negative: '#22c55e', // A股：跌 = 绿色
          neutral: '#71717a',
        },
        // 信号类别色（克制使用）
        signal: {
          beta: '#3b82f6',
          alpha: '#8b5cf6',
          volume: '#f59e0b',
          rotation: '#06b6d4',
          abnormal: '#ec4899',
        },
      },
      spacing: {
        // 紧凑间距
        '0.5': '2px',
        '1': '4px',
        '1.5': '6px',
        '2': '8px',
        '3': '12px',
        '4': '16px',
      },
      borderRadius: {
        // 小圆角（克制）
        sm: '2px',
        DEFAULT: '4px',
        md: '6px',
      },
      fontSize: {
        // 信息密集字体
        xs: ['12px', { lineHeight: '16px' }],
        sm: ['13px', { lineHeight: '18px' }],
        base: ['14px', { lineHeight: '20px' }],
      },
      fontFamily: {
        sans: ['var(--font-inter)'],
        mono: ['var(--font-geist-mono)'],
      },
      // 响应式断点
      screens: {
        sm: '640px',
        md: '768px',
        lg: '1024px',
        xl: '1280px',
      },
    },
  },
  plugins: [],
};

export default config;