import postgres from "postgres";

let sql: ReturnType<typeof postgres> | null = null;

export function getSql() {
  if (!sql) {
    const url = process.env.DATABASE_URL;
    if (!url) {
      throw new Error("DATABASE_URL is required");
    }
    sql = postgres(url, { prepare: false, max: 10 });
  }
  return sql;
}

export function getTenantId() {
  return process.env.DEFAULT_TENANT_ID ?? "00000000-0000-4000-8000-000000000001";
}

export function vectorLiteral(values: number[]) {
  return `[${values.map((v) => Number(v).toFixed(8)).join(",")}]`;
}
