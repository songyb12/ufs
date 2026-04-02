/**
 * Dev 모드에서는 서비스 포트로 직접 접속, prod(nginx)에서는 프록시 경로 사용.
 *
 * Why: Vite dev server 프록시는 HTML만 전달하고, 그 안의 asset 요청
 * (/src/*, /@vite/*)은 프록시를 우회 → Shell이 iframe 안에 재렌더링 → 404.
 * 직접 URL을 사용하면 모든 asset이 올바른 Vite 서버에서 로딩됨.
 */
export function getIframeUrl(proxyPath: string, svcPort: number, svcPath = '/'): string {
  if (import.meta.env.DEV) {
    return `http://${window.location.hostname}:${svcPort}${svcPath}`
  }
  return proxyPath
}
