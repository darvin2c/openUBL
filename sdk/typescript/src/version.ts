export const SDK_VERSION = "0.1.4";

export async function checkApiVersion(
  baseUrl: string = "http://localhost:8000"
): Promise<{ ok: boolean; sdkVersion: string; apiVersion: string }> {
  const res = await fetch(`${baseUrl}/api/v1/version`);
  if (!res.ok) {
    throw new Error(`Failed to fetch API version: ${res.status}`);
  }
  const { version } = (await res.json()) as { version: string };
  return { ok: version === SDK_VERSION, sdkVersion: SDK_VERSION, apiVersion: version };
}
