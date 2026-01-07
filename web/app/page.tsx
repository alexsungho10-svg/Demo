"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { Job } from "@/lib/types";
import {
  createJob,
  uploadStep,
  quote,
  start,
  getJob,
  previewSvgUrl,
  downloadDxfUrl,
  seedVendor,
  dispatch,
  API_BASE,
} from "@/lib/api";

const MATERIALS = [
  { value: "steel", label: "철(SS400)" },
  { value: "stainless", label: "스테인리스(SUS)" },
  { value: "aluminum", label: "알루미늄(AL)" },
  { value: "acrylic", label: "아크릴" },
];

function formatWon(n: number) {
  return new Intl.NumberFormat("ko-KR").format(Math.round(n));
}

export default function Page() {
  const [file, setFile] = useState<File | null>(null);
  const [material, setMaterial] = useState("steel");
  const [thickness, setThickness] = useState<number>(0); // 0=auto
  const [qty, setQty] = useState<number>(1);

  const [jobId, setJobId] = useState<string | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [vendorId, setVendorId] = useState<string | null>(null);

  const [busy, setBusy] = useState(false);
  const [log, setLog] = useState<any>({});

  const pollTimer = useRef<number | null>(null);

  const svgUrl = useMemo(() => (jobId ? previewSvgUrl(jobId) : null), [jobId]);
  const dxfUrl = useMemo(() => (jobId ? downloadDxfUrl(jobId) : null), [jobId]);

  function pushLog(title: string, data: any) {
    setLog((prev: any) => ({ ...prev, [new Date().toISOString()]: { title, data } }));
  }

  async function refreshJob(id: string) {
    const j = await getJob(id);
    setJob(j);
    return j as Job;
  }

  function stopPoll() {
    if (pollTimer.current) window.clearInterval(pollTimer.current);
    pollTimer.current = null;
  }

  function startPoll(id: string) {
    stopPoll();
    pollTimer.current = window.setInterval(async () => {
      try {
        const j = await refreshJob(id);
        if (j.status === "DONE" || j.status === "FAILED") stopPoll();
      } catch {
        // ignore
      }
    }, 1500);
  }

  useEffect(() => {
    return () => stopPoll();
  }, []);

  async function onCreateJob() {
    setBusy(true);
    try {
      const r = await createJob({ material, thickness_mm: thickness, qty });
      setJobId(r.id);
      pushLog("createJob", r);
      await refreshJob(r.id);
    } finally {
      setBusy(false);
    }
  }

  async function onUpload() {
    if (!jobId) return alert("먼저 Job을 생성하세요");
    if (!file) return alert("STEP 파일을 선택하세요");
    setBusy(true);
    try {
      const r = await uploadStep(jobId, file);
      pushLog("uploadStep", r);
      await refreshJob(jobId);
    } finally {
      setBusy(false);
    }
  }

  async function onQuote() {
    if (!jobId) return alert("먼저 Job을 생성하세요");
    setBusy(true);
    try {
      const r = await quote(jobId);
      pushLog("quote", r);
      await refreshJob(jobId);
    } finally {
      setBusy(false);
    }
  }

  async function onStart() {
    if (!jobId) return alert("먼저 Job을 생성하세요");
    setBusy(true);
    try {
      const r = await start(jobId);
      pushLog("start", r);
      startPoll(jobId);
    } finally {
      setBusy(false);
    }
  }

  async function onSeedVendor() {
    setBusy(true);
    try {
      const r = await seedVendor();
      // 구현마다 키가 다를 수 있어서 방어적으로
      const id = r.vendor_id ?? r.id ?? r.vendor?.id;
      if (!id) throw new Error("vendor id not found in response");
      setVendorId(String(id));
      pushLog("seedVendor", r);
    } finally {
      setBusy(false);
    }
  }

  async function onDispatch() {
    if (!jobId) return alert("jobId가 없습니다");
    if (!vendorId) return alert("먼저 seedVendor로 vendorId를 만든 뒤 dispatch하세요");
    setBusy(true);
    try {
      const r = await dispatch(jobId, vendorId);
      pushLog("dispatch", r);
      await refreshJob(jobId);
    } finally {
      setBusy(false);
    }
  }

  const unitWon =
    (job?.quote?.unit_won as number | undefined) ??
    (job as any)?.estimate?.unit_won ??
    0;
  const totalWon =
    (job?.quote?.total_won as number | undefined) ??
    (job as any)?.estimate?.total_won ??
    0;

  return (
    <main className="mx-auto max-w-5xl p-6">
      <div className="rounded-2xl bg-white shadow-sm border p-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold">STEP → Laser DXF Converter (QA)</h1>
            <p className="text-sm text-zinc-500 mt-1">
              백엔드 API 검증용 최소 화면. 고객용 UI는 별도 웹에서 개발.
            </p>
            <p className="text-xs text-zinc-400 mt-1">
              API: <span className="font-mono">{API_BASE}</span>
            </p>
          </div>

          <div className="text-right">
            <div className="text-xs text-zinc-500">Job</div>
            <div className="font-mono text-sm">{jobId ?? "-"}</div>
            <div className="mt-1 inline-flex items-center rounded-full px-2 py-1 text-xs border">
              상태: <span className="ml-1 font-semibold">{job?.status ?? "-"}</span>
            </div>
          </div>
        </div>

        <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-4">
          <section className="rounded-xl border p-4">
            <div className="font-semibold">1) Job 생성</div>

            <div className="mt-3 grid gap-2 text-sm">
              <label className="text-zinc-600">재질</label>
              <select
                className="h-10 rounded-lg border px-3"
                value={material}
                onChange={(e) => setMaterial(e.target.value)}
              >
                {MATERIALS.map((m) => (
                  <option key={m.value} value={m.value}>
                    {m.label}
                  </option>
                ))}
              </select>

              <label className="text-zinc-600">두께(mm) (0=자동)</label>
              <input
                className="h-10 rounded-lg border px-3"
                type="number"
                value={thickness}
                min={0}
                step={0.1}
                onChange={(e) => setThickness(Number(e.target.value))}
              />

              <label className="text-zinc-600">수량</label>
              <input
                className="h-10 rounded-lg border px-3"
                type="number"
                value={qty}
                min={1}
                onChange={(e) => setQty(Number(e.target.value))}
              />

              <button
                className="mt-2 h-10 rounded-lg bg-black text-white disabled:opacity-50"
                onClick={onCreateJob}
                disabled={busy}
              >
                Job 생성
              </button>
            </div>
          </section>

          <section className="rounded-xl border p-4">
            <div className="font-semibold">2) 업로드 / 견적 / 변환</div>

            <div className="mt-3 grid gap-2 text-sm">
              <label className="text-zinc-600">STEP 파일</label>
              <input
                type="file"
                accept=".step,.stp"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              />

              <div className="grid grid-cols-2 gap-2 mt-2">
                <button
                  className="h-10 rounded-lg border disabled:opacity-50"
                  onClick={onUpload}
                  disabled={busy || !jobId || !file}
                >
                  업로드
                </button>
                <button
                  className="h-10 rounded-lg border disabled:opacity-50"
                  onClick={onQuote}
                  disabled={busy || !jobId}
                >
                  견적
                </button>
              </div>

              <button
                className="mt-1 h-10 rounded-lg bg-black text-white disabled:opacity-50"
                onClick={onStart}
                disabled={busy || !jobId}
              >
                변환 시작(폴링)
              </button>

              <div className="mt-2 rounded-lg bg-zinc-50 p-3 border">
                <div className="text-xs text-zinc-500">견적</div>
                <div className="mt-1 grid grid-cols-2 gap-3">
                  <div>
                    <div className="text-xs text-zinc-500">단가</div>
                    <div className="text-lg font-bold">
                      {unitWon ? `${formatWon(unitWon)} 원` : "-"}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-zinc-500">총액</div>
                    <div className="text-lg font-bold">
                      {totalWon ? `${formatWon(totalWon)} 원` : "-"}
                    </div>
                  </div>
                </div>
              </div>

              <div className="mt-2 grid grid-cols-2 gap-2">
                <a
                  className={`h-10 rounded-lg border flex items-center justify-center ${
                    !svgUrl ? "pointer-events-none opacity-50" : ""
                  }`}
                  href={svgUrl ?? "#"}
                  target="_blank"
                  rel="noreferrer"
                >
                  SVG 열기
                </a>

                <a
                  className={`h-10 rounded-lg bg-black text-white flex items-center justify-center ${
                    !dxfUrl ? "pointer-events-none opacity-50" : ""
                  }`}
                  href={dxfUrl ?? "#"}
                >
                  DXF 다운로드
                </a>
              </div>
            </div>
          </section>

          <section className="rounded-xl border p-4">
            <div className="font-semibold">3) 업체 전달(Dispatch)</div>

            <div className="mt-3 grid gap-2 text-sm">
              <button
                className="h-10 rounded-lg border disabled:opacity-50"
                onClick={onSeedVendor}
                disabled={busy}
              >
                Seed Vendor 생성
              </button>

              <label className="text-zinc-600">vendorId</label>
              <input
                className="h-10 rounded-lg border px-3 font-mono"
                value={vendorId ?? ""}
                onChange={(e) => setVendorId(e.target.value)}
                placeholder="seedVendor로 자동 생성됨"
              />

              <button
                className="h-10 rounded-lg bg-black text-white disabled:opacity-50"
                onClick={onDispatch}
                disabled={busy || !jobId || !vendorId}
              >
                Dispatch 실행
              </button>

              <div className="text-xs text-zinc-500">
                * 현재 MVP는 실제 이메일/FTP 전송 대신 서버 로그에 출력될 수 있어요.
              </div>
            </div>
          </section>
        </div>

        <section className="mt-6 rounded-xl border p-4">
          <div className="flex items-center justify-between">
            <div className="font-semibold">상세 로그(JSON)</div>
            <button
              className="text-sm underline text-zinc-600"
              onClick={() => setLog({})}
            >
              지우기
            </button>
          </div>
          <pre className="mt-3 rounded-lg bg-black text-zinc-200 p-3 overflow-auto text-xs">
            {JSON.stringify({ job, log }, null, 2)}
          </pre>
        </section>
      </div>
    </main>
  );
}
