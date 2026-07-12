// Deterministic tests for the Realtime function-call parser.
// Run with: node test_function_calls.js
// Exits non-zero on any assertion failure.

"use strict";

const { createParser, safeParseArgs, normalizeToolName } = require("./parser.js");

let passed = 0;
let failed = 0;
const failures = [];

function assert(cond, msg) {
  if (cond) { passed += 1; return; }
  failed += 1;
  failures.push(msg);
  console.error("  ✗ " + msg);
}

function assertEq(actual, expected, msg) {
  const a = JSON.stringify(actual);
  const e = JSON.stringify(expected);
  if (a === e) { passed += 1; return; }
  failed += 1;
  failures.push(msg + " — expected " + e + " got " + a);
  console.error("  ✗ " + msg + " — expected " + e + " got " + a);
}

async function waitForSend(p, timeoutMs) {
  // Flush microtasks queued by dispatch so the recorded outputs are settled.
  const deadline = Date.now() + (timeoutMs || 50);
  while (p.pending && Date.now() < deadline) {
    await new Promise((r) => setImmediate(r));
  }
}

function buildParser(overrides) {
  const sent = [];
  const opts = Object.assign({
    sendOutput: (callId, payload) => { sent.push({ callId: callId, payload: payload }); },
    log: () => {},
    onMissingCallId: () => {},
    onMissingName: () => {},
    onMalformedArgs: () => {},
    onDispatched: () => {},
  }, overrides || {});
  opts.sendOutput = (callId, payload) => { sent.push({ callId: callId, payload: payload }); };
  const parser = createParser(opts);
  parser.sent = sent;
  parser.pending = 0;
  const baseSend = opts.sendOutput;
  // Wrap sendOutput so pending count is tracked.
  parser._origSend = baseSend;
  return parser;
}

async function run(name, fn) {
  console.log("\n# " + name);
  await fn();
}

(async function main() {
  // ----------------------------------------------------------
  await run("safeParseArgs rejects null / array / primitive JSON", async () => {
    assertEq(safeParseArgs({ question: "hi" }), { question: "hi" }, "object passthrough");
    assertEq(safeParseArgs("{\"q\":1}"), { q: 1 }, "string JSON object parses");
    assertEq(safeParseArgs(""), {}, "empty string => {}");
    assertEq(safeParseArgs(null), {}, "null => {}");
    assertEq(safeParseArgs(undefined), {}, "undefined => {}");
    try { safeParseArgs("null"); assert(false, "should reject JSON null"); }
    catch (e) { assertEq(e.code, "MALFORMED_ARGS", "JSON null throws MALFORMED_ARGS"); }
    try { safeParseArgs("\"hi\""); assert(false, "should reject JSON string"); }
    catch (e) { assertEq(e.code, "MALFORMED_ARGS", "JSON string throws MALFORMED_ARGS"); }
    try { safeParseArgs("[1,2]"); assert(false, "should reject JSON array"); }
    catch (e) { assertEq(e.code, "MALFORMED_ARGS", "JSON array throws MALFORMED_ARGS"); }
    try { safeParseArgs("{not json"); assert(false, "should reject malformed JSON"); }
    catch (e) { assertEq(e.code, "MALFORMED_ARGS", "malformed JSON throws MALFORMED_ARGS"); }
    try { safeParseArgs([]); assert(false, "should reject array object"); }
    catch (e) { assertEq(e.code, "MALFORMED_ARGS", "array object throws MALFORMED_ARGS"); }
  });

  // ----------------------------------------------------------
  await run("normalizeToolName accepts aliases for ask_starchild", async () => {
    assertEq(normalizeToolName("ask_starchild"), "ask_starchild", "snake_case passthrough");
    assertEq(normalizeToolName("askStarchild"), "ask_starchild", "camelCase alias");
    assertEq(normalizeToolName("AskStarchild"), "ask_starchild", "PascalCase alias");
    assertEq(normalizeToolName("ASK_STARCHILD"), "ask_starchild", "UPPER_SNAKE alias");
    assertEq(normalizeToolName("  ask_starchild  "), "ask_starchild", "trims whitespace");
    assertEq(normalizeToolName("other_tool"), "other_tool", "other tools passthrough");
    assertEq(normalizeToolName(null), null, "null returns null");
    assertEq(normalizeToolName(""), null, "empty string returns null");
  });

  // ----------------------------------------------------------
  await run("output_item.added + arguments.done split events dispatch once", async () => {
    const parser = buildParser({
      onBridgeCall: async () => "bridge-ok",
    });
    parser.handleEvent({
      type: "response.output_item.added",
      response_id: "resp_1",
      output_index: 0,
      item: {
        type: "function_call",
        id: "fc_001",
        item_id: "fc_001",
        call_id: "call_001",
        name: "ask_starchild",
      },
    });
    // arguments arrive as a separate event with the same item_id
    const p1 = parser.handleEvent({
      type: "response.function_call_arguments.done",
      response_id: "resp_1",
      item_id: "fc_001",
      output_index: 0,
      call_id: "call_001",
      arguments: '{"question":"hello"}',
    });
    await waitForSend(p1);
    assertEq(parser.sent.length, 1, "exactly one function_call_output sent");
    assertEq(parser.sent[0].callId, "call_001", "sent to correct call_id");
    assertEq(parser.sent[0].payload, "bridge-ok", "bridge result forwarded");
    // A duplicate arguments.done event should not dispatch again.
    const p2 = parser.handleEvent({
      type: "response.function_call_arguments.done",
      response_id: "resp_1",
      item_id: "fc_001",
      output_index: 0,
      call_id: "call_001",
      arguments: '{"question":"hello again"}',
    });
    await waitForSend(p2);
    assertEq(parser.sent.length, 1, "duplicate arguments.done is deduped");
    // A trailing output_item.done should also not dispatch again.
    const p3 = parser.handleEvent({
      type: "response.output_item.done",
      response_id: "resp_1",
      output_index: 0,
      item: {
        type: "function_call",
        id: "fc_001",
        item_id: "fc_001",
        call_id: "call_001",
        name: "ask_starchild",
        arguments: '{"question":"hello"}',
      },
    });
    await waitForSend(p3);
    assertEq(parser.sent.length, 1, "trailing output_item.done is deduped");
  });

  // ----------------------------------------------------------
  await run("output_item.done complete event dispatches once", async () => {
    const parser = buildParser({
      onBridgeCall: async () => "complete-ok",
    });
    // No output_item.added event at all — output_item.done carries everything.
    const p = parser.handleEvent({
      type: "response.output_item.done",
      response_id: "resp_2",
      output_index: 1,
      item: {
        type: "function_call",
        id: "fc_010",
        item_id: "fc_010",
        call_id: "call_010",
        name: "ask_starchild",
        arguments: '{"question":"ping"}',
      },
    });
    await waitForSend(p);
    assertEq(parser.sent.length, 1, "complete output_item.done dispatched once");
    assertEq(parser.sent[0].callId, "call_010", "correct call_id");
    assertEq(parser.sent[0].payload, "complete-ok", "bridge result forwarded");
  });

  // ----------------------------------------------------------
  await run("response.done fallback dispatches when earlier events are missing", async () => {
    const parser = buildParser({
      onBridgeCall: async ({ args }) => "fallback:" + (args.question || ""),
    });
    // No prior output_item.added or arguments.done events.
    const p = parser.handleEvent({
      type: "response.done",
      response: {
        id: "resp_3",
        status: "completed",
        output: [
          { type: "message", role: "assistant", content: [] }, // should be skipped
          {
            type: "function_call",
            id: "fc_020",
            item_id: "fc_020",
            output_index: 0,
            call_id: "call_020",
            name: "ask_starchild",
            arguments: '{"question":"fallback ping"}',
          },
        ],
      },
    });
    await waitForSend(p);
    assertEq(parser.sent.length, 1, "fallback dispatched exactly once");
    assertEq(parser.sent[0].callId, "call_020", "fallback call_id correct");
    assertEq(parser.sent[0].payload, "fallback:fallback ping", "fallback args forwarded");
  });

  // ----------------------------------------------------------
  await run("askStarchild alias is normalized and dispatched", async () => {
    let received = null;
    const parser = buildParser({
      onBridgeCall: async (req) => { received = req; return "alias-ok"; },
    });
    parser.handleEvent({
      type: "response.output_item.added",
      item: {
        type: "function_call", id: "fc_030", item_id: "fc_030",
        call_id: "call_030", name: "askStarchild",
      },
    });
    const p = parser.handleEvent({
      type: "response.function_call_arguments.done",
      item_id: "fc_030", call_id: "call_030",
      arguments: '{"question":"alias?"}',
    });
    await waitForSend(p);
    assertEq(parser.sent.length, 1, "alias dispatch sent once");
    assertEq(received && received.name, "ask_starchild", "aliased name normalized to canonical tool name");
    assertEq(received && received.args && received.args.question, "alias?", "args forwarded correctly");
    assertEq(parser.sent[0].payload, "alias-ok", "alias path resolved correctly");
  });

  // ----------------------------------------------------------
  await run("malformed args produces error output and does not call bridge", async () => {
    let bridgeCalls = 0;
    const parser = buildParser({
      onBridgeCall: async () => { bridgeCalls += 1; return "should-not-reach"; },
    });
    parser.handleEvent({
      type: "response.output_item.added",
      item: { type: "function_call", id: "fc_040", item_id: "fc_040",
        call_id: "call_040", name: "ask_starchild" },
    });
    const p = parser.handleEvent({
      type: "response.function_call_arguments.done",
      item_id: "fc_040", call_id: "call_040",
      arguments: '{"question": ', // malformed JSON
    });
    await waitForSend(p);
    assertEq(parser.sent.length, 1, "one output sent for malformed args");
    const out = parser.sent[0].payload;
    assertEq(out && out.ok, false, "output.ok is false");
    assertEq(out && out.error, "malformed_arguments", "output.error is malformed_arguments");
    assertEq(typeof (out && out.raw_arguments), "string", "raw_arguments preserved");
    assertEq(bridgeCalls, 0, "bridge was NOT called for malformed args");
  });

  // ----------------------------------------------------------
  await run("JSON null / array args also treated as malformed", async () => {
    const cases = [
      { label: "JSON null", args: "null" },
      { label: "JSON array", args: "[1,2,3]" },
      { label: "JSON string", args: '"oops"' },
    ];
    for (const c of cases) {
      const parser = buildParser();
      parser.handleEvent({
        type: "response.output_item.added",
        item: { type: "function_call", id: "fc_" + c.label, item_id: "fc_" + c.label,
          call_id: "call_" + c.label, name: "ask_starchild" },
      });
      const p = parser.handleEvent({
        type: "response.function_call_arguments.done",
        item_id: "fc_" + c.label, call_id: "call_" + c.label,
        arguments: c.args,
      });
      await waitForSend(p);
      assertEq(parser.sent.length, 1, c.label + ": exactly one error output sent");
      assertEq(parser.sent[0].payload && parser.sent[0].payload.error,
        "malformed_arguments", c.label + ": error code is malformed_arguments");
    }
  });

  // ----------------------------------------------------------
  await run("duplicate events (added+args+done+done.fallback) dispatch only once", async () => {
    let bridgeCalls = 0;
    const parser = buildParser({
      onBridgeCall: async () => { bridgeCalls += 1; return "x"; },
    });
    // Event 1: added (no args)
    parser.handleEvent({
      type: "response.output_item.added",
      item: { type: "function_call", id: "fc_050", item_id: "fc_050",
        call_id: "call_050", name: "ask_starchild" },
    });
    // Event 2: arguments.done
    const p1 = parser.handleEvent({
      type: "response.function_call_arguments.done",
      item_id: "fc_050", call_id: "call_050",
      arguments: '{"question":"dup"}',
    });
    await waitForSend(p1);
    assertEq(bridgeCalls, 1, "bridge called once after arguments.done");
    // Event 3: output_item.done (duplicate)
    const p2 = parser.handleEvent({
      type: "response.output_item.done",
      item: { type: "function_call", id: "fc_050", item_id: "fc_050",
        call_id: "call_050", name: "ask_starchild",
        arguments: '{"question":"dup"}' },
    });
    await waitForSend(p2);
    assertEq(bridgeCalls, 1, "bridge NOT called again on output_item.done duplicate");
    // Event 4: response.done fallback (also duplicate)
    const p3 = parser.handleEvent({
      type: "response.done",
      response: { output: [
        { type: "function_call", id: "fc_050", item_id: "fc_050",
          output_index: 0, call_id: "call_050", name: "ask_starchild",
          arguments: '{"question":"dup"}' },
      ] },
    });
    await waitForSend(p3);
    assertEq(bridgeCalls, 1, "bridge NOT called again on response.done fallback");
    assertEq(parser.sent.length, 1, "exactly one function_call_output sent total");
  });

  // ----------------------------------------------------------
  await run("missing question in args returns structured missing_question error", async () => {
    let bridgeCalls = 0;
    const parser = buildParser({
      onBridgeCall: async () => { bridgeCalls += 1; return "should-not-reach"; },
    });
    parser.handleEvent({
      type: "response.output_item.added",
      item: { type: "function_call", id: "fc_060", item_id: "fc_060",
        call_id: "call_060", name: "ask_starchild" },
    });
    const p = parser.handleEvent({
      type: "response.function_call_arguments.done",
      item_id: "fc_060", call_id: "call_060",
      arguments: '{"other":"value"}',
    });
    await waitForSend(p);
    assertEq(bridgeCalls, 0, "bridge NOT called when question missing");
    assertEq(parser.sent.length, 1, "one error output sent");
    const out = parser.sent[0].payload;
    assertEq(out && out.error, "missing_question", "error code is missing_question");
  });

  // ----------------------------------------------------------
  await run("unknown tool name returns 'unknown tool' string", async () => {
    const parser = buildParser({
      onBridgeCall: async () => "should-not-reach",
    });
    parser.handleEvent({
      type: "response.output_item.added",
      item: { type: "function_call", id: "fc_070", item_id: "fc_070",
        call_id: "call_070", name: "some_other_tool" },
    });
    const p = parser.handleEvent({
      type: "response.function_call_arguments.done",
      item_id: "fc_070", call_id: "call_070",
      arguments: '{"foo":"bar"}',
    });
    await waitForSend(p);
    assertEq(parser.sent.length, 1, "one output sent for unknown tool");
    assertEq(parser.sent[0].payload, "unknown tool: some_other_tool",
      "payload identifies unknown tool");
  });

  // ----------------------------------------------------------
  await run("missing call_id logs and skips without sending output", async () => {
    let missingEvents = 0;
    const parser = buildParser({
      onBridgeCall: async () => "should-not-reach",
      onMissingCallId: () => { missingEvents += 1; },
    });
    const p = parser.handleEvent({
      type: "response.function_call_arguments.done",
      item_id: "fc_080", call_id: null,
      name: "ask_starchild",
      arguments: '{"question":"x"}',
    });
    await waitForSend(p);
    assertEq(parser.sent.length, 0, "no output sent when call_id missing");
    assert(missingEvents >= 1, "onMissingCallId fired");
  });

  // ----------------------------------------------------------
  await run("output_item.added without name does not block later resolution via arguments.done", async () => {
    const parser = buildParser({
      onBridgeCall: async ({ args }) => "ok:" + args.question,
    });
    // added event omits the name (some Realtime versions do this)
    parser.handleEvent({
      type: "response.output_item.added",
      item: { type: "function_call", id: "fc_090", item_id: "fc_090",
        call_id: "call_090" /* no name */ },
    });
    const p = parser.handleEvent({
      type: "response.function_call_arguments.done",
      item_id: "fc_090", call_id: "call_090",
      name: "ask_starchild",
      arguments: '{"question":"late name"}',
    });
    await waitForSend(p);
    assertEq(parser.sent.length, 1, "dispatched after name back-fill");
    assertEq(parser.sent[0].payload, "ok:late name", "args forwarded after late name");
  });

  // ----------------------------------------------------------
  await run("arguments.done without prior output_item.added still resolves via item_id", async () => {
    const parser = buildParser({
      onBridgeCall: async ({ args }) => "ok:" + args.question,
    });
    const p = parser.handleEvent({
      type: "response.function_call_arguments.done",
      item_id: "fc_100", call_id: "call_100",
      name: "ask_starchild",
      arguments: '{"question":"no added"}',
    });
    await waitForSend(p);
    assertEq(parser.sent.length, 1, "dispatched without prior added event");
    assertEq(parser.sent[0].payload, "ok:no added", "args forwarded");
  });

  // ----------------------------------------------------------
  console.log("\n=========================================");
  console.log("PASS: " + passed + " / FAIL: " + failed);
  if (failed > 0) {
    console.error("FAILURES:");
    failures.forEach((f) => console.error("  - " + f));
    process.exit(1);
  }
  process.exit(0);
})().catch((e) => {
  console.error("test runner crashed:", e && e.stack || e);
  process.exit(2);
});
