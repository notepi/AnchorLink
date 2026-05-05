import type { Metadata } from 'next';
import '@/styles/globals.css';

export const metadata: Metadata = {
  title: 'AnchorLink - 锚定联动分析',
  description: '专业的量化+新闻驱动市场情报仪表盘',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN" className="dark">
      <body className="font-sans antialiased">
        {children}
      </body>
    </html>
  );
}