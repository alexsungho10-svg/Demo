// web/app/api/checkout/route.ts
import { NextResponse } from "next/server";

export async function POST(req: Request) {
  const body = await req.json().catch(() => ({}));

  return NextResponse.json(
    {
      error: "checkout_not_configured",
      message:
        "결제 기능이 아직 연결되지 않았습니다. 테스트는 NEXT_PUBLIC_BYPASS_PAYMENT=1로 진행하세요.",
      received: body,
    },
    { status: 501 }
  );
}
