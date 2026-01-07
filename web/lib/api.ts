// web/lib/api.ts
export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

async function readJson(res: Response) {
  const txt = await res.text();
  try {
    return JSON.parse(txt);
  } catch {
    return { raw: txt };
  }
}

export async function createJob(input: {
  material: string;
  thickness_mm: number; // 0이면 자동
  qty: number;
}) {
  const res = await fetch(`${API_BASE}/v1/jobs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!res.ok) throw new Error(`createJob failed: ${res.status} ${await res.text()}`);
  return (await res.json()) as { id: string; status: string };
}

export async function uploadStep(jobId: string, file: File) {
  const fd = new FormData();
  fd.append("step", file);

  const res = await fetch(`${API_BASE}/v1/jobs/${jobId}/upload`, {
    method: "POST",
    body: fd,
  });
  if (!res.ok) throw new Error(`uploadStep failed: ${res.status} ${await res.text()}`);
  return await res.json();
}

export async function quote(jobId: string) {
  const res = await fetch(`${API_BASE}/v1/jobs/${jobId}/quote`, { method: "POST" });
  if (!res.ok) throw new Error(`quote failed: ${res.status} ${await res.text()}`);
  return await res.json();
}

export async function start(jobId: string) {
  const res = await fetch(`${API_BASE}/v1/jobs/${jobId}/start`, { method: "POST" });
  if (!res.ok) throw new Error(`start failed: ${res.status} ${await res.text()}`);
  return await res.json();
}

export async function getJob(jobId: string) {
  const res = await fetch(`${API_BASE}/v1/jobs/${jobId}`);
  if (!res.ok) throw new Error(`getJob failed: ${res.status} ${await res.text()}`);
  return await res.json();
}

export function previewSvgUrl(jobId: string) {
  return `${API_BASE}/v1/jobs/${jobId}/preview.svg`;
}

export function downloadDxfUrl(jobId: string) {
  return `${API_BASE}/v1/jobs/${jobId}/download/dxf`;
}

export async function seedVendor() {
  const res = await fetch(`${API_BASE}/v1/vendors/seed`, { method: "POST" });
  if (!res.ok) throw new Error(`seedVendor failed: ${res.status} ${await res.text()}`);
  return await res.json();
}

export async function dispatch(jobId: string, vendor_id: string) {
  const res = await fetch(`${API_BASE}/v1/jobs/${jobId}/dispatch`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ vendor_id }),
  });
  if (!res.ok) throw new Error(`dispatch failed: ${res.status} ${await res.text()}`);
  return await res.json();
}
