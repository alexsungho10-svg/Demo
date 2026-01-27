// web/lib/payment.ts
export const BYPASS_PAYMENT =
  process.env.NEXT_PUBLIC_BYPASS_PAYMENT === "1";

/**
 * 결제 붙일 때만 쓰는 함수.
 * 지금은 BYPASS_PAYMENT=1이면 절대 호출되지 않게 UI에서 막을 것.
 */
export async function createCheckoutAndRedirect(opts: {
  jobId: string;
  amount: number;
  successUrl?: string;
  cancelUrl?: string;
}) {
  const r = await fetch("/api/checkout", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(opts),
  });

  if (!r.ok) {
    const txt = await r.text().catch(() => "");
    throw new Error(`checkout failed: ${r.status} ${txt}`);
  }

  const data = (await r.json()) as { url?: string };
  if (!data.url) throw new Error("checkout url missing");

  window.location.href = data.url;
}
