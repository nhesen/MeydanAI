const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const ts = require("typescript");

// Exercise the production upload client without a server or real credentials.
const source = fs.readFileSync(path.join(__dirname, "../src/services/api-client.ts"), "utf8");
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText;
const exportsObject = {};
new Function("exports", "require", compiled)(exportsObject, (id) => {
  if (id === "@/lib/env") return { getApiBaseUrl: () => "http://api.test" };
  if (id === "@/lib/session") return { getSessionToken: () => "test-session", setSessionToken: () => {} };
  throw new Error(`Unexpected dependency: ${id}`);
});
const { api, ApiError } = exportsObject;

class FakeXMLHttpRequest {
  static instances = [];
  upload = {};
  headers = {};
  constructor() { FakeXMLHttpRequest.instances.push(this); }
  open(method, url) { this.method = method; this.url = url; }
  setRequestHeader(name, value) { this.headers[name] = value; }
  send(body) { this.body = body; }
  abort() { this.onabort?.(); }
  respond(status, body) {
    this.status = status;
    this.responseText = typeof body === "string" ? body : JSON.stringify(body);
    this.onload();
  }
}
global.XMLHttpRequest = FakeXMLHttpRequest;
const video = new File(["test-video"], "match.mp4", { type: "video/mp4" });
const latestRequest = () => FakeXMLHttpRequest.instances.at(-1);

test("video uploads preserve authorization, video data, and real byte progress", async () => {
  const progress = [];
  const result = api.createProcessingJob("match-1", "organizer-test", video, {
    onProgress: (value) => progress.push(value),
  });
  const request = latestRequest();
  assert.equal(request.method, "POST");
  assert.equal(request.url, "http://api.test/api/v1/matches/match-1/processing-jobs");
  assert.equal(request.headers.authorization, "Bearer test-session");
  assert.equal(request.headers["x-organizer-token"], "organizer-test");
  assert.equal(request.headers["content-type"], undefined, "browser must generate the multipart boundary");
  assert.equal(request.body.get("video").name, "match.mp4");
  request.upload.onprogress({ lengthComputable: true, loaded: 25, total: 100 });
  request.upload.onprogress({ lengthComputable: false, loaded: 50, total: 0 });
  request.upload.onprogress({ lengthComputable: true, loaded: 100, total: 100 });
  const payload = { data: { id: "job-1", status: "queued" } };
  request.respond(202, payload);
  assert.deepEqual(await result, payload);
  assert.deepEqual(progress, [25, 100]);
});

test("upload reports structured server problems", async () => {
  const result = api.createProcessingJob("match-1", null, video);
  latestRequest().respond(413, { detail: "Video too large", errorCode: "VIDEO_TOO_LARGE" });
  await assert.rejects(result, (error) => error instanceof ApiError && error.status === 413 && error.problem.errorCode === "VIDEO_TOO_LARGE");
});

test("upload keeps HTTP status when a proxy returns HTML", async () => {
  const result = api.createProcessingJob("match-1", null, video);
  latestRequest().respond(413, "<html>Request entity too large</html>");
  await assert.rejects(result, (error) => error instanceof ApiError && error.status === 413);
});

test("upload rejects broken connections", async () => {
  const result = api.createProcessingJob("match-1", null, video);
  latestRequest().onerror();
  await assert.rejects(result, TypeError);
});

test("upload cancellation aborts the request", async () => {
  const controller = new AbortController();
  const result = api.createProcessingJob("match-1", null, video, { signal: controller.signal });
  controller.abort();
  await assert.rejects(result, { name: "AbortError" });
});

test("already cancelled uploads never send video data", async () => {
  const controller = new AbortController();
  controller.abort();
  const result = api.createProcessingJob("match-1", null, video, { signal: controller.signal });
  await assert.rejects(result, { name: "AbortError" });
  assert.equal(latestRequest().body, undefined);
});

test("a malformed success response is not treated as an accepted job", async () => {
  const result = api.createProcessingJob("match-1", null, video);
  latestRequest().respond(202, "<html>Unavailable</html>");
  await assert.rejects(result, /invalid response/);
});

test("video upload submits exact calibration geometry alongside the video", async () => {
  const calibration = { mode: "manual", pitch_mode: "hali_saha", camera_mode: "fixed", length_m: 44, width_m: 23, points: [[0.1, 0.9], [0.9, 0.9], [0.8, 0.1], [0.2, 0.1]] };
  const result = api.createProcessingJob("match-1", null, video, { calibration });
  assert.deepEqual(JSON.parse(latestRequest().body.get("calibration")), calibration);
  latestRequest().respond(202, { data: { id: "calibrated-job" } });
  assert.equal((await result).data.id, "calibrated-job");
});

test("identity review sends explicit player and team with organizer authorization", async () => {
  const originalFetch = global.fetch;
  global.fetch = async (url, init) => {
    assert.equal(url, "http://api.test/api/v1/matches/match-1/track-mappings/mapping-1/review");
    assert.equal(init.method, "PATCH");
    assert.equal(init.headers.get("X-Organizer-Token"), "organizer-test");
    assert.deepEqual(JSON.parse(init.body), { player_id: "player-2", team_id: "team-1" });
    return new Response(JSON.stringify({ data: { mappings: [] } }), { headers: { "Content-Type": "application/json" } });
  };
  try { assert.deepEqual((await api.reviewTrackMapping("match-1", "mapping-1", "organizer-test", "player-2", "team-1")).data.mappings, []); }
  finally { global.fetch = originalFetch; }
});

test("event rejection uses the review endpoint without mutating the match score", async () => {
  const originalFetch = global.fetch;
  global.fetch = async (url, init) => {
    assert.equal(url, "http://api.test/api/v1/matches/match-1/events/event-1/review");
    assert.deepEqual(JSON.parse(init.body), { status: "rejected" });
    return new Response(JSON.stringify({ data: { events: [] } }));
  };
  try { await api.reviewAnalysisEvent("match-1", "event-1", null, "rejected"); }
  finally { global.fetch = originalFetch; }
});
