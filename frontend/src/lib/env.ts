const HTTP_PROTOCOLS = new Set(["http:", "https:"]);

export function getApiBaseUrl(): string {
  const rawValue = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();

  if (!rawValue) {
    throw new Error(
      "NEXT_PUBLIC_API_BASE_URL is required. Copy .env.example to .env.local.",
    );
  }

  let url: URL;
  try {
    url = new URL(rawValue);
  } catch {
    throw new Error("NEXT_PUBLIC_API_BASE_URL must be a valid absolute URL.");
  }

  if (!HTTP_PROTOCOLS.has(url.protocol)) {
    throw new Error("NEXT_PUBLIC_API_BASE_URL must use HTTP or HTTPS.");
  }

  return url.toString().replace(/\/$/, "");
}
