"use client";

import { useState } from "react";
import { BYPASS_PAYMENT, createCheckoutAndRedirect } from "@/lib/payment";

type Props = {
  onProceed: () => Promise<void> | void;
  jobId?: string;
  amount?: number;
  label?: string;
};

export default function ProceedWithOrWithoutPayment({
  onProceed,
  jobId,
  amount,
  label = "다음 단계 진행",
}: Props) {
  const [loading, setLoading] = useState(false);

  async function handleClick() {
    if (loading) return;
    setLoading(true);

    try {
      // ✅ 결제 우회 ON이면 바로 다음 단계 실행
      if (BYPASS_PAYMENT) {
        await onProceed();
        return;
      }

      // 결제 우회 OFF(운영)일 때만 결제 진행
      if (!jobId || typeof amount !== "number") {
        throw new Error("결제에 필요한 jobId/amount가 없습니다.");
      }

      await createCheckoutAndRedirect({ jobId, amount });
    } finally {
      setLoading(false);
    }
  }

  return (
    <button
      onClick={handleClick}
      disabled={loading}
      style={{
        width: "100%",
        padding: "12px 14px",
        borderRadius: 10,
        border: "1px solid #ddd",
        background: loading ? "#f4f4f4" : "#fff",
        cursor: loading ? "not-allowed" : "pointer",
        fontWeight: 700,
      }}
    >
      {loading
        ? "처리 중..."
        : BYPASS_PAYMENT
        ? `${label} (결제 우회)`
        : `${label} (결제 필요)`}
    </button>
  );
}
