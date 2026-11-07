// Search API for the research maps: GET/POST /functions/v1/search?unit=uwb-stem&q=...
// Embeds the query with Supabase's built-in gte-small model (the pipeline embeds
// records with the same model, thenlper/gte-small) and calls the search_people
// SQL function (record-level hybrid search, see migrations). Public, read-only.
import { createClient } from "jsr:@supabase/supabase-js@2";

const session = new Supabase.ai.Session("gte-small");
const supabase = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_ANON_KEY")!);

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: CORS });
  const url = new URL(req.url);
  const body = req.method === "POST" ? await req.json().catch(() => ({})) : {};
  const unit = String(body.unit ?? url.searchParams.get("unit") ?? "");
  const q = String(body.q ?? url.searchParams.get("q") ?? "").slice(0, 2000);
  const limit = Math.min(Number(body.limit ?? url.searchParams.get("limit") ?? 20), 50);
  const meaning = (body.meaning ?? url.searchParams.get("meaning") ?? "1") !== "0";
  if (!unit || !q.trim()) {
    return Response.json({ error: "unit and q are required" }, { status: 400, headers: CORS });
  }
  const qvec = meaning ? await session.run(q, { mean_pool: true, normalize: true }) : null;
  const { data, error } = await supabase.rpc("search_people", {
    p_unit: unit,
    p_query: q,
    p_qvec: qvec ? JSON.stringify(qvec) : null,
    p_alpha: 0.5,
    p_limit: limit,
    p_use_listed: true,
  });
  if (error) return Response.json({ error: error.message }, { status: 500, headers: CORS });
  return Response.json({ unit, q, meaning, results: data }, {
    headers: { ...CORS, "Cache-Control": "public, max-age=300" },
  });
});
