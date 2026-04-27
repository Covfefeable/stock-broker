export function buildTaskCenterWsUrl(token: string): string {
  const configuredBase = process.env.NEXT_PUBLIC_WS_BASE_URL?.replace(/\/$/, "");
  if (configuredBase) {
    return `${configuredBase}/ws/tasks?token=${encodeURIComponent(token)}`;
  }

  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  const { hostname, host, port } = window.location;
  const isLocalNextDev =
    (hostname === "localhost" || hostname === "127.0.0.1") &&
    (port === "3000" || port === "3001");
  const wsHost = isLocalNextDev ? `${hostname}:8000` : host;

  return `${protocol}://${wsHost}/ws/tasks?token=${encodeURIComponent(token)}`;
}
