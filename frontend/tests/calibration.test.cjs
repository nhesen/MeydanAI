const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const ts = require("typescript");
const exportsObject = {};
const source = fs.readFileSync(path.join(__dirname, "../src/lib/calibration.ts"), "utf8");
new Function("exports", ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText)(exportsObject);
const { calibrationError, RELATIVE_CALIBRATION } = exportsObject;
const manual = { mode: "manual", pitch_mode: "hali_saha", camera_mode: "fixed", length_m: 44, width_m: 23, points: [[0.1, 0.9], [0.9, 0.9], [0.8, 0.1], [0.2, 0.1]] };

test("relative mode is the default and never supplies guessed corners", () => {
  assert.equal(RELATIVE_CALIBRATION.mode, "relative");
  assert.deepEqual(RELATIVE_CALIBRATION.points, []);
  assert.equal(calibrationError(RELATIVE_CALIBRATION), null);
});
test("a visible convex pitch with measured dimensions can be calibrated", () => assert.equal(calibrationError(manual), null));
test("manual calibration requires every corner", () => assert.match(calibrationError({ ...manual, points: manual.points.slice(0, 3) }), /four/));
test("crossed corners are rejected", () => assert.match(calibrationError({ ...manual, points: [manual.points[0], manual.points[2], manual.points[1], manual.points[3]] }), /crossing/));
test("negligible pitch areas are rejected", () => assert.match(calibrationError({ ...manual, points: [[0.1, 0.1], [0.11, 0.1], [0.11, 0.11], [0.1, 0.11]] }), /too small/));
test("manual calibration rejects moving cameras", () => assert.match(calibrationError({ ...manual, camera_mode: "broadcast" }), /fixed/));
test("calibration requires real positive finite dimensions", () => {
  for (const length_m of [0, NaN, Infinity, 131]) assert.match(calibrationError({ ...manual, length_m }), /actual pitch length/);
});
test("corners outside the frame are rejected", () => assert.match(calibrationError({ ...manual, points: [[-0.1, 0.9], ...manual.points.slice(1)] }), /inside/));
test("automatic keypoints are restricted to the trained 11-a-side template", () => {
  assert.match(calibrationError({ ...manual, mode: "automatic", points: [] }), /11-a-side/);
  assert.match(calibrationError({ ...manual, mode: "automatic", pitch_mode: "11v11", points: [] }), /90–120/);
  assert.equal(calibrationError({ ...manual, mode: "automatic", pitch_mode: "11v11", length_m: 105, width_m: 68, points: [] }), null);
});
