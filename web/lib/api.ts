// web/lib/api.ts
const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ||
  "https://step-laser-proxy.alexsungho10.workers.dev";

function buildUrl(path: string) {
  // path는 "/api/quote" 처럼 시작한다고 가정
  return `${API_BASE}${path}`;
}

async function readJson<T>(r: Response): Promise<T> {
  if (!r.ok) {
    const txt = await r.text().catch(() => "");
    throw new Error(`API ${r.status}: ${txt}`);
  }
  return (await r.json()) as T;
}

/**
 * ✅ 예: 견적 API
 * (너희가 /api/quote 를 쓰고 있으면 그대로 동작)
 */
export async function postQuote(formData: FormData) {
  const r = await fetch(buildUrl("/api/quote"), {
    method: "POST",
    body: formData,
  });
  return readJson<any>(r);
}

/**
 * ✅ 예: job 생성/업로드 API가 따로 있으면 여기에 맞춰 추가
 * 아래는 샘플 구조라 너희 백엔드 라우트에 맞게 수정하면 됨.
 */
export async function createJob(formData: FormData) {
  const r = await fetch(buildUrl("/api/jobs"), {
    method: "POST",
    body: formData,
  });
  return readJson<any>(r);
}

export async function getJob(jobId: string) {
  const r = await fetch(buildUrl(`/api/jobs/${encodeURIComponent(jobId)}`), {
    method: "GET",
  });
  return readJson<any>(r);
}

/**
 * ✅ 예: 변환 시작 엔드포인트가 있다면
 * (없으면 삭제해도 됨)
 */
export async function startConvert(jobId: string) {
  const r = await fetch(
    buildUrl(`/api/jobs/${encodeURIComponent(jobId)}/convert`),
    { method: "POST" }
  );
  return readJson<any>(r);
}
