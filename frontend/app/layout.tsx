export const metadata = {
  title: "Threshold — Deal Friction Intelligence",
  description: "Autonomous internal approval bottleneck agent",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body style={{ fontFamily: "sans-serif", margin: 0 }}>{children}</body>
    </html>
  );
}
