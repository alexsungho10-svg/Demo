// web/lib/types.ts
export type JobStatus =
  | "CREATED"
  | "UPLOADED"
  | "QUOTED"
  | "PROCESSING"
  | "DONE"
  | "FAILED";

export type Job = {
  id: string;
  status: JobStatus;
  material?: string;
  thickness_mm?: number;
  qty?: number;
  // 백엔드 구현에 따라 필드명이 다를 수 있어 optional로 둠
  quote?: {
    unit_won?: number;
    total_won?: number;
  };
  metrics?: any;
  validation?: any;
  error?: string | null;
};
