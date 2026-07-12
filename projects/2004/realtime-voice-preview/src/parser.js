// Pure function-call parser for OpenAI Realtime events. Extracted from
// index.html so it can be unit-tested in Node and reused in the browser.
// State (funcItemRegistry, dispatchedFunctions, ...) lives on the parser
// instance so tests construct fresh instances.
//
// Browser:
//   const parser = VoiceParser.createParser({
//     sendOutput: (callId, payload) => dc.send(...),
//     log: (line, obj) => log(line, obj),
//     onBridgeCall: async ({ name, args, callId, itemId, source }) => { ... },
//   });
//   parser.handleEvent(JSON.parse(e.data));
//
// Node tests:
//   const { createParser } = require("./parser.js");
//   const parser = createParser({ sendOutput: mockSend, log: () => {} });
//   parser.handleEvent({ type: "response.output_item.added", ... });

(function (root, factory) {
  if (typeof module !== "undefined" && module.exports) {
    module.exports = factory();
  } else {
    root.VoiceParser = factory();
  }
}(typeof globalThis !== "undefined" ? globalThis : this, function () {

  function safeParseArgs(raw) {
    if (raw === undefined || raw === null || raw === "") return {};
    if (typeof raw === "object") {
      if (raw === null || Array.isArray(raw)) {
        const err = new Error("Arguments must be a JSON object, got " +
          (Array.isArray(raw) ? "array" : typeof raw));
        err.code = "MALFORMED_ARGS";
        err.raw = raw;
        throw err;
      }
      return raw;
    }
    if (typeof raw !== "string") return {};
    let parsed;
    try { parsed = JSON.parse(raw); }
    catch (e) {
      const err = new Error("Malformed JSON arguments: " + String(raw).slice(0, 120));
      err.code = "MALFORMED_ARGS";
      err.raw = raw;
      throw err;
    }
    if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
      const err = new Error("Arguments must be a JSON object, got " +
        (parsed === null ? "null" : Array.isArray(parsed) ? "array" : typeof parsed));
      err.code = "MALFORMED_ARGS";
      err.raw = raw;
      throw err;
    }
    return parsed;
  }

  function normalizeToolName(name) {
    if (!name) return null;
    const n = String(name).trim();
    if (n === "ask_starchild" || n === "askStarchild" ||
        n === "AskStarchild" || n === "ASK_STARCHILD") {
      return "ask_starchild";
    }
    return n;
  }

  function makeStableId(item) {
    return String(
      (item && (item.item_id || item.id)) ||
      (item && item.call_id) ||
      (item && item.output_index !== undefined ? "idx:" + item.output_index : "") ||
      Math.random().toString(36).slice(2, 10)
    );
  }

  function createParser(opts) {
    if (!opts || typeof opts.sendOutput !== "function") {
      throw new Error("createParser requires opts.sendOutput(callId, payload)");
    }
    const sendOutput = opts.sendOutput;
    const log = typeof opts.log === "function" ? opts.log : function () {};
    const onMissingCallId = typeof opts.onMissingCallId === "function"
      ? opts.onMissingCallId : function () {};
    const onMissingName = typeof opts.onMissingName === "function"
      ? opts.onMissingName : function () {};
    const onMalformedArgs = typeof opts.onMalformedArgs === "function"
      ? opts.onMalformedArgs : function () {};
    const onDispatched = typeof opts.onDispatched === "function"
      ? opts.onDispatched : function () {};
    const onBridgeCall = typeof opts.onBridgeCall === "function"
      ? opts.onBridgeCall : null;

    const funcItemRegistry = new Map();
    const inflightFunctions = new Set();
    const dispatchedFunctions = new Set();

    function rememberFunctionCallItem(item) {
      if (!item || item.type !== "function_call") return null;
      const id = item.item_id || item.id;
      if (!id) return null;
      const prev = funcItemRegistry.get(id) || {};
      const merged = {
        type: "function_call",
        item_id: id,
        output_index: item.output_index !== undefined ? item.output_index : prev.output_index,
        call_id: item.call_id || prev.call_id || null,
        name: normalizeToolName(item.name) || prev.name || null,
        arguments: item.arguments !== undefined ? item.arguments : (prev.arguments || ""),
      };
      funcItemRegistry.set(id, merged);
      return merged;
    }

    function resolveCallTarget(raw) {
      const item = (raw && raw.item) ? raw.item : raw;
      if (!item) return null;
      const id = item.item_id || item.id;
      if (!id) return null;
      let remembered = funcItemRegistry.get(id) || null;
      if (item.type === "function_call") {
        remembered = rememberFunctionCallItem(Object.assign({}, item, { item_id: id })) || remembered;
      }
      if (!remembered && item.output_index !== undefined) {
        for (const candidate of funcItemRegistry.values()) {
          if (candidate.output_index === item.output_index) {
            remembered = candidate;
            break;
          }
        }
      }
      const callId = item.call_id || (remembered && remembered.call_id) || null;
      const name = normalizeToolName(item.name || (remembered && remembered.name));
      const args = item.arguments !== undefined
        ? item.arguments
        : ((remembered && remembered.arguments) || "");
      const stableId = makeStableId({
        item_id: id,
        call_id: callId,
        output_index: item.output_index !== undefined
          ? item.output_index
          : (remembered && remembered.output_index),
      });
      return { id: id, callId: callId, name: name, args: args, stableId: stableId };
    }

    async function dispatchFunctionCall(rawItem, sourceLabel) {
      const target = resolveCallTarget(rawItem);
      if (!target || !target.id) {
        log("function call: missing item_id, cannot dispatch", { event: rawItem });
        onMissingCallId({ reason: "no_item_id", raw: rawItem, source: sourceLabel });
        return { dispatched: false, reason: "no_item_id" };
      }
      const dedupeKey = target.callId ? ("cid:" + target.callId) : ("sid:" + target.stableId);
      if (dispatchedFunctions.has(dedupeKey)) {
        log("function call: already dispatched, skip", { key: dedupeKey, source: sourceLabel });
        return { dispatched: false, reason: "duplicate", key: dedupeKey };
      }
      if (inflightFunctions.has(dedupeKey)) {
        log("function call: dispatch in flight, skip duplicate", { key: dedupeKey, source: sourceLabel });
        return { dispatched: false, reason: "inflight", key: dedupeKey };
      }
      if (!target.callId) {
        log("function call: missing call_id, cannot send function_call_output", {
          item_id: target.id, name: target.name, source: sourceLabel,
        });
        onMissingCallId({ reason: "no_call_id", item: target, source: sourceLabel });
        return { dispatched: false, reason: "no_call_id" };
      }
      if (!target.name) {
        log("function call: missing name even after registry correlation", {
          item_id: target.id, call_id: target.callId, source: sourceLabel,
        });
        sendOutput(target.callId, {
          ok: false,
          error: "tool_name_missing",
          message: "Realtime event did not include a tool name for call_id " + target.callId,
          item_id: target.id,
        });
        onMissingName({ item: target, source: sourceLabel });
        dispatchedFunctions.add(dedupeKey);
        return { dispatched: false, reason: "no_name" };
      }
      inflightFunctions.add(dedupeKey);
      dispatchedFunctions.add(dedupeKey);
      log("function call →", { name: target.name, callId: target.callId, item_id: target.id, source: sourceLabel });

      let args = {};
      let argsError = null;
      try { args = safeParseArgs(target.args); }
      catch (e) { argsError = e; }

      if (argsError) {
        log("function call: malformed arguments", { raw: target.args, message: argsError.message });
        sendOutput(target.callId, {
          ok: false,
          error: "malformed_arguments",
          message: argsError.message,
          raw_arguments: argsError.raw,
          item_id: target.id,
        });
        onMalformedArgs({ item: target, error: argsError });
        inflightFunctions.delete(dedupeKey);
        return { dispatched: false, reason: "malformed_args" };
      }

      let output = null;
      const canon = normalizeToolName(target.name);
      if (canon === "ask_starchild") {
        const q = (args && typeof args.question === "string") ? args.question.trim() : "";
        if (!q) {
          output = {
            ok: false,
            error: "missing_question",
            message: "ask_starchild requires a non-empty 'question' string.",
          };
        } else if (onBridgeCall) {
          try {
            output = await onBridgeCall({
              name: target.name, args: args, callId: target.callId,
              itemId: target.id, source: sourceLabel,
            });
          } catch (e) {
            output = { ok: false, error: "bridge_error",
              message: e && e.message ? e.message : String(e) };
          }
        } else {
          output = JSON.stringify({ ok: false, error: "bridge_not_configured",
            message: "ask_starchild bridge is not configured in this environment." });
        }
      } else {
        output = "unknown tool: " + target.name;
      }

      sendOutput(target.callId, output);
      onDispatched({ item: target, args: args, source: sourceLabel });
      inflightFunctions.delete(dedupeKey);
      return { dispatched: true, name: target.name, args: args };
    }

    function handleEvent(ev) {
      if (!ev || typeof ev.type !== "string") return null;
      const t = ev.type;
      if (t === "response.output_item.added") {
        const it = ev.item;
        if (it && it.type === "function_call") {
          rememberFunctionCallItem(it);
          log("output_item.added (function_call)", {
            item_id: it.item_id || it.id, name: it.name, call_id: it.call_id,
          });
        }
        return null;
      }
      if (t === "response.output_item.done") {
        const it = ev.item;
        if (it && it.type === "function_call") {
          rememberFunctionCallItem(it);
          return dispatchFunctionCall(it, "response.output_item.done");
        }
        return null;
      }
      if (t === "response.function_call_arguments.done") {
        return dispatchFunctionCall(ev, "response.function_call_arguments.done");
      }
      if (t === "response.done") {
        const out = ev.response && ev.response.output;
        if (!Array.isArray(out)) return null;
        return (async () => {
          for (const it of out) {
            if (it && it.type === "function_call") {
              rememberFunctionCallItem(it);
              await dispatchFunctionCall(it, "response.done.fallback");
            }
          }
        })();
      }
      return null;
    }

    return {
      handleEvent: handleEvent,
      dispatchFunctionCall: dispatchFunctionCall,
      rememberFunctionCallItem: rememberFunctionCallItem,
      resolveCallTarget: resolveCallTarget,
      safeParseArgs: safeParseArgs,
      normalizeToolName: normalizeToolName,
      makeStableId: makeStableId,
      _state: {
        funcItemRegistry: funcItemRegistry,
        inflightFunctions: inflightFunctions,
        dispatchedFunctions: dispatchedFunctions,
      },
    };
  }

  return {
    createParser: createParser,
    safeParseArgs: safeParseArgs,
    normalizeToolName: normalizeToolName,
    makeStableId: makeStableId,
  };
}));